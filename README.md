# multi-ping

Multi-mode network diagnostic skill. Tests connectivity from your machine and from
100-300+ monitoring points via **ITDOG** (China-focused) or **ping.pe** (global),
covering ICMP ping, TCP ports, website speed, and DNS resolution — over IPv4 or IPv6.

**Tool-agnostic** — works with any AI coding assistant that can execute shell
commands and read files: opencode, Claude Code, WorkBuddy, Codex, Cursor, and more.

## Features

| Mode | Description | Method |
|------|-------------|--------|
| **Local ICMP** | Ping from your machine (IPv4/IPv6) | System `ping` command |
| **Remote ICMP** | Ping from 100-300+ locations | ITDOG or ping.pe (Playwright CLI, headless) |
| **TCP Ping** | Measure TCP handshake latency (IPv4/IPv6) | Raw socket connect |
| **Website Speed** | HTTP/HTTPS response time, DNS/TCP/TLS/TTFB, redirects | `requests` + socket probe |
| **DNS Resolution** | A/AAAA/CNAME/MX/NS/TXT/SOA/PTR/CAA, CNAME chain | `dnspython` + system resolver fallback |

Remote providers:

| Provider | Coverage | Tools |
|----------|----------|-------|
| `itdog` (default) | China-focused, 300+ points | ping / ping_ipv6 / tcping / http / dns |
| `pingpe` | Global, 160+ points (mostly overseas) | ping / ping6 / tcp / tcp6 / dig |

## Quick Start

```bash
# Install dependencies
pip install requests dnspython playwright
playwright install chromium

# Run all tests
python3 scripts/ping.py example.com

# Local ping only
python3 scripts/ping.py example.com --mode local

# Remote multi-location only, JSON output
python3 scripts/ping.py example.com --mode remote --output json

# Global multi-location (ping.pe) instead of ITDOG
python3 scripts/ping.py example.com --mode remote --provider pingpe

# TCP ping specific port (local + remote TCPing)
python3 scripts/ping.py example.com:443 --mode tcp

# HTTPS speed test (local + remote website test)
python3 scripts/ping.py https://example.com --mode web

# DNS resolution test (local + remote)
python3 scripts/ping.py example.com --mode dns --dns-type MX

# IPv6 (dedicated IPv6 tools)
python3 scripts/ping.py example.com --mode remote -6

# Show all remote nodes
python3 scripts/ping.py example.com --show-all
```

## Integrate with your AI assistant

This skill is **not tied to any single tool**. Install it wherever you run
AI-assisted commands:

### opencode

```bash
# Copy the whole skill directory
cp -r ping/ ~/.config/opencode/skills/

# Also install the /ping slash command (shows up when typing / in the TUI)
mkdir -p ~/.config/opencode/commands
cp ~/.config/opencode/skills/ping/commands/ping.md ~/.config/opencode/commands/
```

- `/ping example.com` — runs the skill straight from the command palette
- The skill is also advertised to the agent automatically (via `SKILL.md`)

### Claude Code

```bash
# Copy the whole directory
cp -r ping/ ~/.claude/skills/
```

Claude Code reads `SKILL.md` as a skill definition. Invoke with `@ping example.com`
or naturally.

### WorkBuddy / Cursor / Codex / Others

Copy the `scripts/` directory anywhere and invoke directly:

```bash
python3 /path/to/ping/scripts/ping.py example.com
```

Your assistant will read this README or `SKILL.md` for usage instructions.

## Output Format

### Text Mode (default)

```
  / ping www.baidu.com
  ============================================================

  网络诊断
  ============================================================

  [本机 ICMP]
    10 发 / 10 收
    丢包: 0%
    平均: 21ms
    最快: 21ms
    最慢: 24ms

  [ITDOG 多地点]
    监测点: 306   成功: 304   丢包: 0   超时: 2
    平均: 44ms   最快: <1ms   最慢: 397ms

    区域
    华东        68 节点   平均 17ms
    华北        41 节点   平均 15ms
    华中        33 节点   平均 24ms
    华南        27 节点   平均 20ms
    西南        38 节点   平均 33ms
    西北        31 节点   平均 36ms
    东北        26 节点   平均 28ms
    港澳台       12 节点   平均 41ms
    海外        27 节点   平均 235ms      超时 2

    异常节点
    ! 海外 德国法兰克福                295ms
    ! 海外 南非                    TIMEOUT

  [本机 TCP 443]
    连接成功: 29ms
    最快: 24ms  最慢: 48ms

  [本机 HTTPS 测速]
    HTTP: 200 OK
    DNS: <1ms
    TCP: 25ms
    TLS: 138ms
    TTFB: 486ms
    总耗时: 551ms
    响应大小: 704.8 KB

  [本机 DNS 解析:A]
    响应: 2ms
    - 103.235.46.115
    - 103.235.46.102
    CNAME: www.a.shifen.com -> www.wshifen.com
```

