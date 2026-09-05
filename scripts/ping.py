#!/usr/bin/env python3
"""
Ping a host from multiple locations using online ping services.
Supports ITDOG (itdog.cn) and Ping.pe.
"""

import argparse
import sys
import time
from pathlib import Path

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from services import itdog, pingpe
from utils import parse_host, format_results


def main():
    parser = argparse.ArgumentParser(description="Multi-location ping test")
    parser.add_argument("host", help="Target host (domain or IP)")
    parser.add_argument("--count", type=int, default=10, help="Number of ping packets per monitoring point")
    parser.add_argument("--timeout", type=int, default=5, help="Timeout in seconds")
    parser.add_argument("--service", choices=["itdog", "pingpe", "both"], default="itdog",
                        help="Which service to use (default: itdog)")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    args = parser.parse_args()

    host = parse_host(args.host)
    if not host:
        print("Error: Invalid host", file=sys.stderr)
        sys.exit(1)

    results = []
    region_summary = None

    if args.service in ("itdog", "both"):
        print(f"正在查询 ITDOG: {host}...", file=sys.stderr)
        try:
            itdog_results = itdog.ping(host, count=args.count, timeout=args.timeout)
            results.extend(itdog_results)
            # 获取区域汇总
            region_summary = itdog.get_region_summary(itdog_results)
        except Exception as e:
            print(f"ITDOG 错误: {e}", file=sys.stderr)

    if args.service in ("pingpe", "both"):
        print(f"正在查询 Ping.pe: {host}...", file=sys.stderr)
        try:
            pingpe_results = pingpe.ping(host, count=args.count, timeout=args.timeout)
            results.extend(pingpe_results)
        except Exception as e:
            print(f"Ping.pe 错误: {e}", file=sys.stderr)

    if not results:
        print("所有服务均无结果", file=sys.stderr)
        sys.exit(1)

    format_results(results, args.output, region_summary)


if __name__ == "__main__":
    main()