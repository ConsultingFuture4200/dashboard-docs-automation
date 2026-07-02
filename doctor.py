#!/usr/bin/env python3
"""
Preflight check for the whole pipeline:  make doctor

One line per check:
  ✓  ok
  ✗  hard failure (missing tool/config) — exits non-zero
  !  warning only (reachability depends on tunnels/servers being up)
"""
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import configcheck

ROOT = Path(__file__).parent
FAILURES = 0


def ok(msg):
    print(f"  ✓ {msg}")


def fail(msg):
    global FAILURES
    FAILURES += 1
    print(f"  ✗ {msg}")


def warn(msg):
    print(f"  ! {msg}")


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired):
        return None


def reachable(url):
    """(ok, detail): any HTTP response (even 401/404) counts as reachable."""
    try:
        urllib.request.urlopen(url, timeout=3)
        return True, ""
    except urllib.error.HTTPError:
        return True, ""
    except OSError as e:
        return False, str(getattr(e, "reason", e))


def main():
    print(f"  dashboard-docs-automation v{(ROOT / 'VERSION').read_text().strip()}")

    # node
    r = run(["node", "--version"])
    if r and r.returncode == 0:
        ok(f"node {r.stdout.strip()}")
    else:
        fail("node not found — install Node 18+, then: make setup")

    # playwright + chromium (resolved from node_modules, checked on disk)
    snippet = (
        "const { chromium } = await import('playwright');"
        "const { existsSync } = await import('node:fs');"
        "const p = chromium.executablePath();"
        "console.log(existsSync(p) ? 'ok' : 'missing ' + p);"
    )
    r = run(["node", "--input-type=module", "-e", snippet])
    if r and r.returncode == 0 and r.stdout.strip() == "ok":
        ok("playwright chromium installed")
    elif r and r.returncode == 0:
        fail(f"playwright chromium browser {r.stdout.strip()} — run: npx playwright install chromium")
    else:
        fail("playwright not installed (node_modules) — run: make setup")

    # mkdocs venv
    if (ROOT / ".venv/bin/mkdocs").exists():
        ok(".venv/bin/mkdocs present")
    else:
        fail(".venv/bin/mkdocs missing — run: make setup")

    # config.yaml (exists + non-placeholder, shared check)
    errs = configcheck.config_errors(ROOT)
    if errs:
        for e in errs:
            fail(e)
    else:
        ok("config.yaml (baseUrl + productDescription set)")

    # screens.yaml (exists + not a verbatim copy of the example)
    screens = ROOT / "screens.yaml"
    if not screens.exists():
        fail("screens.yaml not found. Run: cp screens.example.yaml screens.yaml   # then list your screens")
    elif screens.read_bytes() == (ROOT / "screens.example.yaml").read_bytes():
        fail("screens.yaml is an unedited copy of screens.example.yaml — list your real screens.")
    elif not any(line.split("#", 1)[0].strip() for line in screens.read_text().splitlines()):
        fail("screens.yaml has no screens (empty or all commented out) — add at least one entry (see screens.example.yaml).")
    else:
        ok("screens.yaml present")

    # baseUrl reachable (warning only: needs the app/tunnel up)
    base = configcheck.read_key("baseUrl", ROOT)
    if base and not errs:
        up, detail = reachable(base)
        if up:
            ok(f"baseUrl reachable ({base})")
        else:
            warn(f"baseUrl not reachable ({base}): {detail} — is the app running / tunnel open?")

    # OPENAI_BASE_URL reachable, if set (warning only)
    llm_base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    if llm_base:
        up, detail = reachable(f"{llm_base}/models")
        if up:
            ok(f"OPENAI_BASE_URL reachable ({llm_base})")
        else:
            warn(f"OPENAI_BASE_URL not reachable ({llm_base}): {detail} — is the model server up?")
    else:
        warn("OPENAI_BASE_URL not set — draft/judge will default to http://localhost:8000/v1")

    if FAILURES:
        print(f"\n  {FAILURES} problem(s) found — fix the ✗ lines above.")
        return 1
    print("\n  All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
