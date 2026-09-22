---
name: ping
version: "2.2.0"
description: Multi-mode network diagnostic skill - local ICMP, TCP ping (tcpping), website speed test, DNS resolution, IPv4/IPv6, plus remote multi-location testing from 100-300+ monitoring points via ITDOG and ping.pe. Works with any AI coding assistant (opencode, Claude Code, WorkBuddy, etc.).
argument-hint: "<host> [options]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/citie114514/opencode-ping
repository: https://github.com/citie114514/opencode-ping
author: citie114514
license: MIT
user-invocable: true
---

# /ping

Multi-mode network diagnostic tool. Tests connectivity **from your machine** (local ICMP
ping, TCP ping, website speed, DNS resolution) **and from 100-300+ monitoring points**
(multi-location ICMP, TCPing, website, and DNS) via **ITDOG** (China-focused) or
**ping.pe** (global), over IPv4 or IPv6.

## When to use

- User wants to test network latency to a server from multiple locations / ISPs.
- "Ping example.com from multiple locations" or "从全国各地 Ping 8.8.8.8"
- "本机 Ping google.com" — local ICMP test
- "Test TCP port" / "TCP ping example.com:443" / "测一下 443 端口通不通"
- "Website speed test" / "测速 https://example.com" / "网站打开慢"
- "Check DNS records" / "DNS 解析测试" / "解析一下这个域名"
- "Use IPv6" / "IPv6 ping" — force the dedicated IPv6 tools
- User provides a hostname, IP, or URL and wants network diagnostics

## How to invoke

**Step 1 — parse the user input.** The skill auto-detects:
- `example.com` → host used for ICMP + TCP 443 + HTTPS + DNS
- `8.8.8.8` → host for ICMP + TCP (no web test unless `--url` is given)
- `example.com:443` → host + port for TCP ping
- `https://example.com` → URL for the web speed test; host is extracted for ICMP/TCP
- `2606:4700::6811:dfe3` or `[2606:4700::6811:dfe3]:443` → IPv6 literal (no name resolution)

**Step 2 — run the script.** Pass the host verbatim:

```bash
python3 "${SKILL_DIR}/scripts/ping.py" "<host>" [options]
```

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux.
On **Windows**, substitute `python` — the `python3` command on Windows is usually the
Microsoft Store stub and will not run the script. `SKILL_DIR` is the absolute path of
the directory containing this `SKILL.md` (the scripts are its direct sibling at
`SKILL_DIR/scripts/ping.py`), so set it from the path your harness reported when the
file was read.

**Default behavior** (`--mode all`):
1. Local ICMP ping (10 packets)
2. Remote multi-location ICMP ping (ITDOG by default)
3. Local TCP connect test (port 443 or specified)
4. Local HTTPS speed test (DNS/TCP/TLS/TTFB phases)
5. Local DNS resolution (A record)

**Modes** (`--mode`):
- `all` (default) — local ICMP + remote ICMP + local TCP + local web + local DNS
- `local` — local ICMP only
- `remote` — remote multi-location ICMP only
- `tcp` — local TCP + remote multi-location TCPing
- `web` — local website speed test + remote multi-location website test
- `dns` — local DNS resolution + remote multi-location DNS lookup

**Providers** (`--provider`, default `itdog`):

| Provider | Coverage | Tools |
|----------|----------|-------|
| `itdog` (default) | China-focused, 300+ points | ping / ping_ipv6 / tcping / http / dns |
| `pingpe` | Global, 160+ points (mostly overseas) | ping / ping6 / tcp / tcp6 / dig |
| `none` | — | skip remote testing (local only) |

Note: `ping.pe` has no website speed tool; use `--provider itdog` for `--mode web`.

**IPv6** (`-6` / `--ipv6`): forces every test over IPv6 and uses each provider's
dedicated IPv6 tools — ITDOG `/ping_ipv6/`, `ping6.ping.pe`, `tcp6.ping.pe`. The target
must have an AAAA record for remote IPv6 tests.

**Options:**
- `--count N` — number of ICMP packets (default: 10)
- `--timeout T` — timeout in seconds (default: 60)
- `--port N` — TCP port (default: 443)
- `--url URL` — explicit URL for the web speed test
- `--dns-type TYPE` — DNS record type: `A`/`AAAA`/`CNAME`/`MX`/`NS`/`TXT`/`SOA`/`PTR`/`CAA` (default: `A`)
- `--output text|json` — output format (default: text)
- `--show-all` — show all remote nodes in text output
- `-4, --ipv4` — force IPv4 (default)
- `-6, --ipv6` — force IPv6 and use dedicated IPv6 tools
- `--debug` — enable debug output

**Examples:**

