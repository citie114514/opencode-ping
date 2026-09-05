"""Tests for packet loss handling."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import PingNode, NodeStatus
from ping import build_summary


class TestPacketLoss:
    def test_zero_loss(self):
        node = PingNode(
            node_id=1, node_name="Test", target="8.8.8.8",
            latest_ms=30.0, sent=10, received=10, loss_percent=0.0,
        )
        assert node.loss_percent == 0.0
        assert node.status == NodeStatus.SUCCESS.value

    def test_30_percent_loss(self):
        """30% loss: sent=10, received=7."""
        node = PingNode(
            node_id=1, node_name="Test", target="8.8.8.8",
            latest_ms=40.0, sent=10, received=7, loss_percent=30.0,
        )
        assert node.sent == 10
        assert node.received == 7
        assert node.loss_percent == 30.0
        assert node.status == NodeStatus.PARTIAL_LOSS.value

    def test_100_percent_loss(self):
        """100% loss: sent=10, received=0."""
        node = PingNode(
            node_id=1, node_name="Test", target="8.8.8.8",
            sent=10, received=0, loss_percent=100.0,
        )
        assert node.sent == 10
        assert node.received == 0
        assert node.loss_percent == 100.0
        assert node.status == NodeStatus.TIMEOUT.value

    def test_overall_loss_calculation(self):
        """Overall loss should be calculated from total sent/received."""
        nodes = [
            PingNode(node_id=1, node_name="A", target="8.8.8.8",
                     latest_ms=30.0, sent=10, received=10, loss_percent=0.0),
            PingNode(node_id=2, node_name="B", target="8.8.8.8",
                     latest_ms=40.0, sent=10, received=7, loss_percent=30.0),
            PingNode(node_id=3, node_name="C", target="8.8.8.8",
                     sent=10, received=0, loss_percent=100.0,
                     status=NodeStatus.TIMEOUT.value),
        ]
        s = build_summary(nodes)
        # Total sent=30, received=17, loss=13/30=43.3%
        assert s["total_sent"] == 30
        assert s["total_received"] == 17
        assert abs(s["overall_loss_percent"] - 43.3) < 0.1

    def test_loss_nodes_counted(self):
        """Loss nodes should be counted separately from timeout."""
        nodes = [
            PingNode(node_id=1, node_name="A", target="8.8.8.8",
                     latest_ms=30.0, sent=10, received=10, loss_percent=0.0),
            PingNode(node_id=2, node_name="B", target="8.8.8.8",
                     latest_ms=40.0, sent=10, received=7, loss_percent=30.0),
            PingNode(node_id=3, node_name="C", target="8.8.8.8",
                     latest_ms=50.0, sent=10, received=8, loss_percent=20.0),
            PingNode(node_id=4, node_name="D", target="8.8.8.8",
                     sent=10, received=0, loss_percent=100.0,
                     status=NodeStatus.TIMEOUT.value),
        ]
        s = build_summary(nodes)
        assert s["partial_loss"] == 2
        assert s["timeout"] == 1
        assert s["success"] == 1
