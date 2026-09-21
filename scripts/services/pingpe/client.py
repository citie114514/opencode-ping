"""
ping.pe multi-location adapter using the Playwright CLI (headless browser).

ping.pe exposes command-specific hostnames that map a subject to a command:

    ping.pe/SUBJECT          -> ICMP ping (+ mtr)
    ping6.ping.pe/SUBJECT    -> IPv6 ICMP ping
    tcp.ping.pe/SUBJECT:PORT -> TCP port check
    tcp6.ping.pe/SUBJECT:PORT-> IPv6 TCP port check
    dig.ping.pe/SUBJECT:TYPE -> DNS lookup

Results are rendered into an HTML table after the page's own JS/WebSocket
client finishes, so we drive the page and read the table from the DOM.
"""

import os
import re
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


DEFAULT_TIMEOUT = 90  # ping.pe needs "about a minute" to collect results

# Extract the results table (header + rows) as a 2D array of cell texts.
_EXTRACT_JS = (
    "() => {"
    "  const tables = [...document.querySelectorAll('table')];"
    "  for (const t of tables) {"
    "    const trs = [...t.querySelectorAll('tr')];"
    "    const hi = trs.findIndex(r => {"
    "      const s = r.innerText;"
    "      return s.includes('ISP') && (s.includes('Geo') || s.includes('Location'));"
    "    });"
    "    if (hi >= 0) {"
    "      return JSON.stringify(trs.slice(hi)"
    "        .map(r => [...r.querySelectorAll('td,th')].map(c => c.innerText.trim())));"
    "    }"
    "  }"
    "  return JSON.stringify(null);"
    "}"
)

# Detect ping.pe's inline error notice (e.g. an unresolvable subject).
_NOTICE_JS = (
    "() => {"
    "  const m = document.body.innerText.match("
    "    /Unable to (?:resolve|connect)[^\\n]*/i);"
    "  return JSON.stringify(m ? m[0].trim() : null);"
    "}"
)

_MS_RE = re.compile(r"([\d.]+)\s*ms")


class PingPeError(BrowserError):
    pass


def _to_float(text):
    if text is None:
        return None
    text = str(text).strip()
    if text in ("", "-", "--", "N/A"):
        return None
    try:
        return float(text.replace("ms", "").strip())
    except ValueError:
        return None


def _parse_loss(text):
    if not text:
        return None
    m = re.search(r"([\d.]+)", text)
    return float(m.group(1)) if m else None


def _fill_location(node, location, isp):
    node.node_name = location
    node.city = location
    node.isp = isp or extract_isp(location)
    node.province = extract_province(location)
    node.region = classify_region(location)


def _kind_from_header(header):
    joined = " ".join(h.lower() for h in header)
    if "tcp port check" in joined:
        return "tcp"
    if "dig response" in joined:
        return "dig"
    return "ping"


def _parse_rows(rows, host, ipv6=False):
    """Parse the ping.pe results table into a list of PingNode."""
    if not rows:
        return []
    header = rows[0]
    kind = _kind_from_header(header)
    nodes = []
    for cells in rows[1:]:
        node = _parse_row(kind, cells, host, ipv6)
        if node is not None:
            nodes.append(node)
    return nodes


