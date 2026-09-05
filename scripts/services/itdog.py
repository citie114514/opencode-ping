"""
ITDOG ping service adapter.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any


def ping(host: str, count: int = 10, timeout: int = 5) -> List[Dict[str, Any]]:
    """
    Ping a host using ITDOG's online ping service.
    
    Args:
        host: Target hostname or IP
        count: Number of ping packets (not used by ITDOG, kept for interface consistency)
        timeout: Timeout in seconds (not used by ITDOG, kept for interface consistency)
    
    Returns:
        List of dictionaries with ping results from each monitoring point
    """
    url = f"https://www.itdog.cn/ping/{host}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "lxml")
    results = []
    
    # Find the ping results table
    table = soup.find("table", {"id": "simpletable"})
    if not table:
        # Fallback: find any table with ping results
        tables = soup.find_all("table")
        for t in tables:
            if t.find("th", string=lambda x: x and "最新(ms)" in x):
                table = t
                break
    
    if not table:
        raise ValueError("Could not find ping results table on ITDOG page")
    
    # Parse table rows
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue
        
        # Extract data from cells
        try:
            location = cells[0].get_text(strip=True)
            response_ip = cells[1].get_text(strip=True)
            ip_geo = cells[2].get_text(strip=True)
            loss = cells[3].get_text(strip=True)
            sent = cells[4].get_text(strip=True)
            last_ms = cells[5].get_text(strip=True)
            best_ms = cells[6].get_text(strip=True)
            worst_ms = cells[7].get_text(strip=True)
            avg_ms = cells[8].get_text(strip=True)
            
            # Skip rows with no data or timeout
            if last_ms in ("超时", "--", ""):
                continue
            
            # Convert numeric values
            try:
                last_ms = int(last_ms)
                best_ms = int(best_ms) if best_ms not in ("--", "") else None
                worst_ms = int(worst_ms) if worst_ms not in ("--", "") else None
                avg_ms = int(avg_ms) if avg_ms not in ("--", "") else None
                loss_pct = int(loss.replace("%", "")) if loss not in ("--", "") else None
                sent_count = int(sent) if sent not in ("--", "") else None
            except ValueError:
                continue
            
            results.append({
                "service": "itdog",
                "location": location,
                "response_ip": response_ip,
                "ip_geo": ip_geo,
                "loss_pct": loss_pct,
                "sent": sent_count,
                "last_ms": last_ms,
                "best_ms": best_ms,
                "worst_ms": worst_ms,
                "avg_ms": avg_ms,
            })
        except (IndexError, ValueError):
            # Skip malformed rows
            continue
    
    return results