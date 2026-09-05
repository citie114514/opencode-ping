"""
ITDOG ping service adapter.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re


# 区域分类映射
REGION_MAP = {
    # 华东
    "上海": "华东", "江苏": "华东", "浙江": "华东", "安徽": "华东", 
    "福建": "华东", "江西": "华东", "山东": "华东",
    # 华北
    "北京": "华北", "天津": "华北", "河北": "华北", "山西": "华北", "内蒙古": "华北",
    # 华西（西南+西北）
    "四川": "华西", "重庆": "华西", "贵州": "华西", "云南": "华西", "西藏": "华西",
    "陕西": "华西", "甘肃": "华西", "青海": "华西", "宁夏": "华西", "新疆": "华西",
    # 华南
    "广东": "华南", "广西": "华南", "海南": "华南", "湖南": "华南", "湖北": "华南", "河南": "华南",
    # 港澳台
    "香港": "港澳台", "澳门": "港澳台", "台湾": "港澳台",
    # 海外（通过国家名判断）
    "美国": "海外", "日本": "海外", "韩国": "海外", "新加坡": "海外",
    "德国": "海外", "英国": "海外", "法国": "海外", "澳大利亚": "海外",
    "加拿大": "海外", "俄罗斯": "海外", "印度": "海外", "马来西亚": "海外",
    "泰国": "海外", "越南": "海外", "菲律宾": "海外", "印尼": "海外",
}


def classify_region(location: str, ip_geo: str = "") -> str:
    """
    根据地点信息判断所属区域
    
    Args:
        location: 监控点位置（如"电信 辽宁大连"）
        ip_geo: IP地理位置（如"中国/香港/阿里云"）
    
    Returns:
        区域名称：华东、华北、华西、华南、港澳台、海外、未知
    """
    # 合并位置信息进行判断
    text = f"{location} {ip_geo}"
    
    # 先检查是否有明确的区域标记
    for keyword, region in REGION_MAP.items():
        if keyword in text:
            return region
    
    # 检查是否包含"海外"字样
    if "海外" in text:
        return "海外"
    
    # 检查是否包含中国省份
    china_provinces = [
        "黑龙江", "吉林", "辽宁", "河北", "山东", "江苏", "浙江", "安徽",
        "福建", "江西", "湖北", "湖南", "广东", "河南", "山西", "陕西",
        "甘肃", "青海", "四川", "贵州", "云南", "海南", "台湾",
        "北京", "天津", "上海", "重庆", "广西", "西藏", "宁夏", "内蒙古", "新疆"
    ]
    for province in china_provinces:
        if province in text:
            # 根据省份判断区域
            if province in ["黑龙江", "吉林", "辽宁"]:
                return "华北"  # 东北地区
            elif province in ["河北", "山东", "北京", "天津"]:
                return "华北"
            elif province in ["江苏", "浙江", "上海", "安徽", "福建", "江西"]:
                return "华东"
            elif province in ["湖北", "湖南", "河南", "广东", "广西", "海南"]:
                return "华南"
            elif province in ["四川", "重庆", "贵州", "云南", "西藏", "陕西", 
                            "甘肃", "青海", "宁夏", "新疆"]:
                return "华西"
            elif province in ["香港", "澳门", "台湾"]:
                return "港澳台"
    
    return "未知"


def parse_location_from_cell(cell_text: str) -> str:
    """
    从单元格文本中解析出地点信息
    例如："电信 辽宁大连" -> "辽宁大连"
    """
    # 移除运营商前缀
    text = cell_text.strip()
    for prefix in ["电信", "联通", "移动", "广电"]:
        text = text.replace(prefix, "").strip()
    return text


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
            location_raw = cells[0].get_text(strip=True)
            response_ip = cells[1].get_text(strip=True)
            ip_geo = cells[2].get_text(strip=True)
            loss = cells[3].get_text(strip=True)
            sent = cells[4].get_text(strip=True)
            last_ms = cells[5].get_text(strip=True)
            best_ms = cells[6].get_text(strip=True)
            worst_ms = cells[7].get_text(strip=True)
            avg_ms = cells[8].get_text(strip=True)
            
            # 解析地点
            location = parse_location_from_cell(location_raw)
            
            # 判断是否超时
            is_timeout = last_ms in ("超时", "--", "")
            
            # 转换数值
            loss_pct = None
            sent_count = None
            last_ms_val = None
            best_ms_val = None
            worst_ms_val = None
            avg_ms_val = None
            
            if not is_timeout:
                try:
                    last_ms_val = int(last_ms)
                    best_ms_val = int(best_ms) if best_ms not in ("--", "") else None
                    worst_ms_val = int(worst_ms) if worst_ms not in ("--", "") else None
                    avg_ms_val = int(avg_ms) if avg_ms not in ("--", "") else None
                except ValueError:
                    is_timeout = True
            
            # 解析丢包率
            if loss not in ("--", ""):
                try:
                    loss_pct = int(loss.replace("%", ""))
                except ValueError:
                    pass
            
            # 解析发包数
            if sent not in ("--", ""):
                try:
                    sent_count = int(sent)
                except ValueError:
                    pass
            
            # 判断区域
            region = classify_region(location, ip_geo)
            
            results.append({
                "service": "itdog",
                "location": location,
                "location_raw": location_raw,
                "response_ip": response_ip,
                "ip_geo": ip_geo,
                "region": region,
                "is_timeout": is_timeout,
                "loss_pct": loss_pct,
                "sent": sent_count,
                "last_ms": last_ms_val,
                "best_ms": best_ms_val,
                "worst_ms": worst_ms_val,
                "avg_ms": avg_ms_val,
            })
        except (IndexError, ValueError):
            # Skip malformed rows
            continue
    
    return results


def get_region_summary(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    按区域汇总ping结果
    
    Args:
        results: ping结果列表
    
    Returns:
        区域汇总字典
    """
    regions = {}
    
    for r in results:
        region = r.get("region", "未知")
        if region not in regions:
            regions[region] = {
                "total": 0,
                "timeout_count": 0,
                "latencies": [],
                "loss_pcts": [],
                "locations": []
            }
        
        regions[region]["total"] += 1
        regions[region]["locations"].append(r["location"])
        
        if r.get("is_timeout"):
            regions[region]["timeout_count"] += 1
        else:
            if r.get("last_ms") is not None:
                regions[region]["latencies"].append(r["last_ms"])
        
        if r.get("loss_pct") is not None:
            regions[region]["loss_pcts"].append(r["loss_pct"])
    
    # 计算统计值
    for region, data in regions.items():
        latencies = data["latencies"]
        loss_pcts = data["loss_pcts"]
        
        if latencies:
            data["min_latency"] = min(latencies)
            data["max_latency"] = max(latencies)
            data["avg_latency"] = sum(latencies) / len(latencies)
        else:
            data["min_latency"] = None
            data["max_latency"] = None
            data["avg_latency"] = None
        
        if loss_pcts:
            data["avg_loss"] = sum(loss_pcts) / len(loss_pcts)
            data["has_loss"] = any(p > 0 for p in loss_pcts)
        else:
            data["avg_loss"] = None
            data["has_loss"] = False
        
        # 移除临时列表
        del data["latencies"]
        del data["loss_pcts"]
    
    return regions