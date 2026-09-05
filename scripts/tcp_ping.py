"""
TCP Ping using socket.create_connection().
Measures TCP handshake latency.
"""

import socket
import time
from typing import Optional

from utils import TcpPingResult


def tcp_ping(host: str, port: int = 443, count: int = 5, timeout: int = 5,
             delay: float = 0.5) -> TcpPingResult:
    """
    TCP connect test to measure handshake latency.
    
    Args:
        host: Target hostname or IP
        port: Target port (default 443)
        count: Number of attempts
        timeout: Connection timeout in seconds
        delay: Delay between attempts in seconds
    """
    result = TcpPingResult(host=host, port=port, attempts=count)
    latencies = []

    for i in range(count):
        try:
            start = time.monotonic()
            sock = socket.create_connection((host, port), timeout=timeout)
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
