#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-mode network diagnostic tool.

Modes:
    all      local ICMP + remote multi-location ping + local TCP + local web + local DNS
    local    local ICMP ping
    remote   remote multi-location ICMP ping
    tcp      local TCP ping + remote multi-location TCPing
    web      local website speed test + remote multi-location website test
    dns      local DNS resolution test + remote multi-location DNS lookup

Remote providers:
    itdog    (default) China-focused multi-location, tools: ping / ping_ipv6 /
             tcping / http / dns
    pingpe   global multi-location, tools: ping / ping6 / tcp / tcp6 / dig
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure scripts dir is in path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (  # noqa: E402
    PingNode, PingReport, NodeStatus, parse_host, detect_url,
    format_latency, format_loss, classify_region,
)
from local_ping import local_ping  # noqa: E402
from tcp_ping import tcp_ping as do_tcp_ping  # noqa: E402
from web_test import web_test as do_web_test  # noqa: E402
from dns_test import dns_test as do_dns_test  # noqa: E402


PROVIDERS = ["itdog", "pingpe", "none"]


def provider_label(provider: str) -> str:
    return {"itdog": "ITDOG", "pingpe": "ping.pe", "none": "-"}.get(provider, provider)


def _is_ipv6_literal(host: str) -> bool:
    return ":" in host and not host.startswith("[")


def _host_for_url(host: str) -> str:
    """Wrap a bare IPv6 literal in brackets for use in URLs / host:port."""
    if _is_ipv6_literal(host):
        return f"[{host}]"
    return host


# ──────────────────────────────────────────────
# Remote multi-location dispatch
# ──────────────────────────────────────────────

def run_remote(tool: str, host: str, provider: str, port: int = None,
               dns_type: str = None, timeout: int = 60, ipv6: bool = False) -> list:
    """Dispatch a remote multi-location tool to the selected provider."""
    if provider == "none":
        return []
    try:
        if provider == "itdog":
            from services.itdog import client as svc
            if tool == "ping":
                return svc.ping_ipv6(host, timeout=timeout) if ipv6 else svc.ping(host, timeout=timeout)
            if tool == "tcp":
                return svc.tcping(host, port=port or 80, timeout=timeout)
            if tool == "web":
                return svc.http(host, timeout=timeout)
            if tool == "dns":
                return svc.dns(host, rtype=dns_type or "A", timeout=timeout)
        elif provider == "pingpe":
            from services.pingpe import client as svc
            if tool == "ping":
                return svc.ping_ipv6(host, timeout=timeout) if ipv6 else svc.ping(host, timeout=timeout)
            if tool == "tcp":
                if ipv6:
                    return svc.tcp_ipv6(host, port=port or 80, timeout=timeout)
                return svc.tcp(host, port=port or 80, timeout=timeout)
            if tool == "web":
                print("  [WARN] ping.pe has no website test; use --provider itdog", file=sys.stderr)
                return []
            if tool == "dns":
                return svc.dig(host, rtype=dns_type or "A", timeout=timeout)
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] remote {provider}/{tool} error: {e}", file=sys.stderr)
    return []


# ──────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────

def aggregate_regions(nodes: list) -> dict:
    """Aggregate nodes by region."""
    region_order = ["华东", "华北", "华中", "华南", "西南", "西北", "东北", "港澳台", "海外", "未知"]
    regions = {}

    for node in nodes:
        r = node.region
        if r not in regions:
            regions[r] = {
                "name": r, "total": 0, "success": 0, "loss": 0,
                "timeout": 0, "unavailable": 0, "error": 0, "latencies": [],
            }
        d = regions[r]
        d["total"] += 1

        s = node.status
        if s == NodeStatus.SUCCESS.value:
            d["success"] += 1
            if node.latest_ms is not None:
                d["latencies"].append(node.latest_ms)
        elif s == NodeStatus.TIMEOUT.value:
            d["timeout"] += 1
        elif s == NodeStatus.PARTIAL_LOSS.value:
            d["loss"] += 1
            if node.latest_ms is not None:
                d["latencies"].append(node.latest_ms)
        elif s == NodeStatus.UNAVAILABLE.value:
            d["unavailable"] += 1
        else:
            d["error"] += 1

    for d in regions.values():
        lats = d["latencies"]
        d["avg_ms"] = round(sum(lats) / len(lats), 1) if lats else None
        del d["latencies"]

    ordered = {}
    for r in region_order:
        if r in regions:
            ordered[r] = regions[r]
    for r in regions:
        if r not in ordered:
            ordered[r] = regions[r]
    return ordered


