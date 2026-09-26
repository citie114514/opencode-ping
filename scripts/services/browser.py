"""
Shared Playwright CLI plumbing for remote multi-location adapters.

Both the ITDOG and ping.pe adapters drive a headless Chromium through the
`playwright cli` command (a separate subprocess call per action against a
persistent daemon session).
"""

import json
import os
import subprocess

PLAYWRIGHT_CLI = os.environ.get("PLAYWRIGHT_CLI", "playwright")
# Some environments only ship the npm `playwright-cli` binary, where subcommands
# follow the executable directly with no `cli` layer. Set PLAYWRIGHT_CLI_SUBCMD=""
# to omit that layer, e.g.
#   PLAYWRIGHT_CLI=playwright-cli PLAYWRIGHT_CLI_SUBCMD= python scripts/ping.py ...
PLAYWRIGHT_CLI_SUBCMD = os.environ.get("PLAYWRIGHT_CLI_SUBCMD", "cli")


class BrowserError(Exception):
    """Raised when a playwright cli command fails."""


def run_cli(args, timeout=180):
    """Run a `playwright cli` subcommand and return its raw stdout."""
    cmd = [PLAYWRIGHT_CLI]
    if PLAYWRIGHT_CLI_SUBCMD:
        cmd.append(PLAYWRIGHT_CLI_SUBCMD)
    cmd += list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise BrowserError(
            f"playwright cli {' '.join(args[:2])} failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def eval_json(js):
    """Evaluate JS on the page and return the parsed JSON value.

    The CLI's `--raw` output is itself a JSON-encoded string, so decode twice:
    first the outer JSON string literal, then the inner JSON payload.
    """
    out = run_cli(["eval", js, "--raw"])
    if not out:
        return None
    try:
        return json.loads(json.loads(out))
    except (json.JSONDecodeError, TypeError):
        return None


def open_browser():
    """Ensure a fresh headless browser session is running."""
    run_cli(["kill-all"], timeout=30)
    run_cli(["open"], timeout=60)


def close_browser():
    """Close the browser session (best effort)."""
    try:
        run_cli(["close"], timeout=30)
    except Exception:  # noqa: BLE001
        pass


def host_for_url(host):
    """Wrap a bare IPv6 literal in brackets for use in URLs / host:port strings."""
    if host.startswith("[") or ":" not in host:
        return host
    return f"[{host}]"
