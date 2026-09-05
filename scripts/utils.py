"""
Unified data models and utilities for the ping skill.
"""

import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"

LOSS_WARNING_DEFAULT = 0
LOSS_CRITICAL_DEFAULT = 5
LATENCY_WARNING_DEFAULT = 100
LATENCY_CRITICAL_DEFAULT = 200


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_LOSS = "partial_loss"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    UNKNOWN = "unknown"


class Mode(str, Enum):
    ALL = "all"
    LOCAL = "local"
    REMOTE = "remote"
    TCP = "tcp"
    WEB = "web"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PingNode:
    """Single monitoring point result."""
    node_id: Optional[int] = None
    node_name: str = ""
    region: str = "未知"
    province: str = ""
    city: str = ""
    isp: str = ""
    country: str = ""
    continent: str = ""
    target: str = ""
    resolved_ip: str = ""
    sent: int = 0
    received: int = 0
    loss_percent: float = 0.0
    latest_ms: Optional[float] = None
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    avg_ms: Optional[float] = None
    status: str = NodeStatus.UNKNOWN.value
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.status == NodeStatus.UNKNOWN.value:
            if self.error:
                self.status = NodeStatus.ERROR.value
            elif self.latest_ms is None and self.sent > 0 and self.received == 0:
                self.status = NodeStatus.TIMEOUT.value
            elif self.loss_percent == 100 and self.sent > 0:
                self.status = NodeStatus.TIMEOUT.value
            elif self.loss_percent > 0:
                self.status = NodeStatus.PARTIAL_LOSS.value
            elif self.latest_ms is not None:
                self.status = NodeStatus.SUCCESS.value


@dataclass
class LocalPingResult:
    """Result of a local ICMP ping."""
    target: str = ""
    resolved_ip: str = ""
    sent: int = 0
    received: int = 0
    loss_percent: float = 0.0
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    avg_ms: Optional[float] = None
    raw_output: str = ""
    error: str = ""


@dataclass
class TcpPingResult:
    """Result of a TCP connect test."""
    host: str = ""
    port: int = 443
    success: bool = False
    connect_ms: Optional[float] = None
    error: str = ""
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    avg_ms: Optional[float] = None


@dataclass
class WebTestResult:
    """Result of an HTTP/HTTPS test."""
    url: str = ""
    final_url: str = ""
    status_code: Optional[int] = None
    status_text: str = ""
    dns_ms: Optional[float] = None
    tcp_ms: Optional[float] = None
    tls_ms: Optional[float] = None
    ttfb_ms: Optional[float] = None
    total_ms: Optional[float] = None
    connect_ms: Optional[float] = None
    response_size: Optional[int] = None
    content_type: str = ""
    redirect_count: int = 0
    redirect_url: str = ""
    error: str = ""


@dataclass
class PingReport:
    """Complete ping report."""
    target: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    local_ping: Optional[LocalPingResult] = None
    remote_nodes: List[PingNode] = field(default_factory=list)
    tcp_ping: Optional[TcpPingResult] = None
    web_test: Optional[WebTestResult] = None
    regions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Region classification
# ---------------------------------------------------------------------------

_regions_data: Optional[Dict] = None


def _load_regions() -> Dict:
    global _regions_data
    if _regions_data is None:
        path = REFERENCES_DIR / "regions.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _regions_data = json.load(f)
        else:
            _regions_data = {"provinces": {}, "keywords": {}, "overseas_keywords": {}}
    return _regions_data


def classify_region(text: str) -> str:
    """Classify a location string into a region."""
    data = _load_regions()

    # Check domestic keywords first
    for region, keywords in data.get("keywords", {}).items():
        for kw in keywords:
            if kw in text:
                return region

    # Check overseas keywords
    for continent, keywords in data.get("overseas_keywords", {}).items():
        for kw in keywords:
            if kw in text:
                return "海外"

    # Check province mapping
    for province, region in data.get("provinces", {}).items():
        if province in text:
            return region

    return "未知"


def classify_continent(text: str) -> str:
    """Classify overseas location into continent."""
    data = _load_regions()
    for continent, keywords in data.get("overseas_keywords", {}).items():
        for kw in keywords:
            if kw in text:
                return continent
    return "未知"


def extract_province(text: str) -> str:
    """Extract province from location text."""
    data = _load_regions()
    for province in data.get("provinces", {}):
        if province in text:
            return province
    return ""


def extract_isp(text: str) -> str:
    """Extract ISP from location text."""
    for isp in ["电信", "联通", "移动", "广电"]:
        if isp in text:
            return isp
    return ""


# ---------------------------------------------------------------------------
# Host parsing
# ---------------------------------------------------------------------------

def parse_host(raw: str) -> Tuple[str, Optional[int], str]:
    """
    Parse host input, handling host:port, https://, etc.
    Returns (host, port, original_input).
    """
    original = raw.strip()
    host = original
    port = None

    # Strip protocol
    m = re.match(r'^(https?)://(.+)', host)
    if m:
        scheme = m.group(1)
        host = m.group(2)
        port = 443 if scheme == "https" else 80

    # Strip path
    if '/' in host:
        host = host.split('/')[0]

    # Parse port
    if ':' in host:
        parts = host.rsplit(':', 1)
        try:
            port = int(parts[1])
            host = parts[0]
        except ValueError:
            pass

    return host.lower(), port, original


def detect_url(raw: str) -> Optional[str]:
    """If input looks like a URL, return it normalized."""
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+(?:/\S*)?$', raw):
        return None
    return None


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def format_latency(ms: Optional[float]) -> str:
    if ms is None:
        return "-"
    if ms < 1:
        return "<1ms"
    return f"{ms:.0f}ms"


def format_loss(percent: float) -> str:
    if percent == 0:
        return "0%"
    return f"{percent:.0f}%"


def status_emoji(status: str) -> str:
    if status == NodeStatus.TIMEOUT.value:
        return "TIMEOUT"
    if status == NodeStatus.UNAVAILABLE.value:
        return "UNAVAILABLE"
    if status == NodeStatus.PARTIAL_LOSS.value:
        return "LOSS"
    if status == NodeStatus.ERROR.value:
        return "ERROR"
    if status == NodeStatus.SUCCESS.value:
        return ""
    return "?"


def is_warning(loss: float, avg_ms: Optional[float],
               loss_warn: float = LOSS_WARNING_DEFAULT,
               loss_crit: float = LOSS_CRITICAL_DEFAULT,
               lat_warn: float = LATENCY_WARNING_DEFAULT,
               lat_crit: float = LATENCY_CRITICAL_DEFAULT) -> Tuple[bool, bool, str]:
    """Returns (is_warn, is_crit, label)."""
    if loss >= loss_crit:
        return True, True, f"{loss:.0f}% LOSS"
    if loss >= loss_warn:
        return True, False, f"{loss:.0f}% LOSS"
    if avg_ms is not None and avg_ms >= lat_crit:
        return True, True, f"{avg_ms:.0f}ms HIGH LATENCY"
    if avg_ms is not None and avg_ms >= lat_warn:
        return True, False, f"{avg_ms:.0f}ms HIGH LATENCY"
    return False, False, ""