def build_summary(nodes: list) -> dict:
    """Build overall summary for a set of nodes."""
    total = len(nodes)
    success = sum(1 for n in nodes if n.status == NodeStatus.SUCCESS.value)
    loss = sum(1 for n in nodes if n.status == NodeStatus.PARTIAL_LOSS.value)
    timeout = sum(1 for n in nodes if n.status == NodeStatus.TIMEOUT.value)
    unavailable = sum(1 for n in nodes if n.status == NodeStatus.UNAVAILABLE.value)
    error = sum(1 for n in nodes if n.status == NodeStatus.ERROR.value)

    latencies = [n.latest_ms for n in nodes if n.latest_ms is not None]
    avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else None
    min_lat = min(latencies) if latencies else None
    max_lat = max(latencies) if latencies else None

    total_sent = sum(n.sent for n in nodes)
    total_received = sum(n.received for n in nodes)
    overall_loss = round((total_sent - total_received) / total_sent * 100, 1) if total_sent > 0 else 0.0

    return {
        "total": total, "success": success, "partial_loss": loss,
        "timeout": timeout, "unavailable": unavailable, "error": error,
        "avg_ms": avg_lat, "min_ms": min_lat, "max_ms": max_lat,
        "overall_loss_percent": overall_loss,
        "total_sent": total_sent, "total_received": total_received,
    }


# ──────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────

W = 60
LINE = "=" * W


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _print_regions(regions: dict):
    print("    区域")
    for rname, rd in regions.items():
        if rd["total"] == 0:
            continue
        avg_str = format_latency(rd["avg_ms"]) if rd["avg_ms"] is not None else "-"
        extras = []
        if rd["loss"] > 0:
            extras.append(f"丢包 {rd['loss']}")
        if rd["timeout"] > 0:
            extras.append(f"超时 {rd['timeout']}")
        extra_str = "   " + "   ".join(extras) if extras else ""
        print(f"    {rname:<8}{rd['total']:>4} 节点   平均 {avg_str:<8}{extra_str}")
    print()


def _node_metric(node: PingNode, tool: str) -> str:
    if tool == "ping":
        if node.latest_ms is not None:
            return format_latency(node.latest_ms)
        return node.status.upper()
    if tool == "tcp":
        if node.latest_ms is not None:
            return format_latency(node.latest_ms)
        return "FAILED"
    if tool == "web":
        status = node.raw.get("http_status", "") or "-"
        if node.latest_ms is not None:
            dns_ms = node.raw.get("dns_ms")
            conn_ms = node.raw.get("connect_ms")
            extra = ""
            if dns_ms is not None or conn_ms is not None:
                extra = f" (DNS {format_latency(dns_ms)} / 连接 {format_latency(conn_ms)})"
            return f"HTTP {status}  {format_latency(node.latest_ms)}{extra}"
        return f"HTTP {status}  FAILED"
    if tool == "dns":
        answers = node.raw.get("answers") or []
        rtype = node.raw.get("type") or ""
        summary = ", ".join(answers[:3])
        if len(answers) > 3:
            summary += f" (+{len(answers) - 3})"
        ms = format_latency(node.latest_ms)
        return f"{rtype} {summary}  {ms}".strip()
    return format_latency(node.latest_ms)