```bash
python3 scripts/ping.py example.com                                        # full diagnostic
python3 scripts/ping.py 8.8.8.8 --mode remote                              # ITDOG multi-location
python3 scripts/ping.py example.com --mode remote --provider pingpe        # global multi-location
python3 scripts/ping.py example.com --mode tcp --port 443                  # local + remote TCPing
python3 scripts/ping.py https://example.com --mode web                     # local + remote speed test
python3 scripts/ping.py example.com --mode dns --dns-type MX               # DNS MX records
python3 scripts/ping.py example.com --mode dns --dns-type AAAA -6          # IPv6 DNS lookup
python3 scripts/ping.py example.com --mode remote -6                       # dedicated IPv6 tools
python3 scripts/ping.py example.com --provider none -c 5                   # local only
```

On **Windows**, replace `python3` with `python` in every example above.

**Step 3 — read the output.** The script prints structured summaries:
- **Local ICMP** — packets sent / received, packet loss, avg / min / max latency
- **Remote multi-location** — monitoring points, success count, regional summary (per-region nodes and average latency), abnormal nodes
- **Local TCP** — connection result and latency; **remote TCPing** per location
- **Local website speed** — HTTP status, DNS / TCP / TLS / TTFB phase timings, total time, response size; **remote** per-location results
- **Local DNS** — response time, answer records, CNAME chain; **remote** per-location dig results

**Step 4 — answer the user.** Present the results clearly and concisely. Highlight
timeouts, packet loss, and high latency. For JSON mode, pass through the complete
machine-readable output.

## How it works

1. **Local tests** run directly on your machine: system `ping` for ICMP, raw socket
   connect for TCP, `requests` + socket probe for website speed, `dnspython` (or system
   resolver fallback) for DNS — no browser required.
2. **Remote tests** use the **Playwright CLI** (`playwright cli`, headless) to drive a
   persistent headless Chromium daemon session.
3. Navigate to the provider's tool page / command URL — ITDOG form pages, or ping.pe
   URL shortcuts (`ping.pe/HOST`, `tcp.ping.pe/HOST:PORT`, `dig.ping.pe/HOST:TYPE`).
4. Submit the subject (fill + click for ITDOG; URL-encoded shortcut for ping.pe) and
   poll the DOM until the results table is fully rendered (~30-90s for 100-300+ nodes).
5. Extract every node's location, IP, geo, and latency with a single `eval` call;
   aggregate and classify by region.

## Supported services

- **ITDOG** (itdog.cn) — Chinese service with 300+ monitoring points across China and
  some international locations. Tools: ping, IPv6 ping, TCPing, HTTP speed, DNS lookup.
- **Ping.pe** — global service with 160+ monitoring points worldwide (mostly overseas).
  Tools: ping, ping6, TCP, TCP6, dig.

## Dependencies

- Python 3.8+
- `requests` — local website speed test
- `dnspython` — DNS record types beyond A/AAAA (optional; without it, local lookups fall
  back to the system resolver for A/AAAA)
- `playwright` — provides the `playwright cli` headless browser driver (required only
  for remote multi-location tests)

Install:
```bash
pip install requests dnspython playwright
playwright install chromium
```

## Limitations

- ITDOG monitoring points are mostly in China; ping.pe is mostly overseas.
- ICMP ping timeout does NOT mean HTTP/HTTPS is down (host may block ICMP).
- TCP 443 success does NOT mean the website is fully functional.
- Remote providers need ~30-90s to collect results from all nodes.
- IPv6 remote testing requires the target to have an AAAA record (otherwise the provider
  reports "Unable to resolve").
- DNS record types beyond A/AAAA require `dnspython`.
- Some services may have rate limits or require CAPTCHA for frequent requests; the skill
  reports this and falls back to alternatives.

## Security & Permissions

**What this skill does:**
- Performs read-only network diagnostics (ICMP, TCP connect, HTTP(S) speed, DNS lookups)
  against the target host.
- Sends HTTP requests to third-party monitoring services (ITDOG, ping.pe) with the target
  host.
- Runs Playwright in headless mode only for remote data fetching.
- Does NOT execute commands on the target host.

**What this skill does NOT do:**
- Does not access private networks or internal hosts without explicit user request.
- Does not require authentication or API keys for basic usage.
- Does not store or transmit sensitive data.
- Does not perform port scanning (single port only) or CAPTCHA bypass.

## Bundled scripts

- `scripts/ping.py` — main entry point (CLI: modes, providers, IPv6, output)
- `scripts/local_ping.py` — local ICMP ping (system `ping`, IPv4/IPv6)
- `scripts/tcp_ping.py` — local TCP connect timing
- `scripts/web_test.py` — local website speed test (DNS/TCP/TLS/TTFB)
- `scripts/dns_test.py` — local DNS resolution (`dnspython` + system fallback)
- `scripts/utils.py` — shared data models, host/URL parsing, region classification
- `scripts/services/browser.py` — shared Playwright CLI wrapper for remote providers
- `scripts/services/itdog/client.py` — ITDOG adapter (ping / ping_ipv6 / tcping / http / dns)
- `scripts/services/pingpe/client.py` — ping.pe adapter (ping / ping6 / tcp / tcp6 / dig)

Review scripts before first use to verify behavior.