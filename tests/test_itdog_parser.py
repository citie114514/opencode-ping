"""Tests for ITDOG node parsing (new 5-column format)."""

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
            "上海电信", "1.2.3.4", "Anycast/cloudflare.com", "30ms"
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

    def test_timeout(self):
        row = self._make_row([
            "北京联通", "5.6.7.8", "Anycast/cloudflare.com", "超时"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.node_id == 50
        assert node.status == NodeStatus.TIMEOUT.value
        assert node.latest_ms is None

    def test_zero_latency(self):
        row = self._make_row([
            "香港电信", "1.2.3.4", "Anycast/cloudflare.com", "<1ms"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.latest_ms == 0.1  # <1ms parsed as 0.1
        assert node.status == NodeStatus.SUCCESS.value

    def test_numeric_latency(self):
        row = self._make_row([
            "香港电信", "1.2.3.4", "Anycast/cloudflare.com", "10ms"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.latest_ms == 10.0

    def test_overseas(self):
        row = self._make_row([
            "日本东京", "100.200.300.400", "Anycast/cloudflare.com", "50ms"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.region == "海外"
        assert node.latest_ms == 50.0

    def test_gangaotai(self):
        row = self._make_row([
            "台湾台北", "1.2.3.4", "Anycast/cloudflare.com", "10ms"
        ])
        node = _parse_node_row(row, "8.8.8.8")
        assert node is not None
        assert node.region == "港澳台"