def _print_remote_block(title: str, nodes: list, regions: dict, summary: dict,
                        tool: str, show_all: bool = False):
    print(f"  [{title}]")
    if not nodes:
        print("    无数据")
        print()
        return

    s = summary
    print(f"    监测点: {s['total']}   成功: {s['success']}   "
          f"丢包: {s['partial_loss']}   超时: {s['timeout']}")
    if s.get("avg_ms") is not None:
        print(f"    平均: {format_latency(s['avg_ms'])}   "
              f"最快: {format_latency(s['min_ms'])}   "
              f"最慢: {format_latency(s['max_ms'])}")
    print()

    _print_regions(regions)

    abnormal = [
        n for n in nodes
        if n.status != NodeStatus.SUCCESS.value
        or (n.latest_ms is not None and n.latest_ms >= 200)
    ]
    if show_all:
        print(f"    {'节点':<24} {'响应IP':<22} 详情")
        print(f"    {'─' * 90}")
        for n in nodes:
            print(f"    {n.node_name[:24]:<24} {n.resolved_ip[:22]:<22} {_node_metric(n, tool)}")
        print()
    elif abnormal:
        print("    异常节点")
        for n in abnormal[:40]:
            print(f"    ! {n.node_name[:24]:<24} {_node_metric(n, tool)}")
        if len(abnormal) > 40:
            print(f"    ... 其余 {len(abnormal) - 40} 个异常节点")
        print()
    else:
        print("    未发现明显异常")
        print()


