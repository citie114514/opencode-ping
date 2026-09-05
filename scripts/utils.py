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


def format_results(results: List[Dict[str, Any]], output_format: str = "text") -> None:
    """
    Format and print ping results.
    
    Args:
        results: List of ping result dictionaries
        output_format: 'text' or 'json'
    """
    if output_format == "json":
        print(json.dumps(results, indent=2))
        return
    
    # Text format
    if not results:
        print("No results to display")
        return
    
    # Group by service
    services = {}
    for r in results:
        svc = r.get("service", "unknown")
        if svc not in services:
            services[svc] = []
        services[svc].append(r)
    
    for svc, svc_results in services.items():
        print(f"\n=== {svc.upper()} Results ===")
        
        # Calculate statistics
        latencies = [r["last_ms"] for r in svc_results if r.get("last_ms") is not None]
        if not latencies:
            print("No valid latency data")
            continue
        
        min_lat = min(latencies)
        max_lat = max(latencies)
        avg_lat = sum(latencies) / len(latencies)
        
        print(f"Monitoring points: {len(svc_results)}")
        print(f"Fastest: {min_lat} ms")
        print(f"Slowest: {max_lat} ms")
        print(f"Average: {avg_lat:.1f} ms")
        
        # Show top 5 fastest and slowest
        sorted_results = sorted(svc_results, key=lambda x: x.get("last_ms", float('inf')))
        
        print("\nTop 5 fastest:")
        for i, r in enumerate(sorted_results[:5], 1):
            loc = r.get("location", "Unknown")
            lat = r.get("last_ms", "--")
            print(f"  {i}. {loc}: {lat} ms")
        
        print("\nTop 5 slowest:")
        for i, r in enumerate(sorted_results[-5:], 1):
            loc = r.get("location", "Unknown")
            lat = r.get("last_ms", "--")
            print(f"  {i}. {loc}: {lat} ms")
        
        # Show packet loss if available
        losses = [r.get("loss_pct") for r in svc_results if r.get("loss_pct") is not None]
        if losses:
            avg_loss = sum(losses) / len(losses)
            print(f"\nAverage packet loss: {avg_loss:.1f}%")
    
    print()