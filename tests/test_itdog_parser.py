"""Tests for ITDOG client parsers (Playwright-based)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import NodeStatus
from services.itdog.client import (
    _parse_latency,
    _parse_seconds,
    _parse_ping_rows,
    _parse_http_rows,
    _parse_dns_rows,
)


class TestParseLatency:
    def test_normal(self):
        assert _parse_latency("84ms") == 84.0
        assert _parse_latency("123ms") == 123.0

    def test_timeout(self):
        assert _parse_latency("超时") is None
        assert _parse_latency("--") is None
        assert _parse_latency("") is None

    def test_less_than_one(self):
        assert _parse_latency("<1ms") == 0.1

    def test_none(self):
        assert _parse_latency(None) is None


class TestParseSeconds:
    def test_seconds(self):
        assert _parse_seconds("0.201s") == 201.0

    def test_ms(self):
        assert _parse_seconds("201ms") == 201.0

    def test_empty(self):
        assert _parse_seconds("--") is None
        assert _parse_seconds("") is None


class TestParsePingRows:
    def test_success(self):
        rows = [{
            "id": "10",
            "cells": ["电信 湖北十堰", "183.2.172.177:443", "中国/广东/广州/电信", "27ms", "广告"],
        }]
        nodes = _parse_ping_rows(rows, "www.baidu.com")
        assert len(nodes) == 1
        node = nodes[0]
        assert node.latest_ms == 27.0
        assert node.status == NodeStatus.SUCCESS.value
        assert node.resolved_ip == "183.2.172.177:443"
        assert node.isp == "电信"
        assert node.region == "华中"
        assert node.raw["ip_geo"] == "中国/广东/广州/电信"

    def test_timeout(self):
        rows = [{"id": "1", "cells": ["电信 湖北十堰", "解析失败", "", "超时", "广告"]}]
        nodes = _parse_ping_rows(rows, "host")
        assert nodes[0].status == NodeStatus.TIMEOUT.value


class TestParseHttpRows:
    def test_parse(self):
        rows = [{
            "id": "1",
            "cells": ["电信 湖北十堰", "183.2.172.177", "中国/广东/广州/电信",
                      "200", "0.201s", "0.026s", "0.028s", "0.083s", "--", "查看", "广告"],
        }]
        node = _parse_http_rows(rows, "https://www.baidu.com")[0]
        assert node.latest_ms == 201.0
        assert node.raw["http_status"] == "200"
        assert node.raw["dns_ms"] == 26.0
        assert node.raw["connect_ms"] == 28.0
        assert node.raw["download_ms"] == 83.0
        assert node.status == NodeStatus.SUCCESS.value


class TestParseDnsRows:
    def test_parse(self):
        rows = [{
            "id": "1",
            "cells": ["电信 湖北十堰", "www.baidu.com", "A",
                      "180.101.49.44\n180.101.51.73", "2", "查看", "6ms", "运营商DNS", "广告"],
        }]
        node = _parse_dns_rows(rows, "www.baidu.com")[0]
        assert node.latest_ms == 6.0
        assert node.raw["type"] == "A"
        assert node.raw["answers"] == ["180.101.49.44", "180.101.51.73"]
        assert node.raw["answer_count"] == "2"
        assert node.raw["dns_server"] == "运营商DNS"
        assert node.resolved_ip == "180.101.49.44"
