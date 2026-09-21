---
name: ping
version: "2.1.0"
description: Multi-mode network diagnostic skill - local ICMP, TCP ping, website speed test, DNS resolution, IPv4/IPv6, plus remote multi-location testing via ITDOG and ping.pe. Works with any AI coding assistant (opencode, Claude Code, WorkBuddy, etc.).
argument-hint: "<host> [options]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/citie114514/opencode-ping
repository: https://github.com/citie114514/opencode-ping
author: citie114514
license: MIT
user-invocable: true
compatible-tools:
  - opencode
  - claude-code
  - workbuddy
---

# /ping

Multi-mode network diagnostic tool. Tests connectivity from your machine and from
100-300+ monitoring points via **ITDOG** (China-focused) or **ping.pe** (global),
covering ICMP ping, TCP ports, website speed, and DNS resolution — over IPv4 or
IPv6.

## When to use

- "Ping example.com from multiple locations"
- "从全国各地 Ping 8.8.8.8"
- "本机 Ping google.com"
- "测 443 端口" / "TCP ping example.com:443"
- "测速 https://example.com" / "网站打开慢"
- "解析一下这个域名" / "查一下 DNS 记录" / "DNS 解析测试"
- "用 IPv6 测一下" / "IPv6 ping"
- User provides a hostname, IP, or URL and wants network diagnostics

## How to invoke

**Step 1 — parse the input.** The skill auto-detects:
- `example.com` → host for ICMP + TCP 443 + HTTPS
- `8.8.8.8` → host for ICMP + TCP (no web test unless `--url` given)
- `example.com:443` → host + port for TCP
- `https://example.com` → URL for web test, host extracted for ICMP/TCP
- `2606:4700::6811:dfe3` or `[2606:4700::6811:dfe3]:443` → IPv6 literal

**Step 2 — run the script:**

```bash
python3 "${SKILL_DIR}/scripts/ping.py" "<host>" [options]
```

**Default behavior** (`--mode all`):
1. Local ICMP ping (10 packets)
2. Remote multi-location ICMP ping (ITDOG by default)
3. Local TCP connect test (port 443 or specified)
4. Local HTTPS speed test (if URL or domain)
5. Local DNS resolution (A record)

**Modes:**
- `--mode all` (default) — local ICMP + remote ICMP + local TCP + local web + local DNS
- `--mode local` — local ICMP only
- `--mode remote` — remote multi-location ICMP only
- `--mode tcp` — local TCP + remote multi-location TCPing
- `--mode web` — local website speed test + remote multi-location website test
- `--mode dns` — local DNS resolution + remote multi-location DNS lookup

**Providers** (`--provider`, default `itdog`):
| Provider | Coverage | Tools |
|----------|----------|-------|
| `itdog` | China-focused (300+ points) | ping / ping_ipv6 / tcping / http / dns |
| `pingpe` | Global (160+ points, mostly overseas) | ping / ping6 / tcp / tcp6 / dig |
| `none` | — | skip remote testing (local only) |

`ping.pe` has no website test; use `--provider itdog` for `--mode web`.

**IPv6** (`-6` / `--ipv6`): switches every test to IPv6 and uses the provider's
dedicated IPv6 tools (`ITDOG /ping_ipv6/`, `ping6.ping.pe`, `tcp6.ping.pe`).

**Options:**
- `--count N` — ICMP packet count (default: 10)
- `--timeout T` — timeout in seconds (default: 60)
- `--port N` — TCP port (default: 443)
- `--url URL` — explicit URL for web test
- `--dns-type TYPE` — DNS record type: `A`/`AAAA`/`CNAME`/`MX`/`NS`/`TXT`/`SOA`/`PTR`/`CAA` (default: `A`)
- `-6, --ipv6` — force IPv6 (and use dedicated IPv6 tools)
- `-4, --ipv4` — force IPv4 (default)
- `--output text|json` — output format
- `--show-all` — show all remote nodes in text output
- `--debug` — enable debug output

**Examples:**

```bash
python3 scripts/ping.py example.com                         # full diagnostic
python3 scripts/ping.py 8.8.8.8 --mode remote               # ITDOG multi-location
python3 scripts/ping.py example.com --mode remote --provider pingpe
python3 scripts/ping.py example.com --mode tcp --port 443   # local + ITDOG TCPing
python3 scripts/ping.py https://example.com --mode web      # local + ITDOG speed
python3 scripts/ping.py example.com --mode dns --dns-type MX
python3 scripts/ping.py example.com --mode dns --dns-type AAAA -6
python3 scripts/ping.py example.com --mode remote -6        # dedicated IPv6 tools
```

**Step 3 — read the output.** Text mode shows:
- Local ICMP summary
- Remote regional summary with per-region stats and abnormal nodes
- Local TCP connection result + remote TCPing
- Local website speed (DNS/TCP/TLS/TTFB breakdown) + remote website speed
- Local DNS answers (+ CNAME chain) + remote DNS results

**Step 4 — answer the user.** Present results clearly. Highlight timeouts, packet
loss, and high latency. For JSON mode, pass through the full machine-readable output.

## Installation (any AI assistant)

This skill is **tool-agnostic** — it works with any AI coding assistant that can
execute shell commands and read files:

- **opencode** — copy to `~/.config/opencode/skills/ping/`
- **Claude Code** — copy to `~/.claude/skills/ping/`
- **WorkBuddy** — copy to the skills directory of your WorkBuddy installation
- **Others** — copy the `scripts/` directory anywhere and call `python3 ping.py <host>`

```bash
pip install requests dnspython playwright
playwright install chromium
```

`dnspython` enables DNS record types beyond `A`/`AAAA` (CNAME/MX/NS/TXT/SOA/PTR/CAA).
Without it the skill still works, but only `A`/`AAAA` local lookups are available.

## Remote data flow

Both remote providers are driven the same way:

1. Use the **Playwright CLI** (`playwright cli`, headless) to drive a headless
   Chromium in a persistent daemon session.
2. Navigate to the provider's tool page / command URL.
3. Submit the subject (fill + click for ITDOG; URL-encoded shortcut for ping.pe).
4. Poll the DOM until the results table is fully rendered.
5. Extract every node's location, IP, geo and latency with a single `eval` call.

**Note:** Playwright is used only for remote data fetching. Local ICMP ping, TCP
ping, website test, and DNS test do not require Playwright.

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
- `unavailable` — monitoring point itself is down
- `error` — parsing or other error

## Dependencies

- Python 3.8+
- `requests` — local website speed test
- `dnspython` — DNS record types beyond A/AAAA
- `playwright` — provides the `playwright cli` headless browser driver (required for remote testing)

```bash
pip install requests dnspython playwright
playwright install chromium
```

## Security

- Only performs read-only network tests
- No credentials, tokens, or sensitive data stored
- No SSH, no command execution on remote hosts
- No port scanning (single port only)
- No CAPTCHA bypass — reports and falls back
- Playwright runs in headless mode only for remote data fetching
