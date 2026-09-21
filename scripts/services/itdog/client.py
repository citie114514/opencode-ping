"""
ITDOG service adapter using the Playwright CLI (headless browser).

Uses the `playwright cli` command (the CLI front-end of Playwright's browser
driver) to drive a headless Chromium. Each command is a separate subprocess
call against a persistent daemon session, so a fresh browser is opened for
each test, driven through the ITDOG form flow, then closed.

Supported ITDOG tools (all share the same page framework):
    * ping       -> /ping/        ICMP ping (IPv4)
    * ping_ipv6  -> /ping_ipv6/   dedicated IPv6 ICMP ping tool
    * tcping     -> /tcping/      multi-location TCP port test
    * http       -> /http/        multi-location website speed test
    * dns        -> /dns/         multi-location DNS lookup
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import PingNode, NodeStatus, classify_region, extract_province, extract_isp  # noqa: E402
from services.browser import (  # noqa: E402
    BrowserError,
    close_browser as _close_browser,
    eval_json as _eval_json,
    host_for_url,
    open_browser as _open_browser,
    run_cli as _run_cli,
)


ITDOG_BASE = "https://www.itdog.cn"
DEFAULT_TIMEOUT = 60  # seconds

# tool -> (page path, start-button text)
TOOLS = {
    "ping": ("/ping/", "单次测试"),
    "ping6": ("/ping_ipv6/", "单次测试"),
    "tcping": ("/tcping/", "单次测试"),
    "http": ("/http/", "快速测试"),
    "dns": ("/dns/", "开始测试"),
}


class ITDOGError(BrowserError):
    pass


# ──────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────

def _parse_latency(text):
    """Parse a latency value from text like '84ms', '<1ms', '超时' or '--'."""
    if not text or text.strip() in ("超时", "--", "", "-"):
        return None
    text = text.strip()
    if text.startswith("<"):
        try:
            return float(text[1:].replace("ms", "").strip()) * 0.1
        except ValueError:
            return 0.1
    text = text.replace("ms", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_seconds(text):
    """Parse a duration like '0.201s' (or '201ms') into milliseconds."""
    if not text:
        return None
    text = text.strip()
    if text in ("--", "-", ""):
        return None
    try:
        if text.endswith("ms"):
            return float(text[:-2])
        if text.endswith("s"):
            return float(text[:-1]) * 1000
        return float(text)
    except ValueError:
        return None


def _fill_location(node, text):
    node.node_name = text
    node.city = text
    node.province = extract_province(text)
    node.isp = extract_isp(text)
    node.region = classify_region(text)


def _success_or_timeout(node, ms):
    if ms is None:
        node.status = NodeStatus.TIMEOUT.value
    else:
        node.status = NodeStatus.SUCCESS.value
        node.sent = 1
        node.received = 1
        node.loss_percent = 0.0


def _parse_ping_rows(rows, host, ipv6=False):
    """Parse the 5-column ping/tcping table: loc | ip | geo | latency | ad."""
    nodes = []
    for row in rows or []:
        cells = row.get("cells") or []
        if len(cells) < 4:
            continue
        loc = (cells[0] or "").strip()
        ip = (cells[1] or "").strip()
        geo = (cells[2] or "").strip()
        latency = (cells[3] or "").strip()

        node = PingNode(target=host)
        _fill_location(node, loc)
        node.resolved_ip = ip
        node.raw = {
            "node_id": row.get("id"),
            "ip_geo": geo,
            "latency_text": latency,
            "ipv6": ipv6,
        }
        node.latest_ms = _parse_latency(latency)
        _success_or_timeout(node, node.latest_ms)
        nodes.append(node)
    return nodes


def _parse_http_rows(rows, host):
    """Parse the 11-column website test table.

    loc | ip | geo | status | total | dns | connect | download | redirect | head | ad
    """
    nodes = []
    for row in rows or []:
        cells = row.get("cells") or []
        if len(cells) < 4:
            continue
        loc = (cells[0] or "").strip()
        ip = (cells[1] or "").strip()
        geo = (cells[2] or "").strip()
        status = (cells[3] or "").strip()
        total_t = (cells[4] or "").strip() if len(cells) > 4 else ""
        dns_t = (cells[5] or "").strip() if len(cells) > 5 else ""
        conn_t = (cells[6] or "").strip() if len(cells) > 6 else ""
        dl_t = (cells[7] or "").strip() if len(cells) > 7 else ""

        node = PingNode(target=host)
        _fill_location(node, loc)
        node.resolved_ip = ip
        node.latest_ms = _parse_seconds(total_t)
        _success_or_timeout(node, node.latest_ms)
        node.raw = {
            "node_id": row.get("id"),
            "ip_geo": geo,
            "http_status": status,
            "total_text": total_t,
            "dns_ms": _parse_seconds(dns_t),
            "connect_ms": _parse_seconds(conn_t),
            "download_ms": _parse_seconds(dl_t),
        }
        nodes.append(node)
    return nodes


def _parse_dns_rows(rows, host):
    """Parse the 9-column DNS table.

    loc | target | type | answers | count | detail | ms | server | ad
    """
    nodes = []
    for row in rows or []:
        cells = row.get("cells") or []
        if len(cells) < 4:
            continue
        loc = (cells[0] or "").strip()
        target = (cells[1] or "").strip()
        rtype = (cells[2] or "").strip()
        answers_raw = (cells[3] or "").strip()
        count = (cells[4] or "").strip() if len(cells) > 4 else ""
        ms_t = (cells[6] or "").strip() if len(cells) > 6 else ""
        server = (cells[7] or "").strip() if len(cells) > 7 else ""

        answers = [a.strip() for a in answers_raw.split("\n") if a.strip()]
        node = PingNode(target=host)
        _fill_location(node, loc)
        node.resolved_ip = answers[0] if answers else ""
        node.latest_ms = _parse_latency(ms_t)
        _success_or_timeout(node, node.latest_ms)
        node.raw = {
            "node_id": row.get("id"),
            "target": target,
            "type": rtype,
            "answers": answers,
            "answer_count": count,
            "dns_server": server,
        }
        nodes.append(node)
    return nodes


_PARSERS = {
    "ping": lambda rows, host: _parse_ping_rows(rows, host, ipv6=False),
    "ping6": lambda rows, host: _parse_ping_rows(rows, host, ipv6=True),
    "tcping": lambda rows, host: _parse_ping_rows(rows, host, ipv6=False),
    "http": _parse_http_rows,
    "dns": _parse_dns_rows,
}


# ──────────────────────────────────────────────
# Flow
# ──────────────────────────────────────────────

def _wait_for_results(timeout=DEFAULT_TIMEOUT):
    """Poll until all ITDOG node rows are rendered, or timeout expires."""
    deadline = time.time() + timeout
    last_count = 0
    stable = 0
    expected = 0
    timeout_count = 0
    rows = []
    while time.time() < deadline:
        meta = _eval_json(
            "() => JSON.stringify({num: window.check_node_num||0, "
            "timeout: window.time_out_num||0})"
        ) or {}
        expected = int(meta.get("num") or 0)
        timeout_count = int(meta.get("timeout") or 0)
        rows = _eval_json(
            "() => JSON.stringify([...document.querySelectorAll('tr.node_tr')]"
            ".map(r => ({id: r.getAttribute('node'), cells: [...r.querySelectorAll('td')]"
            ".map(c => c.innerText)})))"
        )
        count = len(rows or [])
        if expected and count >= expected:
            break
        if count == last_count and count > 0:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        last_count = count
        time.sleep(2)
    return expected, timeout_count, rows or []


def _run_tool(tool, host, timeout=DEFAULT_TIMEOUT, dtype=None):
    """Drive one ITDOG tool and return the parsed node list."""
    if tool not in TOOLS:
        raise ITDOGError(f"unknown ITDOG tool: {tool}")
    path, button = TOOLS[tool]

    nodes = []
    expected = timeout_count = 0
    try:
        _open_browser()
        _run_cli(["goto", f"{ITDOG_BASE}{path}", "--json"], timeout=60)
        time.sleep(2)

        _run_cli(["fill", "#host", host], timeout=30)
        time.sleep(1)

        if tool == "dns" and dtype and dtype.upper() != "A":
            _run_cli(["click", "#dns_type_button"], timeout=30)
            time.sleep(0.5)
            _run_cli(["click", f".dns_type_menu a:has-text('{dtype.upper()}')"], timeout=30)
            time.sleep(0.5)

        _run_cli(["click", f"button:has-text('{button}')"], timeout=30)

        expected, timeout_count, rows = _wait_for_results(timeout=timeout)
        nodes = _PARSERS[tool](rows, host)
    except ITDOGError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ITDOGError(f"ITDOG {tool} request failed: {e}")
    finally:
        _close_browser()

    if nodes:
        nodes[0].raw["expected_total"] = expected
        nodes[0].raw["actual_returned"] = len(nodes)
        nodes[0].raw["timeout_count"] = timeout_count
    return nodes


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def ping(host, count=10, timeout=DEFAULT_TIMEOUT):
    """ICMP ping via ITDOG /ping/ (IPv4)."""
    return _run_tool("ping", host, timeout=timeout)


def ping_ipv6(host, count=10, timeout=DEFAULT_TIMEOUT):
    """Dedicated IPv6 ICMP ping via ITDOG /ping_ipv6/."""
    return _run_tool("ping6", host, timeout=timeout)


def tcping(host, port=80, count=10, timeout=DEFAULT_TIMEOUT):
    """Multi-location TCP port test via ITDOG /tcping/."""
    target = f"{host_for_url(host)}:{port}" if port else host
    return _run_tool("tcping", target, timeout=timeout)


def http(host, timeout=DEFAULT_TIMEOUT):
    """Multi-location website speed test via ITDOG /http/."""
    target = host if host.startswith(("http://", "https://")) else f"https://{host_for_url(host)}"
    return _run_tool("http", target, timeout=timeout)


def dns(host, rtype="A", timeout=DEFAULT_TIMEOUT):
    """Multi-location DNS lookup via ITDOG /dns/."""
    return _run_tool("dns", host, timeout=timeout, dtype=rtype)
