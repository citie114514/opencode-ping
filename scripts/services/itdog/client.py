"""
ITDOG ping service adapter using Playwright CLI (headless browser).

Uses the `playwright cli` command (the CLI front-end of Playwright's MCP
browser driver) to drive a headless Chromium. Each command is a separate
subprocess call against a persistent daemon session, so a fresh browser is
opened for each ping, driven through the ITDOG form flow, then closed.
"""

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import PingNode, NodeStatus, classify_region, extract_province, extract_isp  # noqa: E402


ITDOG_BASE = "https://www.itdog.cn"
DEFAULT_TIMEOUT = 60  # seconds

# Playwright CLI executable (falls back to full path if not on PATH)
PLAYWRIGHT_CLI = os.environ.get("PLAYWRIGHT_CLI", "playwright")


class ITDOGError(Exception):
    pass


def _run_cli(args, timeout=180):
    """Run a `playwright cli` subcommand and return its raw stdout.

    Args:
        args: list of CLI arguments after the `cli` subcommand, e.g.
            ["goto", "https://..."]
        timeout: subprocess timeout in seconds.
    Returns:
        stripped stdout text (raw value if --raw was used).
    """
    cmd = [PLAYWRIGHT_CLI, "cli"] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise ITDOGError(
            f"playwright cli {' '.join(args[:2])} failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _eval_json(js):
    """Evaluate JS on the page and return the parsed JSON value.

    The CLI's `--raw` output is itself a JSON-encoded string, so we decode
    twice: first the outer JSON string literal, then the inner JSON payload.
    """
    out = _run_cli(["eval", js, "--raw"])
    if not out:
        return None
    try:
        return json.loads(json.loads(out))
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_latency(text):
    """Parse latency value from text like '84ms' or '<1ms' or '超时'."""
    if not text or text in ("超时", "--", ""):
        return None
    text = text.strip()
    if text.startswith("<"):
        try:
            return float(text[1:].replace("ms", "")) * 0.1
        except ValueError:
            return 0.1
    text = text.replace("ms", "")
    try:
        return float(text)
    except ValueError:
        return None


def _row_to_node(row, host):
    """Convert a raw table row dict from the page to a PingNode."""
    cells = row.get("cells") or []
    if len(cells) < 4:
        return None

    loc_text = (cells[0] or "").strip()
    ip_text = (cells[1] or "").strip()
    geo_text = (cells[2] or "").strip()
    latency_text = (cells[3] or "").strip()

    node = PingNode(target=host, raw={})
    node.node_name = loc_text
    node.province = extract_province(loc_text)
    node.isp = extract_isp(loc_text)
    node.region = classify_region(loc_text)
    node.city = loc_text
    node.resolved_ip = ip_text
    node.raw = {"node_id_raw": row.get("id"), "ip_geo": geo_text, "latency_text": latency_text}

    node.latest_ms = _parse_latency(latency_text)
    if node.latest_ms is None:
        node.status = NodeStatus.TIMEOUT.value
    else:
        node.status = NodeStatus.SUCCESS.value
        node.sent = 1
        node.received = 1
        node.loss_percent = 0.0
    return node


def _extract_rows(js_rows):
    """Turn a JS array of {id, cells} dicts into PingNode list."""
    nodes = []
    for row in js_rows or []:
        try:
            node = _row_to_node(row, "")
            if node is not None:
                nodes.append(node)
        except Exception:
            continue
    return nodes


def _wait_for_results():
    """Poll until all ITDOG node rows are rendered, or timeout expires."""
    deadline = time.time() + DEFAULT_TIMEOUT
    last_count = 0
    stable = 0
    while time.time() < deadline:
        meta = _eval_json("() => JSON.stringify({num: window.check_node_num||0, timeout: window.time_out_num||0})") or {}
        expected = int(meta.get("num") or 0)
        rows = _eval_json("() => JSON.stringify([...document.querySelectorAll('tr.node_tr')].map(r => ({id: r.getAttribute('node'), cells: [...r.querySelectorAll('td')].map(c => c.innerText)})))")
        count = len(rows or [])
        if expected and count >= expected:
            return expected, (meta.get("timeout") or 0), rows or []
        if count == last_count and count > 0:
            stable += 1
            if stable >= 3:
                return expected, (meta.get("timeout") or 0), rows or []
        else:
            stable = 0
        last_count = count
        time.sleep(2)
    return expected if 'expected' in dir() else 0, 0, rows or []



def _build_final_rows(rows, host):
    """Attach target host to every parsed node and return the list."""
    nodes = _extract_rows(rows)
    for n in nodes:
        n.target = host
    return nodes


def ping(host, count=10, timeout=DEFAULT_TIMEOUT):
    """
    Ping a host using ITDOG service via Playwright CLI (headless).

    Args:
        host: Target hostname or IP
        count: Not used (kept for interface consistency)
        timeout: Timeout in seconds (default: 60)

    Returns:
        List of PingNode objects
    """
    global DEFAULT_TIMEOUT
    if timeout > 0:
        DEFAULT_TIMEOUT = timeout

    nodes = []
    expected_total = 0
    timeout_count = 0

    try:
        _open_browser()
        expected_total, timeout_count, rows = _run_itdog_flow(host)
        nodes = _build_final_rows(rows, host)
    except Exception as e:
        raise ITDOGError(f"ITDOG request failed: {e}")
    finally:
        _close_browser()

    # Store metadata
    if nodes:
        nodes[0].raw["expected_total"] = expected_total
        nodes[0].raw["actual_returned"] = len(nodes)
        nodes[0].raw["timeout_count"] = timeout_count

    return nodes



def _open_browser():
    """Ensure a fresh headless browser session is running."""
    _run_cli(["kill-all"], timeout=30)
    _run_cli(["open"], timeout=60)


def _close_browser():
    """Close the browser session."""
    try:
        _run_cli(["close"], timeout=30)
    except ITDOGError:
        pass


def _run_itdog_flow(host):
    """Drive ITDOG form flow and return (expected, timeout_count, rows)."""
    _run_cli(["goto", f"{ITDOG_BASE}/ping/", "--json"], timeout=60)
    time.sleep(2)

    _run_cli(["fill", "#host", host], timeout=30)
    time.sleep(1)

    _run_cli(["click", "button:has-text('单次测试')"], timeout=30)

    return _wait_for_results()
