"""Tests for timeout handling."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import PingNode, NodeStatus


class TestTimeoutHandling:
    def test_timeout_node(self):
        """Timeout node should have status=timeout, loss=100%."""
        node = PingNode(
            node_id=1,
            node_name="北京电信",
            region="华北",
            target="8.8.8.8",
            sent=10,
            received=0,
            loss_percent=100.0,
            status=NodeStatus.TIMEOUT.value,
        )
        assert node.status == NodeStatus.TIMEOUT.value
        assert node.loss_percent == 100.0
        assert node.received == 0
        assert node.latest_ms is None

    def test_timeout_not_success(self):
        """Timeout should not be classified as success."""
        node = PingNode(
            node_id=1,
            node_name="Test",
            target="8.8.8.8",
            sent=10,
            received=0,
            loss_percent=100.0,
        )
        # __post_init__ should set status to timeout
        assert node.status == NodeStatus.TIMEOUT.value

    def test_unavailable_node(self):
        """Node unavailable (ITDOG node itself down)."""
        node = PingNode(
            node_id=1,
            node_name="Test Node",
            target="8.8.8.8",
            status=NodeStatus.UNAVAILABLE.value,
            error="Node unavailable",
        )
        assert node.status == NodeStatus.UNAVAILABLE.value
        assert node.sent == 0
        assert node.received == 0

    def test_zero_loss(self):
        """Zero loss should be success."""
        node = PingNode(
            node_id=1,
            node_name="Test",
            target="8.8.8.8",
            latest_ms=30.0,
            sent=10,
            received=10,
            loss_percent=0.0,
        )
        assert node.status == NodeStatus.SUCCESS.value

    def test_partial_loss_30_percent(self):
        """30% loss should be partial_loss."""
        node = PingNode(
            node_id=1,
            node_name="Test",
            target="8.8.8.8",
            latest_ms=40.0,
            sent=10,
            received=7,
            loss_percent=30.0,
        )
        assert node.status == NodeStatus.PARTIAL_LOSS.value

    def test_timeout_in_list(self):
        """Timeout nodes should appear in the nodes list."""
        nodes = [
            PingNode(node_id=1, node_name="A", target="8.8.8.8",
                     latest_ms=30.0, sent=10, received=10, loss_percent=0.0),
            PingNode(node_id=2, node_name="B", target="8.8.8.8",
                     sent=10, received=0, loss_percent=100.0,
                     status=NodeStatus.TIMEOUT.value),
        ]
        timeout_nodes = [n for n in nodes if n.status == NodeStatus.TIMEOUT.value]
        assert len(timeout_nodes) == 1
        assert timeout_nodes[0].node_id == 2
