---
name: ping
version: "2.0.0"
description: Multi-mode network diagnostic skill - local ICMP, ITDOG multi-location, TCP ping, and website speed test.
argument-hint: "<host> [options]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/citie114514/opencode-ping
repository: https://github.com/citie114514/opencode-ping
author: citie114514
license: MIT
user-invocable: true
---

# /ping

Multi-mode network diagnostic tool. Tests connectivity from your machine and from 100-300+ monitoring points across China and overseas via ITDOG, plus TCP port connectivity and HTTP/HTTPS speed tests.

## When to use

- "Ping example.com from multiple locations"
- "从全国各地 Ping 8.8.8.8"
- "本机 Ping google.com"
- "测 443 端口" / "TCP ping example.com:443"
- "测速 https://example.com"
- User provides a hostname, IP, or URL and wants network diagnostics

## How to invoke

**Step 1 — parse the input.** The skill auto-detects:
- `example.com` → host for ICMP + TCP 443 + HTTPS
- `8.8.8.8` → host for ICMP + TCP (no web test unless `--url` given)
- `example.com:443` → host + port for TCP
- `https://example.com` → URL for web test, host extracted for ICMP/TCP

**Step 2 — run the script:**

```bash
python3 "${SKILL_DIR}/scripts/ping.py" "<host>" [options]
```

**Default behavior** (`--mode all`):
1. Local ICMP ping (10 packets)
2. ITDOG remote ping (all monitoring points)
3. TCP connect test (port 443 or specified)
4. HTTPS speed test (if URL or domain)

**Modes:**
- `--mode all` (default) — all four tests
- `--mode local` — local ICMP only
- `--mode remote` — ITDOG multi-location only
- `--mode tcp` — TCP connect only
- `--mode web` — HTTP/HTTPS speed test only

**Options:**
- `--count N` — ICMP packet count (default: 10)
- `--timeout T` — timeout in seconds (default: 60)
- `--port N` — TCP port (default: 443)
- `--url URL` — explicit URL for web test
- `--output text|json` — output format
- `--show-all` — show all ITDOG nodes in text output
- `--debug` — enable debug output

**Step 3 — read the output.** Text mode shows:
- Local ICMP summary
- ITDOG regional summary with per-region stats
- Abnormal nodes (timeout, loss, high latency)
- TCP connection result
- HTTP/HTTPS speed result

**Step 4 — answer the user.** Present results clearly. Highlight timeouts, packet loss, and high latency. For JSON mode, pass through the full machine-readable output.

## ITDOG data flow

1. GET `https://www.itdog.cn/ping/{host}` to fetch the results page
2. Parse the HTML table (`<table id="simpletable">`) to extract all monitoring points
3. Each row (`<tr class="node_tr">`) contains: location, response IP, loss%, sent count, latency stats
4. All nodes are collected — no truncation, no artificial limits
5. No WebSocket or JavaScript execution required

## Region classification

- **华东**: 上海、江苏、浙江、安徽、福建、江西、山东
- **华北**: 北京、天津、河北、山西、内蒙古
- **华中**: 湖北、湖南、河南
- **华南**: 广东、广西、海南
- **西南**: 四川、重庆、贵州、云南、西藏
- **西北**: 陕西、甘肃、青海、宁夏、新疆
- **东北**: 辽宁、吉林、黑龙江
- **港澳台**: 香港、澳门、台湾
- **海外**: All non-China locations (Asia, Europe, Americas, etc.)

## Node statuses

- `success` — normal response
- `partial_loss` — some packets lost (e.g., sent 10, received 7)
- `timeout` — 100% packet loss (sent 10, received 0)
- `unavailable` — ITDOG monitoring point itself is down
- `error` — parsing or other error

## Dependencies

```
requests
beautifulsoup4
lxml
websocket-client
```

Install: `pip install requests beautifulsoup4 lxml websocket-client`

## Security

- Only performs read-only network tests
- No credentials, tokens, or sensitive data stored
- No SSH, no command execution on remote hosts
- No port scanning (single port only)
- No CAPTCHA bypass — reports and falls back
