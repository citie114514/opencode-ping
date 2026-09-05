"""Tests for ITDOG node parsing."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import PingNode, NodeStatus
from services.itdog.client import _parse_node_row


class TestParseNodeRow:
    def _make_row(self, cells_text):
        """Create a mock table row with the given cell texts."""
        from bs4 import BeautifulSoup
        html = "<tr node='50'>"
        for text in cells_text:
            html += f"<td>{text}</td>"
        html += "</tr>"
        soup = BeautifulSoup(html, "lxml")
        return soup.find("tr")

    def test_success(self):
        row = self._make_row([
            "上海电信", "1.2.3.4", "中国/上海/阿里云",
            "0%", "100", "30", "25", "35", "30"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.node_id == 50
        assert node.node_name == "上海电信"
        assert node.resolved_ip == "1.2.3.4"
        assert node.region == "华东"
        assert node.province == "上海"
        assert node.isp == "电信"
        assert node.latest_ms == 30.0
        assert node.status == NodeStatus.SUCCESS.value
        assert node.sent == 100
        assert node.received == 100
        assert node.loss_percent == 0.0

    def test_timeout(self):
        row = self._make_row([
            "北京联通", "5.6.7.8", "中国/北京/联通",
            "100%", "100", "超时", "--", "--", "--"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.node_id == 50
        assert node.status == NodeStatus.TIMEOUT.value
        assert node.latest_ms is None
        assert node.sent == 100
        assert node.received == 0
        assert node.loss_percent == 100.0

    def test_partial_loss(self):
        row = self._make_row([
            "广东广州电信", "1.2.3.4", "中国/广东/电信",
            "30%", "100", "40", "30", "50", "40"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.loss_percent == 30.0
        assert node.sent == 100
        assert node.received == 70
        assert node.status == NodeStatus.PARTIAL_LOSS.value

    def test_overseas(self):
        row = self._make_row([
            "日本东京", "100.200.300.400", "日本/东京",
            "0%", "100", "50", "40", "60", "50"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.region == "海外"
        assert node.latest_ms == 50.0

    def test_gangaotai(self):
        row = self._make_row([
            "台湾台北", "1.2.3.4", "台湾/台北",
            "0%", "100", "10", "8", "12", "10"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.region == "港澳台"
