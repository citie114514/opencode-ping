"""Tests for aggregation and summary."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import PingNode, NodeStatus
from ping import aggregate_regions, build_summary


def _make_node(region="华东", status=NodeStatus.SUCCESS.value, ms=30.0,
               loss=0.0, sent=10, received=10, **kwargs):
    n = PingNode(region=region, status=status, latest_ms=ms,
                 loss_percent=loss, sent=sent, received=received, **kwargs)
    return n


class TestAggregateRegions:
    def test_single_region(self):
        nodes = [
            _make_node(region="华东", ms=30),
            _make_node(region="华东", ms=40),
            _make_node(region="华东", ms=50),
        ]
        regions = aggregate_regions(nodes)
        assert "华东" in regions
        assert regions["华东"]["total"] == 3
        assert regions["华东"]["success"] == 3
        assert regions["华东"]["avg_ms"] == 40.0

    def test_multiple_regions(self):
        nodes = [
            _make_node(region="华东", ms=30),
            _make_node(region="华北", ms=50),
            _make_node(region="华南", ms=40),
            _make_node(region="海外", ms=150),
        ]
        regions = aggregate_regions(nodes)
        assert len(regions) == 4
        assert regions["华东"]["total"] == 1
        assert regions["华北"]["total"] == 1
        assert regions["华南"]["total"] == 1
        assert regions["海外"]["total"] == 1

    def test_with_timeout(self):
        nodes = [
            _make_node(region="华东", ms=30),
            _make_node(region="华东", status=NodeStatus.TIMEOUT.value, ms=None, sent=10, received=0, loss=100),
        ]
        regions = aggregate_regions(nodes)
        assert regions["华东"]["total"] == 2
        assert regions["华东"]["success"] == 1
        assert regions["华东"]["timeout"] == 1
        assert regions["华东"]["avg_ms"] == 30.0  # Only success nodes

    def test_with_loss(self):
        nodes = [
            _make_node(region="华东", ms=30),
            _make_node(region="华东", status=NodeStatus.PARTIAL_LOSS.value, ms=40, loss=30, sent=10, received=7),
        ]
        regions = aggregate_regions(nodes)
        assert regions["华东"]["loss"] == 1
        assert regions["华东"]["avg_ms"] == 35.0

    def test_empty(self):
        regions = aggregate_regions([])
        assert len(regions) == 0


class TestBuildSummary:
    def test_all_success(self):
        nodes = [_make_node(ms=i * 10) for i in range(10)]
        s = build_summary(nodes)
        assert s["total"] == 10
        assert s["success"] == 10
        assert s["timeout"] == 0
        assert s["partial_loss"] == 0
        assert s["overall_loss_percent"] == 0.0

    def test_mixed(self):
        nodes = (
            [_make_node(ms=i * 10) for i in range(90)] +
            [_make_node(status=NodeStatus.PARTIAL_LOSS.value, ms=50, loss=30, sent=10, received=7) for _ in range(5)] +
            [_make_node(status=NodeStatus.TIMEOUT.value, ms=None, sent=10, received=0, loss=100) for _ in range(5)]
        )
        s = build_summary(nodes)
        assert s["total"] == 100
        assert s["success"] == 90
        assert s["partial_loss"] == 5
        assert s["timeout"] == 5
        assert s["overall_loss_percent"] > 0

    def test_all_timeout(self):
        nodes = [_make_node(status=NodeStatus.TIMEOUT.value, ms=None, sent=10, received=0, loss=100) for _ in range(50)]
        s = build_summary(nodes)
        assert s["total"] == 50
        assert s["timeout"] == 50
        assert s["success"] == 0
        assert s["overall_loss_percent"] == 100.0
