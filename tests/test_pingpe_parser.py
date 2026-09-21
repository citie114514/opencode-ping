"""Tests for ping.pe client parsers (Playwright-based)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import NodeStatus
from services.pingpe.client import _kind_from_header, _parse_rows, _count_ready


PING_HEADER = ["Geo", "ISP", "Loss", "Sent", "Last", "Avg", "Best", "Worst", "StDev", "MTR▾", "Chart"]


class TestKindFromHeader:
    def test_ping(self):
        assert _kind_from_header(PING_HEADER) == "ping"

    def test_tcp(self):
        assert _kind_from_header(["Location", "ISP", "TCP port check result"]) == "tcp"

    def test_dig(self):
        assert _kind_from_header(["Location", "ISP", "dig response"]) == "dig"


class TestParsePingRows:
    def test_success(self):
        rows = [PING_HEADER, ["Canada, BC, Vancouver", "Shaw", "0%", "6", "204.36", "215.48", "204.36", "237.34", "12.23", "...", ""]]
        nodes = _parse_rows(rows, "www.baidu.com")
        assert len(nodes) == 1
        node = nodes[0]
        assert node.latest_ms == 204.36
        assert node.avg_ms == 215.48
        assert node.min_ms == 204.36
        assert node.max_ms == 237.34
        assert node.sent == 6
        assert node.loss_percent == 0.0
        assert node.status == NodeStatus.SUCCESS.value
        assert node.isp == "Shaw"

    def test_full_loss(self):
        rows = [PING_HEADER, ["Japan, Tokyo", "NTT", "100%", "6", "", "", "", "", "", "...", ""]]
        node = _parse_rows(rows, "host")[0]
        assert node.status == NodeStatus.TIMEOUT.value
        assert node.latest_ms is None

    def test_skips_header_and_short_rows(self):
        rows = [PING_HEADER, ["", "", "", "", "", "", "", "", "", "", ""], ["Canada", "Shaw"]]
        assert _parse_rows(rows, "host") == []


class TestParseTcpRows:
    def test_success(self):
        rows = [
            ["Location", "ISP", "TCP port check result"],
            ["Canada, BC, Vancouver", "Shaw", "Connection to 103.235.46.115:443 successful — 189.32 ms"],
        ]
        node = _parse_rows(rows, "www.baidu.com")[0]
        assert node.latest_ms == 189.32
        assert node.status == NodeStatus.SUCCESS.value
        assert node.resolved_ip == "103.235.46.115"

    def test_failed(self):
        rows = [
            ["Location", "ISP", "TCP port check result"],
            ["Canada, BC, Vancouver", "Shaw", "Connection to 1.2.3.4:443 failed — timeout"],
        ]
        node = _parse_rows(rows, "host")[0]
        assert node.status == NodeStatus.TIMEOUT.value


class TestParseDigRows:
    def test_parse(self):
        rows = [
            ["Location", "ISP", "dig response"],
            ["Canada, BC, Vancouver", "Shaw",
             "www.baidu.com. 150 IN CNAME www.a.shifen.com.\nwww.a.shifen.com. 42 IN A 183.2.172.177 [23 ms]"],
        ]
        node = _parse_rows(rows, "www.baidu.com")[0]
        assert node.latest_ms == 23.0
        assert len(node.raw["answers"]) == 2
        assert node.status == NodeStatus.SUCCESS.value


class TestCountReady:
    def test_counts_ping_rows(self):
        rows = [PING_HEADER, ["Canada", "Shaw", "0%", "6", "12.3", "12.3", "12.3", "12.3", "0", "...", ""]]
        assert _count_ready(rows) == 1

    def test_empty(self):
        assert _count_ready([]) == 0
        assert _count_ready([PING_HEADER]) == 0
