"""
Website speed test using the requests library.

Measures DNS, TCP, TLS, TTFB and total response time. The DNS/TCP/TLS phases
are measured with a dedicated socket probe so they are available even when the
request itself is served from a reused connection.
"""

import socket
import ssl
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import WebTestResult


def _phase_timings(host: str, port: int, use_tls: bool, timeout: int,
                   ipv6: bool = False):
    """
    Measure DNS / TCP / TLS setup time with a short-lived probe socket.

    Returns (dns_ms, tcp_ms, tls_ms, resolved_ip, error).
    """
    family = socket.AF_INET6 if ipv6 else socket.AF_UNSPEC
    dns_ms = tcp_ms = tls_ms = None
    resolved_ip = ""
    err = ""

    try:
        t0 = time.monotonic()
        infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
        dns_ms = round((time.monotonic() - t0) * 1000, 1)
    except OSError as exc:
        return dns_ms, tcp_ms, tls_ms, resolved_ip, f"DNS error: {exc}"

    if infos:
        resolved_ip = infos[0][4][0]
    af, socktype, proto, _canon, sockaddr = infos[0]

    sock = socket.socket(af, socktype, proto)
    try:
        sock.settimeout(timeout)
        t1 = time.monotonic()
        sock.connect(sockaddr)
        tcp_ms = round((time.monotonic() - t1) * 1000, 1)

        if use_tls:
            t2 = time.monotonic()
            ctx = ssl.create_default_context()
            ctx.wrap_socket(sock, server_hostname=host)
            tls_ms = round((time.monotonic() - t2) * 1000, 1)
    except Exception as exc:  # noqa: BLE001 - probe failures are non-fatal
        err = str(exc)
    finally:
        try:
            sock.close()
        except OSError:
            pass

    return dns_ms, tcp_ms, tls_ms, resolved_ip, err


def web_test(url: str, timeout: int = 10, max_body: int = 1024 * 1024,
             verify_ssl: bool = True, ipv6: bool = False) -> WebTestResult:
    """
    Perform an HTTP/HTTPS speed test.

    Args:
        url: Target URL (http:// or https://)
        timeout: Request timeout in seconds
        max_body: Maximum response body size to read (bytes)
        verify_ssl: Whether to verify SSL certificates
        ipv6: Hint to probe DNS/TCP/TLS over IPv6.
    """
    result = WebTestResult(url=url, ipv6=ipv6)

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
        result.url = url

    parsed = urlparse(url)
    result.final_url = url
    host = parsed.hostname or ""
    use_tls = parsed.scheme == "https"
    port = parsed.port or (443 if use_tls else 80)

    # Phase timings via a dedicated probe.
    dns_ms, tcp_ms, tls_ms, resolved_ip, probe_err = _phase_timings(
        host, port, use_tls, timeout, ipv6=ipv6
    )
    result.dns_ms = dns_ms
    result.tcp_ms = tcp_ms
    result.tls_ms = tls_ms
    result.resolved_ip = resolved_ip

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

        response = session.get(
            url,
            headers=headers,
            timeout=(timeout, timeout),
            verify=verify_ssl,
            stream=True,
        )

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
        ttfb_ms = ((first_chunk_time or end_time) - start_total) * 1000

        result.status_code = response.status_code
        result.status_text = getattr(response, "reason", "")
        result.ttfb_ms = round(ttfb_ms, 1)
        result.total_ms = round(total_ms, 1)
        result.response_size = total_size
        result.content_type = response.headers.get("Content-Type", "")

        result.redirect_count = len(response.history)
        if response.history:
            result.redirect_url = response.history[0].url

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

    # If the request failed but the probe also failed, surface the probe error.
    if result.error and probe_err and not result.resolved_ip:
        result.error = f"{result.error} ({probe_err})"

    return result
