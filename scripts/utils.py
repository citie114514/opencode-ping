"""
Shared utilities for ping scripts.
"""

import re
import sys
import json
from typing import List, Dict, Any, Optional


def parse_host(host: str) -> Optional[str]:
    """
    Validate and clean host input.
    
    Args:
        host: Hostname or IP address
    
    Returns:
        Cleaned host string or None if invalid
    """
    # Remove protocol if present
    host = re.sub(r'^https?://', '', host)
    # Remove trailing slash or path
    host = host.split('/')[0]
    # Remove port if present
    host = host.split(':')[0]
    
    if not host:
        return None
    
    # Basic validation: host should contain at least one alphanumeric character
    if not re.search(r'[a-zA-Z0-9]', host):
        return None
    
    return host.lower()


def format_results(results: List[Dict[str, Any]], output_format: str = "text", 
                   region_summary: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    """
    Format and print ping results.
    
    Args:
        results: List of ping result dictionaries
        output_format: 'text' or 'json'
        region_summary: 区域汇总数据（可选）
    """
    if output_format == "json":
        output = {
            "results": results,
            "region_summary": region_summary
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return
    
    # Text format
    if not results:
        print("No results to display")
        return
    
    # 统计总数
    total_points = len(results)
    timeout_points = sum(1 for r in results if r.get("is_timeout"))
    valid_points = total_points - timeout_points
    
    print(f"\n{'='*60}")
    print(f"Ping 测试结果 - 共 {total_points} 个监控点")
    print(f"{'='*60}")
    
    # 显示区域汇总
    if region_summary:
        print(f"\n{'─'*60}")
        print("各区域汇总")
        print(f"{'─'*60}")
        
        # 按固定顺序显示区域
        region_order = ["华东", "华北", "华西", "华南", "港澳台", "海外", "未知"]
        
        for region in region_order:
            if region not in region_summary:
                continue
            
            data = region_summary[region]
            total = data["total"]
            timeout_count = data["timeout_count"]
            min_lat = data.get("min_latency")
            max_lat = data.get("max_latency")
            avg_lat = data.get("avg_latency")
            avg_loss = data.get("avg_loss")
            has_loss = data.get("has_loss", False)
            
            # 区域状态标记
            if timeout_count > 0:
                status = "[超时]"
            elif has_loss:
                status = "[丢包]"
            else:
                status = "[正常]"
            
            print(f"\n【{region}】{status}")
            print(f"  监控点: {total} 个", end="")
            if timeout_count > 0:
                print(f" (其中 {timeout_count} 个超时)", end="")
            print()
            
            if min_lat is not None:
                print(f"  延迟: {min_lat}ms ~ {max_lat}ms, 平均 {avg_lat:.1f}ms")
            else:
                print(f"  延迟: 全部超时")
            
            if avg_loss is not None:
                if avg_loss > 0:
                    print(f"  丢包率: {avg_loss:.1f}%")
                else:
                    print(f"  丢包率: 0%")
        
        print(f"\n{'─'*60}")
    
    # 显示详细结果（按区域分组）
    print(f"\n{'─'*60}")
    print("详细结果")
    print(f"{'─'*60}")
    
    # 按区域分组
    by_region = {}
    for r in results:
        region = r.get("region", "未知")
        if region not in by_region:
            by_region[region] = []
        by_region[region].append(r)
    
    for region in ["华东", "华北", "华西", "华南", "港澳台", "海外", "未知"]:
        if region not in by_region:
            continue
        
        region_results = by_region[region]
        print(f"\n【{region}】")
        
        # 分离正常和超时的结果
        normal = [r for r in region_results if not r.get("is_timeout")]
        timeout = [r for r in region_results if r.get("is_timeout")]
        
        # 显示正常结果
        if normal:
            print("  正常:")
            for r in sorted(normal, key=lambda x: x.get("last_ms", float('inf'))):
                loc = r.get("location", "未知")
                lat = r.get("last_ms", "--")
                loss = r.get("loss_pct")
                loss_str = f", 丢包{loss}%" if loss and loss > 0 else ""
                print(f"    - {loc}: {lat}ms{loss_str}")
        
        # 显示超时结果
        if timeout:
            print("  超时:")
            for r in timeout:
                loc = r.get("location", "未知")
                print(f"    - {loc}: 超时")
    
    print(f"\n{'='*60}")
    print(f"统计: 共 {total_points} 个监控点, 正常 {valid_points} 个, 超时 {timeout_points} 个")
    print(f"{'='*60}\n")