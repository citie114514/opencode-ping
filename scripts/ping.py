#!/usr/bin/env python3
"""
Multi-mode network diagnostic tool.
Supports local ICMP ping, ITDOG multi-location ping, TCP ping, and website speed test.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts dir is in path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    Mode, PingNode, PingReport, LocalPingResult, TcpPingResult, WebTestResult,
    NodeStatus, parse_host, detect_url, format_latency, format_loss,
    status_emoji, is_warning, classify_region,
)
from local_ping import local_ping
from tcp_ping import tcp_ping as do_tcp_ping
from web_test import web_test as do_web_test


# ──────────────────────────────────────────────
# ITDOG remote ping
# ──────────────────────────────────────────────

def run_remote_ping(host: str, count: int, timeout: int) -> list:
    """Run ITDOG multi-location ping."""
    try:
        from services.itdog.client import ping as itdog_ping
        return itdog_ping(host, count=count, timeout=timeout)
    except ImportError as e:
        print(f"  [WARN] ITDOG module import error: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  [WARN] ITDOG error: {e}", file=sys.stderr)
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
                "name": r,
                "total": 0,
                "success": 0,
                "loss": 0,
                "timeout": 0,
                "unavailable": 0,
                "error": 0,
                "latencies": [],
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

    # Compute averages
    for d in regions.values():
        lats = d["latencies"]
        d["avg_ms"] = round(sum(lats) / len(lats), 1) if lats else None
        del d["latencies"]

    # Sort by defined order
    ordered = {}
    for r in region_order:
        if r in regions:
            ordered[r] = regions[r]
    for r in regions:
        if r not in ordered:
            ordered[r] = regions[r]

    return ordered


def build_summary(nodes: list, local: LocalPingResult = None) -> dict:
    """Build overall summary."""
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

    # Overall packet loss
    total_sent = sum(n.sent for n in nodes)
    total_received = sum(n.received for n in nodes)
    overall_loss = round((total_sent - total_received) / total_sent * 100, 1) if total_sent > 0 else 0.0

    return {
        "total": total,
        "success": success,
        "partial_loss": loss,
        "timeout": timeout,
        "unavailable": unavailable,
        "error": error,
        "avg_ms": avg_lat,
        "min_ms": min_lat,
        "max_ms": max_lat,
        "overall_loss_percent": overall_loss,
        "total_sent": total_sent,
        "total_received": total_received,
    }


# ──────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────

def print_report(report: PingReport, show_all: bool = False,
                 show_timeouts: bool = False, show_loss: bool = False):
    """Print formatted text report."""
    W = 60

    print()
    print(f"  / ping {report.target}")
    print(f"{'━' * W}")

    # ── Local Ping ──
    if report.local_ping:
        lp = report.local_ping
        print(f"  [本机 ICMP]")
        if lp.error:
            print(f"    错误: {lp.error}")
        else:
            print(f"    {lp.sent} 发 / {lp.received} 收  丢包: {format_loss(lp.loss_percent)}")
            if lp.avg_ms is not None:
                parts = [f"平均: {format_latency(lp.avg_ms)}"]
                if lp.min_ms is not None:
                    parts.append(f"最快: {format_latency(lp.min_ms)}")
                if lp.max_ms is not None:
                    parts.append(f"最慢: {format_latency(lp.max_ms)}")
                print(f"    {' | '.join(parts)}")
        print()

    # ── Remote Ping (ITDOG) ──
    if report.remote_nodes:
        s = report.summary
        print(f"  [ITDOG 多地点]")
        print(f"    监测点: {s['total']}")
        print(f"    成功: {s['success']}  丢包节点: {s['partial_loss']}  超时: {s['timeout']}")
        if s['unavailable'] > 0:
            print(f"    不可用: {s['unavailable']}")
        if s['avg_ms'] is not None:
            print(f"    平均延迟: {format_latency(s['avg_ms'])}  最快: {format_latency(s['min_ms'])}  最慢: {format_latency(s['max_ms'])}")
        print(f"    整体丢包: {format_loss(s['overall_loss_percent'])} ({s['total_received']}/{s['total_sent']})")
        print()

        # Region table
        print(f"    {'区域':<8} {'节点':>6} {'成功':>6} {'丢包':>6} {'超时':>6} {'平均延迟':>10}")
        print(f"    {'─'*52}")
        for rname, rd in report.regions.items():
            if rd["total"] == 0:
                continue
            avg_str = format_latency(rd["avg_ms"]) if rd["avg_ms"] is not None else "-"
            warn = ""
            if rd["timeout"] > 0:
                warn = " [T]"
            elif rd["loss"] > 0:
                warn = " [L]"
            print(f"    {rname:<8} {rd['total']:>6} {rd['success']:>6} {rd['loss']:>6} {rd['timeout']:>6} {avg_str:>10}{warn}")
        print()

        # Abnormal nodes
        abnormal = [n for n in report.remote_nodes
                    if n.status in (NodeStatus.TIMEOUT.value, NodeStatus.PARTIAL_LOSS.value,
                                    NodeStatus.UNAVAILABLE.value, NodeStatus.ERROR.value)
                    or (n.latest_ms is not None and n.latest_ms >= 100)]
        if abnormal:
            print(f"    异常节点:")
            for n in abnormal:
                label = status_emoji(n.status)
                if n.latest_ms is not None and n.latest_ms >= 200:
                    label = f"{n.latest_ms:.0f}ms HIGH LATENCY"
                elif n.latest_ms is not None and n.latest_ms >= 100:
                    label = f"{n.latest_ms:.0f}ms"
                elif n.status == NodeStatus.TIMEOUT.value:
                    label = "TIMEOUT"
                elif n.status == NodeStatus.PARTIAL_LOSS.value:
                    label = f"{n.loss_percent:.0f}% LOSS"
                elif n.status == NodeStatus.UNAVAILABLE.value:
                    label = "UNAVAILABLE"
                print(f"    ! {n.node_name:<20} {label}")
            print()
        else:
            print(f"    未发现明显丢包或超时")
            print()

        # Show all nodes if requested
        if show_all:
            print(f"    {'区域':<6} {'省份':<6} {'城市':<10} {'ISP':<4} {'节点':<16} {'响应IP':<16} {'丢包':>6} {'最新':>8} {'最快':>8} {'最慢':>8} {'平均':>8} {'状态':<10}")
            print(f"    {'─'*120}")
            for n in report.remote_nodes:
                region = n.region[:6]
                prov = n.province[:6]
                city = n.city[:10]
                isp = n.isp[:4] if n.isp else "-"
                name = n.node_name[:16]
                ip = n.resolved_ip[:16]
                loss_s = format_loss(n.loss_percent) if n.sent > 0 else "-"
                last_s = format_latency(n.latest_ms)
                min_s = format_latency(n.min_ms)
                max_s = format_latency(n.max_ms)
                avg_s = format_latency(n.avg_ms)
                status_s = n.status
                print(f"    {region:<6} {prov:<6} {city:<10} {isp:<4} {name:<16} {ip:<16} {loss_s:>6} {last_s:>8} {min_s:>8} {max_s:>8} {avg_s:>8} {status_s:<10}")
            print()
        else:
            print(f"    已获取 {len(report.remote_nodes)} 个节点, 使用 --show-all 查看完整节点明细")
            print()

    # ── TCP Ping ──
    if report.tcp_ping:
        tp = report.tcp_ping
        print(f"  [TCP {tp.port}]")
        if tp.success:
            print(f"    连接成功: {format_latency(tp.avg_ms)}  (尝试 {tp.attempts} 次, 成功 {tp.successes} 次)")
            if tp.min_ms is not None:
                print(f"    最快: {format_latency(tp.min_ms)}  最慢: {format_latency(tp.max_ms)}")
        else:
            print(f"    连接失败: {tp.error}")
        print()

    # ── Web Test ──
    if report.web_test:
        wt = report.web_test
        print(f"  [HTTPS 测速]")
        if wt.error:
            print(f"    错误: {wt.error}")
        else:
            print(f"    HTTP {wt.status_code} {wt.statusText}")
            if wt.ttfb_ms is not None:
                print(f"    TTFB: {format_latency(wt.ttfb_ms)}  总耗时: {format_latency(wt.total_ms)}")
            if wt.response_size is not None:
                size_str = _format_size(wt.response_size)
                print(f"    响应大小: {size_str}  Content-Type: {wt.content_type}")
            if wt.redirect_count > 0:
                print(f"    重定向: {wt.redirect_count} 次")
        print()

    # ── Errors ──
    if report.errors:
        print(f"  [错误]")
        for e in report.errors:
            print(f"    - {e}")
        print()


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-mode network diagnostic tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("host", help="Target host, IP, or URL")
    parser.add_argument("--mode", choices=["all", "local", "remote", "tcp", "web"],
                        default="all", help="Test mode (default: all)")
    parser.add_argument("--count", type=int, default=10, help="Ping count (default: 10)")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (default: 60)")
    parser.add_argument("--port", type=int, default=None, help="TCP port (default: auto-detect)")
    parser.add_argument("--url", default=None, help="URL for web test")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--show-all", action="store_true", help="Show all nodes in text output")
    parser.add_argument("--show-timeouts", action="store_true", help="Show timeout nodes")
    parser.add_argument("--show-loss", action="store_true", help="Show packet loss nodes")
    parser.add_argument("--sort", choices=["latency", "loss", "region", "status"], default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    # Parse input
    raw_host = args.host
    host, port_from_input, original = parse_host(raw_host)
    url = args.url or detect_url(raw_host)

    # Determine port
    port = args.port or port_from_input or 443

    # Determine modes
    mode = args.mode
    do_local = mode in ("all", "local")
    do_remote = mode in ("all", "remote")
    do_tcp = mode in ("all", "tcp")
    do_web = mode in ("all", "web")

    # If URL provided, extract host for ping/tcp
    if url and do_web:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname:
            host = parsed.hostname

    start_time = datetime.now(timezone.utc)
    report = PingReport(target=host)
    report.started_at = start_time.isoformat()

    # ── Local ICMP Ping ──
    if do_local:
        if args.debug:
            print(f"[DEBUG] Running local ping to {host}", file=sys.stderr)
        report.local_ping = local_ping(host, count=args.count, timeout=min(args.timeout, 30))

    # ── Remote ITDOG Ping ──
    if do_remote:
        if args.debug:
            print(f"[DEBUG] Running ITDOG ping to {host}", file=sys.stderr)
        report.remote_nodes = run_remote_ping(host, args.count, args.timeout)
        if report.remote_nodes:
            report.regions = aggregate_regions(report.remote_nodes)
            report.summary = build_summary(report.remote_nodes, report.local_ping)

    # ── TCP Ping ──
    if do_tcp:
        if args.debug:
            print(f"[DEBUG] Running TCP ping to {host}:{port}", file=sys.stderr)
        report.tcp_ping = do_tcp_ping(host, port, count=5, timeout=min(args.timeout, 10))

    # ── Web Test ──
    if do_web and url:
        if args.debug:
            print(f"[DEBUG] Running web test on {url}", file=sys.stderr)
        report.web_test = do_web_test(url, timeout=min(args.timeout, 15))
    elif do_web and not url:
        # Auto-generate URL from host
        auto_url = f"https://{host}"
        if args.debug:
            print(f"[DEBUG] Auto-generated URL: {auto_url}", file=sys.stderr)
        report.web_test = do_web_test(auto_url, timeout=min(args.timeout, 15))

    end_time = datetime.now(timezone.utc)
    report.finished_at = end_time.isoformat()
    report.duration_seconds = round((end_time - start_time).total_seconds(), 2)

    # Output
    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print_report(report, show_all=args.show_all,
                     show_timeouts=args.show_timeouts,
                     show_loss=args.show_loss)


if __name__ == "__main__":
    main()