def print_report(report: PingReport, show_all: bool = False,
                 show_timeouts: bool = False, show_loss: bool = False):
    """Print formatted text report."""
    print()
    print(f"  / ping {report.target}")
    print(f"  {LINE}")
    print()
    print("  网络诊断")
    print(f"  {LINE}")
    print()

    # ── Local ICMP ──
    if report.local_ping:
        lp = report.local_ping
        print("  [本机 ICMP]")
        if lp.error:
            print(f"    错误: {lp.error}")
        else:
            print(f"    {lp.sent} 发 / {lp.received} 收")
            print(f"    丢包: {format_loss(lp.loss_percent)}")
            if lp.avg_ms is not None:
                print(f"    平均: {format_latency(lp.avg_ms)}")
                if lp.min_ms is not None:
                    print(f"    最快: {format_latency(lp.min_ms)}")
                if lp.max_ms is not None:
                    print(f"    最慢: {format_latency(lp.max_ms)}")
        print()

    # ── Remote ICMP ──
    if report.remote_nodes:
        _print_remote_block(
            f"{provider_label(report.remote_provider)} 多地点",
            report.remote_nodes, report.regions, report.summary, "ping", show_all,
        )

    # ── Local TCP ──
    if report.tcp_ping:
        tp = report.tcp_ping
        print(f"  [本机 TCP {tp.port}]")
        if tp.success:
            print(f"    连接成功: {format_latency(tp.avg_ms)}")
            if tp.min_ms is not None:
                print(f"    最快: {format_latency(tp.min_ms)}  最慢: {format_latency(tp.max_ms)}")
        else:
            print(f"    连接失败: {tp.error}")
        print()

    # ── Remote TCPing ──
    if report.remote_tcp_nodes:
        _print_remote_block(
            f"{provider_label(report.remote_provider)} TCPing",
            report.remote_tcp_nodes, report.tcp_regions, report.tcp_summary,
            "tcp", show_all,
        )

    # ── Local Web test ──
    if report.web_test:
        wt = report.web_test
        print("  [本机 HTTPS 测速]")
        if wt.error:
            print(f"    错误: {wt.error}")
        else:
            print(f"    HTTP: {wt.status_code} {wt.status_text}")
            if wt.dns_ms is not None:
                print(f"    DNS: {format_latency(wt.dns_ms)}")
            if wt.tcp_ms is not None:
                print(f"    TCP: {format_latency(wt.tcp_ms)}")
            if wt.tls_ms is not None:
                print(f"    TLS: {format_latency(wt.tls_ms)}")
            if wt.ttfb_ms is not None:
                print(f"    TTFB: {format_latency(wt.ttfb_ms)}")
                print(f"    总耗时: {format_latency(wt.total_ms)}")
            if wt.response_size is not None:
                print(f"    响应大小: {_format_size(wt.response_size)}")
            if wt.redirect_count > 0:
                print(f"    重定向: {wt.redirect_count} 次")
        print()

    # ── Remote website test ──
    if report.remote_web_nodes:
        _print_remote_block(
            f"{provider_label(report.remote_provider)} 网站测速",
            report.remote_web_nodes, report.web_regions, report.web_summary,
            "web", show_all,
        )

    # ── Local DNS ──
    if report.local_dns:
        dns = report.local_dns
        print(f"  [本机 DNS 解析:{dns.rtype}]")
        if dns.error and not dns.answers:
            print(f"    错误: {dns.error}")
        else:
            print(f"    响应: {format_latency(dns.resolve_ms)}")
            answers = dns.answers
            if answers:
                for a in answers[:10]:
                    print(f"    - {a}")
                if len(answers) > 10:
                    print(f"    ... 共 {len(answers)} 条")
            else:
                print("    无记录")
            if dns.cname_chain:
                print(f"    CNAME: {' -> '.join(dns.cname_chain)}")
            if dns.error:
                print(f"    提示: {dns.error}")
        print()

    # ── Remote DNS ──
    if report.remote_dns_nodes:
        _print_remote_block(
            f"{provider_label(report.remote_provider)} DNS",
            report.remote_dns_nodes, report.dns_regions, report.dns_summary,
            "dns", show_all,
        )

    # ── Errors ──
    if report.errors:
        print("  [错误]")
        for e in report.errors:
            print(f"    - {e}")
        print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-mode network diagnostic tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("host", help="Target host, IP, or URL")
    parser.add_argument("--mode", choices=["all", "local", "remote", "tcp", "web", "dns"],
                        default="all", help="Test mode (default: all)")
    parser.add_argument("--provider", choices=PROVIDERS, default="itdog",
                        help="Remote multi-location provider (default: itdog)")
    parser.add_argument("--count", type=int, default=10, help="Ping count (default: 10)")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (default: 60)")
    parser.add_argument("--port", type=int, default=None, help="TCP port (default: auto-detect)")
    parser.add_argument("--url", default=None, help="URL for web test")
    parser.add_argument("--dns-type", default="A",
                        help="DNS record type: A/AAAA/CNAME/MX/NS/TXT/SOA/PTR (default: A)")
    family = parser.add_mutually_exclusive_group()
    family.add_argument("-4", "--ipv4", action="store_true", help="Force IPv4 (default)")
    family.add_argument("-6", "--ipv6", action="store_true",
                        help="Force IPv6 and use dedicated IPv6 tools")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--show-all", action="store_true", help="Show all nodes in text output")
    parser.add_argument("--show-timeouts", action="store_true", help="Show timeout nodes")
    parser.add_argument("--show-loss", action="store_true", help="Show packet loss nodes")
    parser.add_argument("--sort", choices=["latency", "loss", "region", "status"], default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    raw_host = args.host
    host, port_from_input, _original = parse_host(raw_host)
    url = args.url or detect_url(raw_host)
    port = args.port or port_from_input or 443
    ipv6 = bool(args.ipv6)

    mode = args.mode
    do_local_icmp = mode in ("all", "local")
    do_remote_ping = mode in ("all", "remote")
    do_local_tcp = mode in ("all", "tcp")
    do_remote_tcp = mode == "tcp"
    do_local_web = mode in ("all", "web")
    do_remote_web = mode == "web"
    do_local_dns = mode in ("all", "dns")
    do_remote_dns = mode == "dns"

    start_time = datetime.now(timezone.utc)
    report = PingReport(target=host)
    report.remote_provider = args.provider
    report.started_at = start_time.isoformat()

    # ── Local ICMP ──
    if do_local_icmp:
        if args.debug:
            print(f"[DEBUG] local ping {host} (ipv6={ipv6})", file=sys.stderr)
        report.local_ping = local_ping(host, count=args.count,
                                       timeout=min(args.timeout, 30), ipv6=ipv6)

    # ── Remote ICMP ──
    if do_remote_ping:
        if args.debug:
            print(f"[DEBUG] remote ping {host} via {args.provider} (ipv6={ipv6})", file=sys.stderr)
        report.remote_nodes = run_remote("ping", host, args.provider,
                                         timeout=args.timeout, ipv6=ipv6)
        if report.remote_nodes:
            report.regions = aggregate_regions(report.remote_nodes)
            report.summary = build_summary(report.remote_nodes)
            first_raw = report.remote_nodes[0].raw
            expected = first_raw.get("expected_total", 0)
            if expected and expected > len(report.remote_nodes):
                report.errors.append(
                    f"{provider_label(args.provider)}返回了 {len(report.remote_nodes)} 个节点，"
                    f"但预期 {expected} 个（可能有节点仍在加载）。"
                )

    # ── Local TCP ──
    if do_local_tcp:
        if args.debug:
            print(f"[DEBUG] local TCP {host}:{port} (ipv6={ipv6})", file=sys.stderr)
        report.tcp_ping = do_tcp_ping(host, port, count=5,
                                      timeout=min(args.timeout, 10), ipv6=ipv6)

    # ── Remote TCPing ──
    if do_remote_tcp:
        if args.debug:
            print(f"[DEBUG] remote TCPing {host}:{port} via {args.provider}", file=sys.stderr)
        report.remote_tcp_nodes = run_remote("tcp", host, args.provider, port=port,
                                             timeout=args.timeout, ipv6=ipv6)
        if report.remote_tcp_nodes:
            report.tcp_regions = aggregate_regions(report.remote_tcp_nodes)
            report.tcp_summary = build_summary(report.remote_tcp_nodes)

    # ── Local Web test ──
    if do_local_web:
        web_url = url or f"https://{_host_for_url(host)}"
        if args.debug:
            print(f"[DEBUG] web test {web_url} (ipv6={ipv6})", file=sys.stderr)
        report.web_test = do_web_test(web_url, timeout=min(args.timeout, 15), ipv6=ipv6)

    # ── Remote website test ──
    if do_remote_web:
        if args.debug:
            print(f"[DEBUG] remote web test {host} via {args.provider}", file=sys.stderr)
        report.remote_web_nodes = run_remote("web", host, args.provider,
                                             timeout=args.timeout, ipv6=ipv6)
        if report.remote_web_nodes:
            report.web_regions = aggregate_regions(report.remote_web_nodes)
            report.web_summary = build_summary(report.remote_web_nodes)

    # ── Local DNS ──
    if do_local_dns:
        if args.debug:
            print(f"[DEBUG] local DNS {host} type={args.dns_type}", file=sys.stderr)
        report.local_dns = do_dns_test(host, rtype=args.dns_type, ipv6=ipv6)

    # ── Remote DNS ──
    if do_remote_dns:
        if args.debug:
            print(f"[DEBUG] remote DNS {host} type={args.dns_type} via {args.provider}", file=sys.stderr)
        report.remote_dns_nodes = run_remote("dns", host, args.provider, dns_type=args.dns_type,
                                             timeout=args.timeout, ipv6=ipv6)
        if report.remote_dns_nodes:
            report.dns_regions = aggregate_regions(report.remote_dns_nodes)
            report.dns_summary = build_summary(report.remote_dns_nodes)

    end_time = datetime.now(timezone.utc)
    report.finished_at = end_time.isoformat()
    report.duration_seconds = round((end_time - start_time).total_seconds(), 2)

    if args.output == "json":
        output = report.to_dict()
        if output.get("local_ping") and output["local_ping"].get("raw_output"):
            output["local_ping"]["raw_output"] = output["local_ping"]["raw_output"][:500]
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    else:
        print_report(report, show_all=args.show_all,
                     show_timeouts=args.show_timeouts, show_loss=args.show_loss)


if __name__ == "__main__":
    main()
