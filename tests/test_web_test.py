"""Tests for web test."""

from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from web_test import web_test


class TestWebTest:
    @patch("web_test.requests.Session")
    def test_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.history = []
        mock_response.iter_content.return_value = [b"Hello, World!"]
        mock_session.get.return_value = mock_response

        result = web_test("https://example.com", timeout=10)
        assert result.status_code == 200
        assert result.response_size == 13
        assert result.content_type == "text/html"
        assert result.error == ""

    @patch("web_test.requests.Session")
    def test_redirect(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_history = MagicMock()
        mock_history.url = "http://example.com"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.history = [mock_history]
        mock_response.iter_content.return_value = [b"Redirected"]
        mock_session.get.return_value = mock_response

        result = web_test("http://example.com", timeout=10)
        assert result.redirect_count == 1
        assert result.redirect_url == "http://example.com"

    @patch("web_test.requests.Session")
    def test_404(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.headers = {}
        mock_response.history = []
        mock_response.iter_content.return_value = []
        mock_session.get.return_value = mock_response

        result = web_test("https://example.com/nonexistent", timeout=10)
        assert result.status_code == 404
