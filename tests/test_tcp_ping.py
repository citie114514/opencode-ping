"""Tests for TCP ping."""

import socket
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from tcp_ping import tcp_ping


class TestTcpPing:
    @patch("tcp_ping.socket.create_connection")
    def test_success(self, mock_conn):
        mock_sock = MagicMock()
        mock_conn.return_value = mock_sock

        result = tcp_ping("example.com", 443, count=3, timeout=5, delay=0)
        assert result.success is True
        assert result.host == "example.com"
        assert result.port == 443
        assert result.attempts == 3
        assert result.successes == 3
        assert result.failures == 0
        assert result.timeouts == 0
        assert result.connect_ms is not None
        assert result.min_ms is not None
        assert result.max_ms is not None
        assert result.avg_ms is not None

    @patch("tcp_ping.socket.create_connection", side_effect=socket.timeout)
    def test_all_timeout(self, mock_conn):
        result = tcp_ping("192.0.2.1", 443, count=3, timeout=1, delay=0)
        assert result.success is False
        assert result.timeouts == 3
        assert "timed out" in result.error

    @patch("tcp_ping.socket.create_connection", side_effect=ConnectionRefusedError)
    def test_connection_refused(self, mock_conn):
        result = tcp_ping("localhost", 1, count=2, timeout=1, delay=0)
        assert result.success is False
        assert result.failures == 2

    @patch("tcp_ping.socket.create_connection")
    def test_partial_success(self, mock_conn):
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise socket.timeout("Connection timed out")
            mock_sock = MagicMock()
            return mock_sock

        mock_conn.side_effect = side_effect
        result = tcp_ping("example.com", 443, count=3, timeout=5, delay=0)
        assert result.success is True
        assert result.successes == 2
        assert result.timeouts == 1
