"""Tests for local ICMP ping."""

import platform
import subprocess
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from local_ping import local_ping, _parse_windows_ping, _parse_linux_ping


class TestParseWindowsPing:
    def test_normal(self):
        output = """
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=15ms TTL=118
Reply from 8.8.8.8: bytes=32 time=18ms TTL=118
Reply from 8.8.8.8: bytes=32 time=20ms TTL=118
Reply from 8.8.8.8: bytes=32 time=24ms TTL=118

Ping statistics for 8.8.8.8:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 15ms, Maximum = 24ms, Average = 19ms
"""
        result = _parse_windows_ping(output)
        assert result is not None
        assert result["sent"] == 4
        assert result["received"] == 4
        assert result["loss_percent"] == 0.0
        assert result["min_ms"] == 15.0
        assert result["max_ms"] == 24.0
        assert result["avg_ms"] == 19.0

    def test_partial_loss(self):
        output = """
Ping statistics for 8.8.8.8:
    Packets: Sent = 10, Received = 7, Lost = 3 (30% loss),
Approximate round trip times in milli-seconds:
    Minimum = 15ms, Maximum = 24ms, Average = 18ms
"""
        result = _parse_windows_ping(output)
        assert result is not None
        assert result["sent"] == 10
        assert result["received"] == 7
        assert result["loss_percent"] == 30.0

    def test_all_timeout(self):
        output = """
Ping statistics for 8.8.8.8:
    Packets: Sent = 10, Received = 0, Lost = 10 (100% loss),
"""
        result = _parse_windows_ping(output)
        assert result is not None
        assert result["sent"] == 10
        assert result["received"] == 0
        assert result["loss_percent"] == 100.0


class TestParseLinuxPing:
    def test_normal(self):
        output = """
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=15.1 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=18.2 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=20.3 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 15.1/17.9/20.3/2.1 ms
"""
        result = _parse_linux_ping(output)
        assert result is not None
        assert result["sent"] == 3
        assert result["received"] == 3
        assert result["loss_percent"] == 0.0
        assert result["min_ms"] == 15.1
        assert result["avg_ms"] == 17.9
        assert result["max_ms"] == 20.3

    def test_partial_loss(self):
        output = """
3 packets transmitted, 2 received, 33% packet loss, time 2002ms
rtt min/avg/max/mdev = 15.1/17.9/20.3/2.1 ms
"""
        result = _parse_linux_ping(output)
        assert result is not None
        assert result["sent"] == 3
        assert result["received"] == 2
        assert result["loss_percent"] == 33.0

    def test_all_timeout(self):
        output = """
10 packets transmitted, 0 received, 100% packet loss
"""
        result = _parse_linux_ping(output)
        assert result is not None
        assert result["sent"] == 10
        assert result["received"] == 0
        assert result["loss_percent"] == 100.0

    def test_macos_format(self):
        output = """
round-trip min/avg/max/stddev = 15.123/18.456/24.789/2.345 ms
"""
        result = _parse_linux_ping(output)
        assert result is not None
        assert result["min_ms"] == 15.123
        assert result["avg_ms"] == 18.456
        assert result["max_ms"] == 24.789


class TestLocalPing:
    @patch("local_ping.subprocess.run")
    def test_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.stdout = "Packets: Sent = 10, Received = 10, Lost = 0 (0% loss)\nMinimum = 15ms, Maximum = 24ms, Average = 18ms"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = local_ping("8.8.8.8", count=10, timeout=5)
        assert result.sent == 10
        assert result.received == 10
        assert result.loss_percent == 0.0
        assert result.avg_ms == 18.0

    @patch("local_ping.subprocess.run")
    def test_timeout(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.stdout = "Packets: Sent = 10, Received = 0, Lost = 10 (100% loss)"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = local_ping("192.0.2.1", count=10, timeout=1)
        assert result.sent == 10
        assert result.received == 0
        assert result.loss_percent == 100.0

    @patch("local_ping.subprocess.run", side_effect=FileNotFoundError)
    def test_ping_not_found(self, mock_run):
        result = local_ping("8.8.8.8")
        assert result.error == "ping command not found"
