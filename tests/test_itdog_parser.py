"""Tests for ITDOG client (Playwright-based)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import PingNode, NodeStatus
from services.itdog.client import _parse_latency


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
