"""
Local ICMP Ping using system ping command.
Windows: ping.exe, Linux/macOS: ping
"""

import platform
import re
import subprocess
import sys
from typing import Optional

from utils import LocalPingResult


def _ping_command() -> str:
    return "ping"


def _ping_args(target: str, count: int, timeout: int) -> list:
    system = platform.system().lower()
    if system == "windows":
        return [
            "ping.exe", "-n", str(count), "-w", str(timeout * 1000), target
        ]
    else:
        return [
            "ping", "-c", str(count), "-W", str(timeout), target
        ]


def _parse_windows_ping(output: str) -> Optional[dict]:
    """Parse Windows ping output."""
    # Format: "Packets: Sent = 10, Received = 10, Lost = 0 (0% loss),"
    # or:     "Sent = 10 Received = 10 Lost = 0 (0% loss)"
    m = re.search(r'Sent\s*=\s*(\d+).*?Received\s*=\s*(\d+).*?Lost\s*=\s*(\d+)', output)
    if not m:
        return None
    sent = int(m.group(1))
    received = int(m.group(2))
    lost = int(m.group(3))
    loss_pct = (lost / sent * 100) if sent > 0 else 0.0

    # Minimum = 15ms, Maximum = 24ms, Average = 18ms
    min_ms = max_ms = avg_ms = None
    m2 = re.search(r'Minimum\s*=\s*(\d+)ms.*Maximum\s*=\s*(\d+)ms.*Average\s*=\s*(\d+)ms', output, re.DOTALL)
    if m2:
        min_ms = float(m2.group(1))
        max_ms = float(m2.group(2))
        avg_ms = float(m2.group(3))

    return {
        "sent": sent,
        "received": received,
        "loss_percent": loss_pct,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "avg_ms": avg_ms,
    }


def _parse_linux_ping(output: str) -> Optional[dict]:
    """Parse Linux/macOS ping output."""
    # rtt min/avg/max/mdev = 15.123/18.456/24.789/2.345 ms
    m = re.search(r'rtt\s+min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms', output)
    if m:
        min_ms = float(m.group(1))
        avg_ms = float(m.group(2))
        max_ms = float(m.group(3))
    else:
        # macOS format: round-trip min/avg/max/stddev = 15.123/18.456/24.789/2.345 ms
        m = re.search(r'round-trip\s+min/avg/max/stddev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms', output)
        if m:
            min_ms = float(m.group(1))
            avg_ms = float(m.group(2))
            max_ms = float(m.group(3))
        else:
            min_ms = max_ms = avg_ms = None

    # 10 packets transmitted, 10 received, 0% packet loss
    m2 = re.search(r'(\d+)\s+(?:packets?\s+)?transmitted.*?(\d+)\s+received.*?([\d.]+)%\s+(?:packet\s+)?loss', output)
    if m2:
        sent = int(m2.group(1))
        received = int(m2.group(2))
        loss_pct = float(m2.group(3))
    else:
        # Try: 10 packets transmitted, 10 received, 0% packet loss, time 9012ms
        m3 = re.search(r'(\d+)\s+(?:packets?\s+)?transmitted.*?(\d+)\s+received', output)
        sent = int(m3.group(1)) if m3 else 0
        received = int(m3.group(2)) if m3 else 0
        loss_pct = ((sent - received) / sent * 100) if sent > 0 else 0.0

    return {
        "sent": sent,
        "received": received,
        "loss_percent": loss_pct,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "avg_ms": avg_ms,
    }


def _resolve_host(target: str) -> str:
    """Try to resolve hostname to IP for display."""
    import socket
    try:
        return socket.gethostbyname(target)
    except socket.gaierror:
        return target


def local_ping(target: str, count: int = 10, timeout: int = 5) -> LocalPingResult:
    """
    Execute a local ICMP ping and return structured result.
    """
    result = LocalPingResult(target=target)

    try:
        resolved = _resolve_host(target)
        result.resolved_ip = resolved
    except Exception:
        result.resolved_ip = target

    cmd = _ping_args(target, count, timeout)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout * count + 10,
            encoding="utf-8",
            errors="replace",
        )
        output = proc.stdout + "\n" + proc.stderr
        result.raw_output = output.strip()

        system = platform.system()
        if system == "Windows":
            parsed = _parse_windows_ping(output)
        else:
            parsed = _parse_linux_ping(output)

        if parsed:
            result.sent = parsed["sent"]
            result.received = parsed["received"]
            result.loss_percent = parsed["loss_percent"]
            result.min_ms = parsed["min_ms"]
            result.max_ms = parsed["max_ms"]
            result.avg_ms = parsed["avg_ms"]
        else:
            result.error = "Failed to parse ping output"

    except FileNotFoundError:
        result.error = "ping command not found"
    except subprocess.TimeoutExpired:
        result.error = "ping command timed out"
    except Exception as e:
        result.error = str(e)

    return result
