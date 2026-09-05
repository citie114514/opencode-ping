---
name: ping
version: "0.1.0"
description: Ping a host from multiple locations using ITDOG or other free online ping tools. Returns latency statistics from various ISPs and regions.
argument-hint: "<host> [options]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/your-username/opencode-ping
repository: https://github.com/your-username/opencode-ping
author: your-name
license: MIT
user-invocable: true
---

# /ping

Ping a host (domain or IP) from multiple geographic locations and ISPs to measure network latency and packet loss. This skill uses ITDOG's online ping service (or alternative services) to gather results from diverse monitoring points.

## When to use

- User wants to test network latency to a server from multiple locations.
- User asks for "ping from different regions" or "multi-location ping test".
- User provides a hostname or IP address and wants to see response times from various ISPs.

## How to invoke

**Step 1 — parse the user input.** Separate the host (domain or IP) from any options. Example: `/ping example.com --count 10` → host = `example.com`, options = `--count 10`.

**Step 2 — run the ping script.** Pass the host verbatim:

```bash
python3 "${SKILL_DIR}/scripts/ping.py" "<host>"
```

Optional flags:
- `--count N` — number of ping packets to send per monitoring point (default: 10).
- `--timeout T` — timeout in seconds for each ping (default: 5).
- `--service itdog|pingpe|both` — which online service to use (default: itdog).
- `--output json|text` — output format (default: text).

**Step 3 — read the output.** The script prints a summary of ping results from multiple locations, including:
- Fastest and slowest response times
- Average latency
- Packet loss percentage
- Results grouped by ISP/region

**Step 4 — answer the user.** Present the results in a clear, structured way. Highlight any outliers, high latency, or packet loss. If the user asked a specific question, answer it directly.

## How it works

1. The script sends a request to ITDOG's ping service (or alternative) with the target host.
2. ITDOG runs ping tests from its distributed monitoring points across China and globally.
3. The script parses the HTML response to extract latency data from each monitoring point.
4. Results are aggregated and formatted for display.

## Supported services

- **ITDOG** (itdog.cn) — Chinese service with many monitoring points across China and some international locations.
- **Ping.pe** — Global service with monitoring points worldwide.
- **Custom API** — You can add other services by extending the script.

## Dependencies

- Python 3.6+
- `requests` library
- `beautifulsoup4` library (for HTML parsing)
- Optional: `lxml` for faster parsing

Install dependencies:
```bash
pip install requests beautifulsoup4 lxml
```

## Limitations

- Some services may have rate limits or require CAPTCHA for frequent requests.
- Results depend on the availability of the online service.
- Monitoring point locations are fixed by the service provider.
- For ITDOG, most monitoring points are in China; international points are limited.

## Security & Permissions

**What this skill does:**
- Sends HTTP requests to third‑party ping services (ITDOG, Ping.pe, etc.) with the target host.
- Parses HTML responses to extract ping results.
- Does NOT execute any commands on the target host.
- Does NOT store or transmit any sensitive data.

**What this skill does NOT do:**
- Does not perform direct ICMP ping from your machine.
- Does not access any private networks or internal hosts.
- Does not require authentication or API keys for basic usage.

## Bundled scripts

- `scripts/ping.py` — Main entry point that orchestrates the ping test.
- `scripts/services/itdog.py` — ITDOG service adapter.
- `scripts/services/pingpe.py` — Ping.pe service adapter.
- `scripts/utils.py` — Shared utilities.

Review scripts before first use to verify behavior.