"""Tests for host parsing (including IPv6 literals)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import parse_host


class TestParseHost:
    def test_plain_host(self):
        assert parse_host("example.com") == ("example.com", None, "example.com")

    def test_host_port(self):
        host, port, _ = parse_host("example.com:8080")
        assert host == "example.com"
        assert port == 8080

    def test_url(self):
        host, port, _ = parse_host("https://example.com/path")
        assert host == "example.com"
        assert port == 443

    def test_ipv4(self):
        host, port, _ = parse_host("1.2.3.4")
        assert host == "1.2.3.4"
        assert port is None

    def test_ipv6_bare(self):
        host, port, _ = parse_host("2606:4700::6811:dfe3")
        assert host == "2606:4700::6811:dfe3"
        assert port is None

    def test_ipv6_bracketed_with_port(self):
        host, port, _ = parse_host("[2606:4700::6811:dfe3]:443")
        assert host == "2606:4700::6811:dfe3"
        assert port == 443

    def test_ipv6_url(self):
        host, port, _ = parse_host("https://[2606:4700::6811:dfe3]/")
        assert host == "2606:4700::6811:dfe3"
        assert port == 443
