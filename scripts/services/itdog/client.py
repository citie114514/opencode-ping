"""
ITDOG ping service adapter.
Note: ITDOG uses WebSocket to push results dynamically.
Python requests can only parse the initial HTML which may have limited data.
For full results, use a browser-based approach.
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils import PingNode, NodeStatus, classify_region, extract_province, extract_isp


ITDOG_BASE = "https://www.itdog.cn"


class ITDOGError(Exception):
    pass


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


def _parse_latency(text: str) -> Optional[float]:
    """Parse latency value from text like '84ms' or '超时'."""
    if not text or text in ("超时", "--", ""):
        return None
    text = text.replace("ms", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_node_row(row, target: str) -> Optional[PingNode]:
    """Parse a single node row from the HTML table."""
    try:
        node_id = row.get("node")
        if node_id:
            try:
                node_id = int(node_id)
            except ValueError:
                node_id = None

        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        node = PingNode(node_id=node_id, target=target, raw={})

        # Cell 0: location (e.g., "电信 湖北十堰")
        loc_text = cells[0].get_text(strip=True)
        node.node_name = loc_text
        node.province = extract_province(loc_text)
        node.isp = extract_isp(loc_text)
        node.region = classify_region(loc_text)
        node.city = loc_text

        # Cell 1: response IP
        node.resolved_ip = cells[1].get_text(strip=True)

        # Cell 2: IP geo/location
        ip_geo = cells[2].get_text(strip=True)

        # Cell 3: latency
        latency_text = cells[3].get_text(strip=True)
        node.latest_ms = _parse_latency(latency_text)

        # Determine status
        if node.latest_ms is None:
            node.status = NodeStatus.TIMEOUT.value
        else:
            node.status = NodeStatus.SUCCESS.value
            node.sent = 1
            node.received = 1
            node.loss_percent = 0.0

        node.raw = {
            "location": loc_text,
            "ip_geo": ip_geo,
            "latency_text": latency_text,
        }

        return node
    except (IndexError, ValueError):
        return None


def ping(host: str, count: int = 10, timeout: int = 60) -> List[PingNode]:
    """
    Ping a host using ITDOG service.
    
    Note: ITDOG dynamically loads data via WebSocket.
    This function parses the initial HTML response which may contain
    limited or cached data. For complete results, use a browser-based approach.
    
    Args:
        host: Target hostname or IP
        count: Not used (kept for interface consistency)
        timeout: Not used (kept for interface consistency)
    
    Returns:
        List of PingNode objects (may be incomplete)
    """
    session = _session()

    # Fetch the ping results page
    url = f"{ITDOG_BASE}/ping/{host}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    nodes = []

    # Try to find total node count from JavaScript variables
    total_nodes = 0
    timeout_nodes = 0
    
    scripts = soup.find_all("script")
    for script in scripts:
        text = script.string or ""
        m = re.search(r"check_node_num\s*=\s*(\d+)", text)
        if m:
            total_nodes = int(m.group(1))
        m = re.search(r"time_out_num\s*=\s*(\d+)", text)
        if m:
            timeout_nodes = int(m.group(1))

    # Find the results table
    table = soup.find("table", {"id": "simpletable"})
    if not table:
        raise ITDOGError("Could not find results table on ITDOG page")

    # Parse all node rows
    rows = table.find_all("tr", class_="node_tr")
    
    # If no node_tr rows found, try all tr rows
    if not rows:
        rows = table.find_all("tr")

    for row in rows:
        node = _parse_node_row(row, host)
        if node:
            nodes.append(node)

    # Add metadata note if we got fewer nodes than expected
    if total_nodes > 0 and len(nodes) < total_nodes:
        # Store the expected count in the first node's raw data
        if nodes:
            nodes[0].raw["expected_total"] = total_nodes
            nodes[0].raw["actual_returned"] = len(nodes)

    return nodes
