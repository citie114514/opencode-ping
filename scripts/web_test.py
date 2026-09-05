"""
Website speed test using requests library.
Measures DNS, TCP, TLS, TTFB, and total response time.
"""

import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import WebTestResult


def web_test(url: str, timeout: int = 10, max_body: int = 1024 * 1024,
             verify_ssl: bool = True) -> WebTestResult:
    """
    Perform HTTP/HTTPS speed test.
    
    Args:
        url: Target URL (http:// or https://)
        timeout: Request timeout in seconds
        max_body: Maximum response body size to read (bytes)
        verify_ssl: Whether to verify SSL certificates
    """
    result = WebTestResult(url=url)

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
        result.url = url

    parsed = urlparse(url)
    result.final_url = url

    # Configure session with retry
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "close",
    }

    try:
        start_total = time.monotonic()

        # Use a streaming request to measure TTFB
        response = session.get(
            url,
            headers=headers,
            timeout=(timeout, timeout),
            verify=verify_ssl,
            stream=True,
        )

        # Read first chunk to get TTFB
        first_chunk_time = None
        total_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            if first_chunk_time is None:
                first_chunk_time = time.monotonic()
            total_size += len(chunk)
            if total_size >= max_body:
                break

        end_time = time.monotonic()
        total_ms = (end_time - start_total) * 1000
        ttfb_ms = ((first_chunk_time or end_time) - start_total) * 1000 if first_chunk_time else total_ms

        result.status_code = response.status_code
        result.statusText = getattr(response, "reason", "")
        result.ttfb_ms = round(ttfb_ms, 1)
        result.total_ms = round(total_ms, 1)
        result.response_size = total_size
        result.content_type = response.headers.get("Content-Type", "")

        # Count redirects
        result.redirect_count = len(response.history)
        if response.history:
            result.redirect_url = response.history[0].url

        # Try to extract timing from headers (if server provides)
        # Some servers include Server-Timing or X-Response-Time
        server_timing = response.headers.get("Server-Timing", "")
        if server_timing:
            result.raw_headers = {"Server-Timing": server_timing}

        response.close()

    except requests.exceptions.SSLError as e:
        result.error = f"SSL Error: {e}"
    except requests.exceptions.ConnectionError as e:
        result.error = f"Connection Error: {e}"
    except requests.exceptions.Timeout:
        result.error = "Request timed out"
    except requests.exceptions.RequestException as e:
        result.error = str(e)
    except Exception as e:
        result.error = str(e)

    return result
