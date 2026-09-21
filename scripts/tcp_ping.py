"""
TCP Ping using a raw socket connect.
Measures TCP handshake latency, with optional IPv6 support.
"""

import socket
import time
from typing import Optional

from utils import TcpPingResult


def _connect(host: str, port: int, timeout: int, family: int) -> socket.socket:
    """Open a TCP connection, trying each resolved address in turn."""
    infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    last_exc: Optional[Exception] = None
    for af, socktype, proto, _canon, sockaddr in infos:
        sock = socket.socket(af, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_exc = exc
            try:
                sock.close()
            except OSError:
                pass
    if last_exc is not None:
        raise last_exc
    raise OSError(f"could not resolve {host}")


def _resolve_ip(host: str, port: int, family: int) -> str:
    try:
        infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
        return infos[0][4][0] if infos else ""
    except OSError:
        return ""


def tcp_ping(host: str, port: int = 443, count: int = 5, timeout: int = 5,
             delay: float = 0.5, ipv6: bool = False) -> TcpPingResult:
    """
    TCP connect test to measure handshake latency.

    Args:
        host: Target hostname or IP
        port: Target port (default 443)
        count: Number of attempts
        timeout: Connection timeout in seconds
        delay: Delay between attempts in seconds
        ipv6: Force IPv6 (AF_INET6) when true.
    """
    family = socket.AF_INET6 if ipv6 else socket.AF_UNSPEC
    result = TcpPingResult(host=host, port=port, attempts=count, ipv6=ipv6)
    result.resolved_ip = _resolve_ip(host, port, family)
    latencies = []

    for i in range(count):
        try:
            start = time.monotonic()
            sock = _connect(host, port, timeout, family)
            elapsed = (time.monotonic() - start) * 1000  # ms
            sock.close()
            result.successes += 1
            latencies.append(elapsed)
        except socket.timeout:
            result.timeouts += 1
        except OSError as e:
            result.failures += 1
            if not result.error:
                result.error = str(e)
        except Exception as e:
            result.failures += 1
            if not result.error:
                result.error = str(e)

        if i < count - 1 and delay > 0:
            time.sleep(delay)

    if latencies:
        result.success = True
        result.connect_ms = latencies[0]
        result.min_ms = min(latencies)
        result.max_ms = max(latencies)
        result.avg_ms = sum(latencies) / len(latencies)
    elif result.timeouts == count:
        result.error = f"All {count} connection attempts timed out"
    elif result.failures == count and not result.error:
        result.error = f"All {count} connection attempts failed"

    return result
