"""Tests for TCP ping."""

import socket
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from tcp_ping import tcp_ping


ADDRINFO_V4 = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
ADDRINFO_V6 = [
    (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0))
]


class TestTcpPing:
    @patch("tcp_ping.socket.getaddrinfo", return_value=ADDRINFO_V4)
    @patch("tcp_ping.socket.socket")
    def test_success(self, mock_socket, mock_gai):
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

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

    @patch("tcp_ping.socket.getaddrinfo", return_value=ADDRINFO_V4)
    @patch("tcp_ping.socket.socket")
    def test_all_timeout(self, mock_socket, mock_gai):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("Connection timed out")
        mock_socket.return_value = mock_sock

        result = tcp_ping("192.0.2.1", 443, count=3, timeout=1, delay=0)
        assert result.success is False
        assert result.timeouts == 3
        assert "timed out" in result.error

    @patch("tcp_ping.socket.getaddrinfo", return_value=ADDRINFO_V4)
    @patch("tcp_ping.socket.socket")
    def test_connection_refused(self, mock_socket, mock_gai):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")
        mock_socket.return_value = mock_sock

        result = tcp_ping("localhost", 1, count=2, timeout=1, delay=0)
        assert result.success is False
        assert result.failures == 2

    @patch("tcp_ping.socket.getaddrinfo", return_value=ADDRINFO_V4)
    @patch("tcp_ping.socket.socket")
    def test_partial_success(self, mock_socket, mock_gai):
        call_count = 0

        def socket_factory(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_sock = MagicMock()
            if call_count == 2:
                mock_sock.connect.side_effect = socket.timeout("Connection timed out")
            return mock_sock

        mock_socket.side_effect = socket_factory
        result = tcp_ping("example.com", 443, count=3, timeout=5, delay=0)
        assert result.success is True
        assert result.successes == 2
        assert result.timeouts == 1

    @patch("tcp_ping.socket.getaddrinfo", return_value=ADDRINFO_V6)
    @patch("tcp_ping.socket.socket")
    def test_ipv6(self, mock_socket, mock_gai):
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        result = tcp_ping("example.com", 443, count=1, timeout=5, delay=0, ipv6=True)
        assert result.ipv6 is True
        assert result.success is True
        # getaddrinfo must be called with AF_INET6 when ipv6 is requested
        assert mock_gai.call_args[0][2] == socket.AF_INET6