def _parse_row(kind, cells, host, ipv6):
    if kind == "tcp":
        if len(cells) < 3:
            return None
        location, isp, result = cells[0], cells[1], cells[2]
        if not location:
            return None
        node = PingNode(target=host)
        _fill_location(node, location, isp)
        node.raw = {"result": result, "ipv6": ipv6, "tool": "tcp"}
        m = _MS_RE.search(result)
        node.latest_ms = float(m.group(1)) if m else None
        ok = "successful" in result.lower()
        if ok and node.latest_ms is not None:
            node.status = NodeStatus.SUCCESS.value
            node.sent = node.received = 1
        else:
            node.status = NodeStatus.TIMEOUT.value
        ip_m = re.search(r"Connection to ([^\s:]+)", result)
        if ip_m:
            node.resolved_ip = ip_m.group(1)
        return node

    if kind == "dig":
        if len(cells) < 3:
            return None
        location, isp, response = cells[0], cells[1], cells[2]
        if not location:
            return None
        node = PingNode(target=host)
        _fill_location(node, location, isp)
        m = _MS_RE.search(response)
        node.latest_ms = float(m.group(1)) if m else None
        clean = _MS_RE.sub("", response).strip()
        answers = [ln.strip().rstrip(".") for ln in clean.split("\n") if ln.strip()]
        node.raw = {
            "tool": "dig",
            "ipv6": ipv6,
            "response": clean,
            "answers": answers,
        }
        if node.latest_ms is not None:
            node.status = NodeStatus.SUCCESS.value
            node.sent = node.received = 1
        elif response:
            node.status = NodeStatus.SUCCESS.value
            node.sent = node.received = 1
        else:
            node.status = NodeStatus.TIMEOUT.value
        return node

    # ping / ping6
    if len(cells) < 8:
        return None
    location, isp, loss, sent, last, avg, best, worst = cells[:8]
    if not location:
        return None
    node = PingNode(target=host)
    _fill_location(node, location, isp)
    node.loss_percent = _parse_loss(loss) or 0.0
    try:
        node.sent = int(sent) if sent else 0
    except ValueError:
        node.sent = 0
    node.received = node.sent - round(node.sent * node.loss_percent / 100)
    node.latest_ms = _to_float(last)
    node.avg_ms = _to_float(avg)
    node.min_ms = _to_float(best)
    node.max_ms = _to_float(worst)
    node.raw = {"tool": "ping6" if ipv6 else "ping", "ipv6": ipv6, "loss_text": loss}
    if node.latest_ms is not None:
        node.status = NodeStatus.SUCCESS.value
    elif node.sent and node.loss_percent >= 100:
        node.status = NodeStatus.TIMEOUT.value
    elif node.sent:
        node.status = NodeStatus.PARTIAL_LOSS.value
    else:
        node.status = NodeStatus.TIMEOUT.value
    return node


def _count_ready(rows):
    if not rows or len(rows) < 2:
        return 0
    kind = _kind_from_header(rows[0])
    ready = 0
    for cells in rows[1:]:
        if kind == "tcp":
            if len(cells) >= 3 and cells[0] and cells[2]:
                ready += 1
        elif kind == "dig":
            if len(cells) >= 3 and cells[0] and cells[2]:
                ready += 1
        else:
            if len(cells) >= 8 and cells[0] and (cells[4] or cells[3]):
                ready += 1
    return ready


def _wait_results(timeout=DEFAULT_TIMEOUT):
    deadline = time.time() + timeout
    last_ready = -1
    stable = 0
    rows = []
    while time.time() < deadline:
        rows = _eval_json(_EXTRACT_JS) or []
        ready = _count_ready(rows)
        if ready > 0 and ready == last_ready:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        last_ready = ready
        time.sleep(3)
    return rows


def _run(url, host, ipv6=False, timeout=DEFAULT_TIMEOUT):
    nodes = []
    try:
        _open_browser()
        last_err = None
        for _attempt in range(2):
            try:
                _run_cli(["goto", url, "--json"], timeout=90)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(2)
        if last_err is not None:
            raise last_err
        time.sleep(3)
        notice = _eval_json(_NOTICE_JS)
        if notice:
            raise PingPeError(f"ping.pe: {notice}")
        rows = _wait_results(timeout=timeout)
        nodes = _parse_rows(rows, host, ipv6=ipv6)
    except PingPeError:
        raise
    except Exception as e:  # noqa: BLE001
        raise PingPeError(f"ping.pe request failed: {e}")
    finally:
        _close_browser()
    return nodes


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def ping(host, timeout=DEFAULT_TIMEOUT):
    """Global multi-location ICMP ping (IPv4)."""
    return _run(f"https://ping.pe/{host_for_url(host)}", host, timeout=timeout)


def ping_ipv6(host, timeout=DEFAULT_TIMEOUT):
    """Global multi-location IPv6 ICMP ping."""
    return _run(f"https://ping6.ping.pe/{host_for_url(host)}", host, ipv6=True, timeout=timeout)


def tcp(host, port=80, timeout=DEFAULT_TIMEOUT):
    """Global multi-location TCP port check (IPv4)."""
    return _run(f"https://tcp.ping.pe/{host_for_url(host)}:{port}", host, timeout=timeout)


def tcp_ipv6(host, port=80, timeout=DEFAULT_TIMEOUT):
    """Global multi-location IPv6 TCP port check."""
    return _run(f"https://tcp6.ping.pe/{host_for_url(host)}:{port}", host, ipv6=True, timeout=timeout)


def dig(host, rtype="A", timeout=DEFAULT_TIMEOUT):
    """Global multi-location DNS lookup."""
    return _run(f"https://dig.ping.pe/{host_for_url(host)}:{rtype.upper()}", host, timeout=timeout)
