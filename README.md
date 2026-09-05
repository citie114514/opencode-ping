# opencode-ping

Multi-mode network diagnostic skill for [opencode](https://opencode.ai). Tests connectivity from your machine and from 100-300+ monitoring points across China and overseas via ITDOG, plus TCP port connectivity and HTTP/HTTPS speed tests.

## Features

| Mode | Description | Method |
|------|-------------|--------|
| **Local ICMP** | Ping from your machine | System `ping` command |
| **ITDOG Remote** | Ping from 100-300+ locations across China & overseas | WebSocket to ITDOG |
| **TCP Ping** | Measure TCP handshake latency | `socket.create_connection()` |
| **Website Speed** | HTTP/HTTPS response time, TTFB, redirects | `requests` library |

## Quick Start

```bash
# Install dependencies
pip install requests beautifulsoup4 lxml websocket-client

# Run all tests
python3 scripts/ping.py example.com

# Local ping only
python3 scripts/ping.py example.com --mode local

# ITDOG remote only, JSON output
python3 scripts/ping.py example.com --mode remote --output json

# TCP ping specific port
python3 scripts/ping.py example.com:443 --mode tcp

# HTTPS speed test
python3 scripts/ping.py https://example.com --mode web

# Show all ITDOG nodes
python3 scripts/ping.py example.com --show-all
```

## Output Format

### Text Mode (default)

```
  / ping example.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [本机 ICMP]
    10 发 / 10 收  丢包: 0%
    平均: 18ms | 最快: 15ms | 最慢: 24ms

  [ITDOG 多地点]
    监测点: 200
    成功: 187  丢包节点: 8  超时: 5
    平均延迟: 45ms  最快: 2ms  最慢: 286ms
    整体丢包: 2.3% (1930/2000)

    区域       节点     成功     丢包     超时     平均延迟
    ────────────────────────────────────────────────────
    华东         42       41       1        0       31ms
    华北         31       28       2        1       48ms
    华中         22       22       0        0       43ms
    华南         35       34       1        0       29ms
    西南         21       19       1        1       57ms
    西北         14       12       1        1       71ms
    东北         13       12       0        1       68ms
    港澳台        8        8       0        0       12ms
    海外         14       13       1        1      143ms

    异常节点:
    ⚠ 北京联通             TIMEOUT
    ⚠ 广州电信             30% LOSS
    ⚠ 成都移动             TIMEOUT
    ⚠ 法兰克福 ISP         186ms HIGH LATENCY

  [TCP 443]
    连接成功: 12ms  (尝试 5 次, 成功 5 次)
    最快: 11ms  最慢: 15ms

  [HTTPS 测速]
    HTTP 200 OK
    TTFB: 86ms  总耗时: 142ms
    响应大小: 12.3 KB  Content-Type: text/html
```

### JSON Mode

```bash
python3 scripts/ping.py example.com --output json
```

Returns complete machine-readable data with all nodes, regions, summaries, and test results.

## CLI Reference

```
usage: ping.py [-h] [--mode {all,local,remote,tcp,web}] [--count N]
               [--timeout T] [--port N] [--url URL]
               [--output {text,json}] [--show-all] [--debug]
               host

positional arguments:
  host                  Target host, IP, or URL

options:
  --mode                Test mode: all|local|remote|tcp|web (default: all)
  --count N             ICMP packet count (default: 10)
  --timeout T           Timeout in seconds (default: 60)
  --port N              TCP port (default: 443)
  --url URL             Explicit URL for web test
  --output text|json    Output format (default: text)
  --show-all            Show all ITDOG nodes in text output
  --debug               Enable debug output
```

## How ITDOG Works

1. Uses Playwright headless browser to navigate to `https://www.itdog.cn/ping/{host}`
2. Waits for JavaScript to fully load all monitoring point results (up to 294 nodes)
3. Parses the HTML table (`<table id="simpletable">`) to extract all node data
4. Extracts metadata from JavaScript variables (`check_node_num`, `time_out_num`)
5. Returns complete results — no truncation, no artificial limits

**Note:** Playwright is used only for ITDOG data fetching. Local ICMP ping, TCP ping, and web tests do not require Playwright.

## Region Classification

| Region | Provinces |
|--------|-----------|
| 华东 | 上海、江苏、浙江、安徽、福建、江西、山东 |
| 华北 | 北京、天津、河北、山西、内蒙古 |
| 华中 | 湖北、湖南、河南 |
| 华南 | 广东、广西、海南 |
| 西南 | 四川、重庆、贵州、云南、西藏 |
| 西北 | 陕西、甘肃、青海、宁夏、新疆 |
| 东北 | 辽宁、吉林、黑龙江 |
| 港澳台 | 香港、澳门、台湾 |
| 海外 | All non-China locations |

## Testing

```bash
# Run unit tests (offline, no network required)
pytest tests/ -v

# Run integration tests (requires network)
pytest tests/ -m integration -v

# Or run specific integration test
python3 scripts/ping.py example.com --output json | python -m json.tool
```

## Privacy & Security

- Only performs read-only network tests
- No credentials, tokens, or sensitive data stored
- No SSH, no command execution on remote hosts
- No port scanning (single port only)
- No CAPTCHA bypass — reports and falls back to alternatives
- Playwright is only used during development for reverse engineering ITDOG's protocol; the final runtime has zero dependency on Playwright, Chromium, or any browser

## Limitations

- ITDOG monitoring points are mostly in China; international coverage is limited
- ICMP ping timeout does NOT mean HTTP/HTTPS is down (host may block ICMP)
- TCP 443 success does NOT mean the website is fully functional
- HTTP failure and ICMP failure should be analyzed separately
- Website speed test measures from your machine only (not multi-location)

## License

MIT
