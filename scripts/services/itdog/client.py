"""
ITDOG ping client.
Uses HTML parsing to get results from ITDOG's ping page.
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


class CaptchaRequired(ITDOGError):
    pass


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


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
        if len(cells) < 9:
            return None

        node = PingNode(node_id=node_id, target=target, raw={})

        # Cell 0: location (e.g., "电信 辽宁大连")
        loc_text = cells[0].get_text(strip=True)
        node.node_name = loc_text
        node.province = extract_province(loc_text)
        node.isp = extract_isp(loc_text)
        node.region = classify_region(loc_text)
        node.city = loc_text

        # Cell 1: response IP
        node.resolved_ip = cells[1].get_text(strip=True)

        # Cell 2: IP geo location
        ip_geo = cells[2].get_text(strip=True)

        # Cell 3: loss percentage
        loss_text = cells[3].get_text(strip=True)
        if loss_text not in ("--", ""):
            try:
                node.loss_percent = float(loss_text.replace("%", ""))
            except ValueError:
                pass

        # Cell 4: sent count
        sent_text = cells[4].get_text(strip=True)
        if sent_text not in ("--", ""):
            try:
                node.sent = int(sent_text)
            except ValueError:
                pass

        # Cell 5: latest latency
        last_text = cells[5].get_text(strip=True)
        if last_text in ("超时", "--", ""):
            node.status = NodeStatus.TIMEOUT.value
        else:
            try:
                node.latest_ms = float(last_text)
                node.status = NodeStatus.SUCCESS.value
            except ValueError:
                node.status = NodeStatus.ERROR.value
                node.error = f"Unparseable latency: {last_text}"

        # Cell 6: best latency
        best_text = cells[6].get_text(strip=True)
        if best_text not in ("--", ""):
            try:
                node.min_ms = float(best_text)
            except ValueError:
                pass

        # Cell 7: worst latency
        worst_text = cells[7].get_text(strip=True)
        if worst_text not in ("--", ""):
            try:
                node.max_ms = float(worst_text)
            except ValueError:
                pass

        # Cell 8: average latency
        avg_text = cells[8].get_text(strip=True)
        if avg_text not in ("--", ""):
            try:
                node.avg_ms = float(avg_text)
            except ValueError:
                pass

        # Calculate received from sent and loss
        if node.sent > 0:
            if node.loss_percent >= 100:
                node.received = 0
            else:
                node.received = int(node.sent * (1 - node.loss_percent / 100))

        # Update status based on loss
        if node.status == NodeStatus.SUCCESS.value and node.loss_percent > 0:
            if node.loss_percent >= 100:
                node.status = NodeStatus.TIMEOUT.value
            else:
                node.status = NodeStatus.PARTIAL_LOSS.value

        return node
    except (IndexError, ValueError):
        return None


def ping(host: str, count: int = 10, timeout: int = 60) -> List[PingNode]:
    """
    Ping a host using ITDOG service.
    
    Args:
        host: Target hostname or IP
        count: Not used (kept for interface consistency)
        timeout: Not used (kept for interface consistency)
    
    Returns:
        List of PingNode objects
    """
    session = _session()

    # Check captcha first
    try:
        resp = session.get(
            f"{ITDOG_BASE}/verify/clicaptcha.php",
            params={"type": "ajax"},
            timeout=10,
        )
        data = resp.json()
        if data.get("type") == "verify":
            raise CaptchaRequired("CAPTCHA required by ITDOG")
        if data.get("type") == "error":
            raise ITDOGError(f"ITDOG error: {data.get('message', 'unknown')}")
    except (ValueError, KeyError):
        pass

    # Fetch the ping results page
    url = f"{ITDOG_BASE}/ping/{host}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    nodes = []

    # Find the results table
    table = soup.find("table", {"id": "simpletable"})
    if not table:
        raise ITDOGError("Could not find results table on ITDOG page")

    # Parse all node rows
    rows = table.find_all("tr", class_="node_tr")
    for row in rows:
        node = _parse_node_row(row, host)
        if node:
            nodes.append(node)

    # If no node_tr rows found, try all tr rows
    if not rows:
        all_rows = table.find_all("tr")
        for row in all_rows:
            cells = row.find_all("td")
            if len(cells) >= 9:
                node = _parse_node_row(row, host)
                if node:
                    nodes.append(node)

    return nodes
