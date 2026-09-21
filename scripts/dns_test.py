"""
Local DNS resolution test.

Resolves A / AAAA / CNAME / MX / NS / TXT / SOA / PTR records and measures
resolution time. Uses dnspython when available, and always falls back to
socket.getaddrinfo for A/AAAA lookups so the basic test works with only the
standard library.
"""

import socket
import time
from typing import List, Optional

from utils import DnsTestResult

try:  # optional dependency
    import dns.exception
    import dns.resolver

    _HAVE_DNSPYTHON = True
except ImportError:  # pragma: no cover - depends on environment
    _HAVE_DNSPYTHON = False

SUPPORTED_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR", "CAA"]


def _new_resolver(server: Optional[str], timeout: int):
    resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout = timeout
    resolver.lifetime = timeout
    if server:
        resolver.nameservers = [server]
    return resolver


def _socket_lookup(host: str, family: int) -> List[str]:
    """Resolve A/AAAA using the system resolver. Returns sorted unique addresses."""
    infos = socket.getaddrinfo(host, None, family, socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _rdata_to_str(rtype: str, rdata) -> str:
    """Convert a dnspython rdata object to a readable string."""
    if rtype == "MX":
        return f"{rdata.preference} {str(rdata.exchange).rstrip('.')}"
    if rtype == "TXT":
        try:
            return "".join(
                part.decode("utf-8", "replace") if isinstance(part, bytes) else str(part)
                for part in rdata.strings
            )
        except AttributeError:
            return str(rdata).strip('"')
    if rtype == "SOA":
        return (
            f"{str(rdata.mname).rstrip('.')} "
            f"{str(rdata.rname).rstrip('.')} "
            f"serial={rdata.serial}"
        )
    return str(rdata).rstrip(".")


def _cname_chain(resolver, host: str, limit: int = 10) -> List[str]:
    """Follow the CNAME chain for a hostname (best effort)."""
    chain: List[str] = []
    name = host
    for _ in range(limit):
        try:
            answer = resolver.resolve(name, "CNAME", raise_on_no_answer=True)
        except Exception:
            break
        target = str(answer[0].target).rstrip(".")
        if not target:
            break
        chain.append(target)
        name = target
    return chain


def dns_test(host: str, rtype: str = "A", server: Optional[str] = None,
             timeout: int = 5, ipv6: bool = False) -> DnsTestResult:
    """
    Run a local DNS resolution test.

    Args:
        host: Target hostname or IP.
        rtype: Record type (A, AAAA, CNAME, MX, NS, TXT, SOA, PTR, CAA).
        server: Optional custom nameserver (e.g. "8.8.8.8").
        timeout: Query timeout in seconds.
        ipv6: Hint that AAAA resolution is desired when rtype is not explicit.
    """
    rtype = (rtype or "A").upper()
    if ipv6 and rtype == "A":
        rtype = "AAAA"
    result = DnsTestResult(host=host, rtype=rtype, server=server or "", ipv6=ipv6)
    start = time.monotonic()

    # Fast path / fallback: A and AAAA via the system resolver.
    if rtype in ("A", "AAAA"):
        family = socket.AF_INET6 if rtype == "AAAA" else socket.AF_INET
        try:
            result.records[rtype] = _socket_lookup(host, family)
        except socket.gaierror as exc:
            result.records.setdefault(rtype, [])
            if not _HAVE_DNSPYTHON:
                result.error = f"DNS resolution failed: {exc}"
        result.resolve_ms = round((time.monotonic() - start) * 1000, 1)

    if _HAVE_DNSPYTHON:
        try:
            resolver = _new_resolver(server, timeout)
            answer = resolver.resolve(host, rtype, raise_on_no_answer=False)
            values = [_rdata_to_str(rtype, rdata) for rdata in answer]
            if values or not result.records.get(rtype):
                result.records[rtype] = values
            if rtype in ("A", "AAAA"):
                chain = _cname_chain(resolver, host)
                if chain:
                    result.cname_chain = chain
                    result.records.setdefault("CNAME", chain)
            if result.resolve_ms is None:
                result.resolve_ms = round((time.monotonic() - start) * 1000, 1)
        except Exception as exc:  # noqa: BLE001 - report any resolver failure
            if not result.answers and not result.error:
                result.error = f"DNS query failed: {exc}"
    else:
        if rtype not in ("A", "AAAA"):
            result.error = "dnspython is required for non-A/AAAA record queries"

    if result.resolve_ms is None:
        result.resolve_ms = round((time.monotonic() - start) * 1000, 1)
    return result
