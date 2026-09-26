"""Tests for the ITDOG IPv6 TCPing tool wiring (`/tcping_ipv6/`)."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import NodeStatus  # noqa: E402
from services.itdog.client import (  # noqa: E402
    TOOLS,
    _PARSERS,
    _parse_ping_rows,
)
from services.browser import host_for_url  # noqa: E402


class TestToolRegistry:
    def test_tcping6_registered(self):
        assert "tcping6" in TOOLS
        path, button = TOOLS["tcping6"]
        assert path == "/tcping_ipv6/"
        assert button == "单次测试"

    def test_tcping6_has_parser(self):
        assert "tcping6" in _PARSERS

    def test_existing_tools_untouched(self):
        for name in ("ping", "ping6", "tcping", "http", "dns"):
            assert name in TOOLS
            assert name in _PARSERS


class TestTcping6Parsing:
    ROWS = [
        {"id": "1", "cells": ["电信 福建福州", "[2408:8248::1]", "中国 福建", "12ms", "ad"]},
        {"id": "2", "cells": ["联通 上海", "[2408:8248::2]", "中国 上海", "超时", "ad"]},
    ]

    def test_marks_ipv6(self):
        nodes = _PARSERS["tcping6"](self.ROWS, "2408:8248::1")
        assert len(nodes) == 2
        assert all(n.raw["ipv6"] is True for n in nodes)

    def test_success_and_timeout(self):
        nodes = _PARSERS["tcping6"](self.ROWS, "2408:8248::1")
        assert nodes[0].status == NodeStatus.SUCCESS.value
        assert nodes[0].latest_ms == 12.0
        assert nodes[1].status == NodeStatus.TIMEOUT.value
        assert nodes[1].latest_ms is None

    def test_ipv4_parser_marks_ipv6_false(self):
        nodes = _PARSERS["tcping"](self.ROWS, "1.2.3.4")
        assert all(n.raw["ipv6"] is False for n in nodes)


class TestHostForUrl:
    def test_bare_ipv6_gets_brackets(self):
        assert host_for_url("2408:8248::1") == "[2408:8248::1]"

    def test_already_bracketed(self):
        assert host_for_url("[2408:8248::1]") == "[2408:8248::1]"

    def test_hostname_unchanged(self):
        assert host_for_url("www.qq.com") == "www.qq.com"

    def test_ipv4_untouched(self):
        assert host_for_url("1.2.3.4") == "1.2.3.4"
