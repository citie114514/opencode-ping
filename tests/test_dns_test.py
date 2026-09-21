"""Tests for local DNS resolution test."""

import socket
from unittest.mock import patch

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import dns_test
from dns_test import dns_test as run_dns_test


ADDRINFO_V4 = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 0))]
ADDRINFO_V6 = [
    (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1", 0, 0, 0))
]


@pytest.fixture
def socket_only(monkeypatch):
    """Force the stdlib socket fallback so tests never hit the network."""
    monkeypatch.setattr(dns_test, "_HAVE_DNSPYTHON", False)


class TestDnsTest:
    @patch("dns_test.socket.getaddrinfo", return_value=ADDRINFO_V4)
    def test_a_record(self, mock_gai, socket_only):
        result = run_dns_test("example.com", rtype="A")
        # getaddrinfo is called with AF_INET for an A lookup
        assert mock_gai.call_args[0][2] == socket.AF_INET
        assert result.rtype == "A"
        assert result.records.get("A") == ["1.2.3.4"]
        assert result.resolve_ms is not None
        assert result.error == ""

    @patch("dns_test.socket.getaddrinfo", return_value=ADDRINFO_V6)
    def test_aaaa_via_ipv6_flag(self, mock_gai, socket_only):
        # ipv6 hint upgrades the default A lookup to AAAA
        result = run_dns_test("example.com", rtype="A", ipv6=True)
        assert result.rtype == "AAAA"
        assert mock_gai.call_args[0][2] == socket.AF_INET6
        assert result.records.get("AAAA") == ["2606:4700::1"]

    @patch("dns_test.socket.getaddrinfo", side_effect=socket.gaierror("not found"))
    def test_resolution_failure(self, mock_gai, socket_only):
        result = run_dns_test("nonexistent.invalid")
        assert result.answers == []
        assert "failed" in result.error

    def test_unsupported_type_without_dnspython(self, socket_only):
        result = run_dns_test("example.com", rtype="MX")
        assert result.error
        assert "dnspython" in result.error