In `--mode tcp`, `--mode web`, and `--mode dns` the matching remote block is
appended (e.g. `[ITDOG TCPing]`, `[ITDOG 网站测速]`, `[ITDOG DNS]`).

### JSON Mode

```bash
python3 scripts/ping.py example.com --output json
```

Returns complete machine-readable data with all nodes, regions, summaries, and
test results.

## CLI Reference

```
usage: ping.py [-h] [--mode {all,local,remote,tcp,web,dns}]
               [--provider {itdog,pingpe,none}] [--count N] [--timeout T]
               [--port N] [--url URL] [--dns-type TYPE] [-4 | -6]
               [--output {text,json}] [--show-all] [--debug]
               host

positional arguments:
  host                  Target host, IP, or URL

options:
  --mode                Test mode: all|local|remote|tcp|web|dns (default: all)
  --provider            Remote provider: itdog|pingpe|none (default: itdog)
  --count N             ICMP packet count (default: 10)
  --timeout T           Timeout in seconds (default: 60)
  --port N              TCP port (default: 443)
  --url URL             Explicit URL for web test
  --dns-type TYPE       DNS record type: A/AAAA/CNAME/MX/NS/TXT/SOA/PTR/CAA (default: A)
  -4, --ipv4            Force IPv4 (default)
  -6, --ipv6            Force IPv6 and use dedicated IPv6 tools
  --output text|json    Output format (default: text)
  --show-all            Show all remote nodes in text output
  --debug               Enable debug output
```

## Mode matrix

| Mode | Local ICMP | Remote ICMP | Local TCP | Remote TCPing | Local Web | Remote Web | Local DNS | Remote DNS |
|------|:---------:|:-----------:|:---------:|:-------------:|:---------:|:----------:|:---------:|:----------:|
| `all` | ✓ | ✓ | ✓ | | ✓ | | ✓ | |
| `local` | ✓ | | | | | | | |
| `remote` | | ✓ | | | | | | |
| `tcp` | | | ✓ | ✓ | | | | |
| `web` | | | | | ✓ | ✓ | | |
| `dns` | | | | | | | ✓ | ✓ |

## How remote testing works

1. Uses the **Playwright CLI** (`playwright cli`, headless) to drive a persistent
   headless Chromium daemon session.
2. Navigates to the provider's tool page / command URL.
3. Submits the subject (fill + click for ITDOG; URL-encoded shortcut for ping.pe).
4. Polls the DOM until the results table is fully rendered.
5. Extracts every node's location, IP, geo and latency with a single `eval` call.

**ITDOG** tools share one page framework (`#host` input + result table). **ping.pe**
maps a command to a subdomain: `ping.pe/HOST`, `ping6.ping.pe/HOST`,
`tcp.ping.pe/HOST:PORT`, `tcp6.ping.pe/HOST:PORT`, `dig.ping.pe/HOST:TYPE`.

**Note:** Playwright is used only for remote data fetching. Local ICMP ping, TCP
ping, website test, and DNS test do not require Playwright.

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

# Or run a live diagnostic as JSON
python3 scripts/ping.py example.com --output json | python -m json.tool
```

## Privacy & Security

- Only performs read-only network tests
- No credentials, tokens, or sensitive data stored
- No SSH, no command execution on remote hosts
- No port scanning (single port only)
- No CAPTCHA bypass — reports and falls back to alternatives
- Playwright runs in headless mode only for remote data fetching

## Limitations

- ITDOG monitoring points are mostly in China; ping.pe is mostly overseas
- ICMP ping timeout does NOT mean HTTP/HTTPS is down (host may block ICMP)
- TCP 443 success does NOT mean the website is fully functional
- HTTP failure and ICMP failure should be analyzed separately
- Remote providers need ~30-90s to collect results from all nodes
- IPv6 remote testing requires the target to have an AAAA record (otherwise the
  provider reports "Unable to resolve")
- DNS record types beyond A/AAAA require `dnspython`

## License

MIT
