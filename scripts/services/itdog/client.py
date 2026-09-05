"""
ITDOG ping service adapter using Playwright headless browser.
"""

import re
from typing import List, Optional

from playwright.sync_api import sync_playwright

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils import PingNode, NodeStatus, classify_region, extract_province, extract_isp


ITDOG_BASE = "https://www.itdog.cn"
DEFAULT_TIMEOUT = 60  # seconds


class ITDOGError(Exception):
    pass


def _parse_latency(text: str) -> Optional[float]:
    """Parse latency value from text like '84ms' or '<1ms' or '超时'."""
    if not text or text in ("超时", "--", ""):
        return None
    text = text.strip()
    
    # Handle "<1ms" format
    if text.startswith("<"):
        try:
            return float(text[1:].replace("ms", "")) * 0.1
        except ValueError:
            return 0.1
    
    # Remove "ms" suffix
    text = text.replace("ms", "")
    try:
        return float(text)
    except ValueError:
        return None


def ping(host: str, count: int = 10, timeout: int = DEFAULT_TIMEOUT) -> List[PingNode]:
    """
    Ping a host using ITDOG service via Playwright headless browser.
    
    Args:
        host: Target hostname or IP
        count: Not used (kept for interface consistency)
        timeout: Timeout in seconds (default: 60)
    
    Returns:
        List of PingNode objects
    """
    nodes = []
    expected_total = 0
    timeout_count = 0
    
    timeout_ms = timeout * 1000
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        
        try:
            # Step 1: Navigate to main ping page
            page.goto(f"{ITDOG_BASE}/ping/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            # Step 2: Fill in the host
            page.fill("#host", host)
            page.wait_for_timeout(1000)
            
            # Step 3: Click the "单次测试" button
            buttons = page.query_selector_all("button")
            for btn in buttons:
                text = btn.inner_text()
                if "单次" in text or "测试" in text:
                    btn.click()
                    break
            
            # Step 4: Wait for results to load
            page.wait_for_timeout(10000)
            
            # Step 5: Get metadata from JavaScript
            expected_total = page.evaluate("() => window.check_node_num || 0")
            timeout_count = page.evaluate("() => window.time_out_num || 0")
            
            # Step 6: Wait for table rows to appear
            page.wait_for_selector("tr.node_tr", timeout=30000)
            
            # Step 7: Get all node rows
            rows = page.query_selector_all("tr.node_tr")
            
            # Step 8: Parse each row
            for row in rows:
                try:
                    node_id = row.get_attribute("node")
                    if node_id:
                        try:
                            node_id = int(node_id)
                        except ValueError:
                            node_id = None
                    
                    cells = row.query_selector_all("td")
                    if len(cells) < 4:
                        continue
                    
                    loc_text = cells[0].inner_text().strip()
                    ip_text = cells[1].inner_text().strip()
                    geo_text = cells[2].inner_text().strip()
                    latency_text = cells[3].inner_text().strip()
                    
                    node = PingNode(node_id=node_id, target=host, raw={})
                    node.node_name = loc_text
                    node.province = extract_province(loc_text)
                    node.isp = extract_isp(loc_text)
                    node.region = classify_region(loc_text)
                    node.city = loc_text
                    node.resolved_ip = ip_text
                    node.raw = {
                        "location": loc_text,
                        "ip_geo": geo_text,
                        "latency_text": latency_text,
                    }
                    
                    node.latest_ms = _parse_latency(latency_text)
                    
                    if node.latest_ms is None:
                        node.status = NodeStatus.TIMEOUT.value
                    else:
                        node.status = NodeStatus.SUCCESS.value
                        node.sent = 1
                        node.received = 1
                        node.loss_percent = 0.0
                    
                    nodes.append(node)
                except Exception:
                    continue
            
            # If we got fewer nodes than expected, wait a bit more
            if len(nodes) < expected_total:
                page.wait_for_timeout(5000)
                rows = page.query_selector_all("tr.node_tr")
                current_ids = {n.node_id for n in nodes if n.node_id}
                for row in rows:
                    try:
                        node_id = row.get_attribute("node")
                        if node_id and node_id not in current_ids:
                            try:
                                node_id = int(node_id)
                            except ValueError:
                                continue
                            
                            cells = row.query_selector_all("td")
                            if len(cells) < 4:
                                continue
                            
                            loc_text = cells[0].inner_text().strip()
                            ip_text = cells[1].inner_text().strip()
                            geo_text = cells[2].inner_text().strip()
                            latency_text = cells[3].inner_text().strip()
                            
                            node = PingNode(node_id=node_id, target=host, raw={})
                            node.node_name = loc_text
                            node.province = extract_province(loc_text)
                            node.isp = extract_isp(loc_text)
                            node.region = classify_region(loc_text)
                            node.city = loc_text
                            node.resolved_ip = ip_text
                            node.raw = {
                                "location": loc_text,
                                "ip_geo": geo_text,
                                "latency_text": latency_text,
                            }
                            
                            node.latest_ms = _parse_latency(latency_text)
                            
                            if node.latest_ms is None:
                                node.status = NodeStatus.TIMEOUT.value
                            else:
                                node.status = NodeStatus.SUCCESS.value
                                node.sent = 1
                                node.received = 1
                                node.loss_percent = 0.0
                            
                            nodes.append(node)
                            current_ids.add(node_id)
                    except Exception:
                        continue
                        
        except Exception as e:
            raise ITDOGError(f"ITDOG request failed: {e}")
        finally:
            browser.close()
    
    # Store metadata
    if nodes:
        nodes[0].raw["expected_total"] = expected_total
        nodes[0].raw["actual_returned"] = len(nodes)
        nodes[0].raw["timeout_count"] = timeout_count
    
    return nodes
