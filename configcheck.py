#!/usr/bin/env python3
"""
Shared config.yaml validation for the Python pipeline scripts (stdlib only).

config.yaml is gitignored and created by copying config.example.yaml, so the two
failure modes are: the file is missing, or a key is still the .example
placeholder. Every script fails with the same actionable message pointing at
the exact key and the cp-from-example step. The Node side (capture.js /
verify.js) does the same via config-check.js.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# key -> substring that proves the value is still the .example placeholder
PLACEHOLDERS = {
    "baseUrl": "your-dashboard.example.com",
    "productDescription": "one-line description of what the dashboard does",
}

CP_HINT = "cp config.example.yaml config.yaml   # then edit baseUrl + productDescription"


def read_key(key: str, root: Path = ROOT) -> str:
    """Best-effort single-line 'key: value' read from config.yaml (no PyYAML)."""
    try:
        text = (root / "config.yaml").read_text()
    except OSError:
        return ""
    m = re.search(rf'^{key}:\s*"?(.+?)"?\s*$', text, re.M)
    return m.group(1).strip() if m else ""


def config_errors(root: Path = ROOT) -> list:
    """Return actionable error strings for config.yaml problems (empty = ok)."""
    if not (root / "config.yaml").exists():
        return [f"config.yaml not found. Run: {CP_HINT}"]
    errs = []
    for key, placeholder in PLACEHOLDERS.items():
        value = read_key(key, root)
        if not value:
            errs.append(f'config.yaml: "{key}" is missing — set it (see config.example.yaml).')
        elif placeholder in value:
            errs.append(f'config.yaml: "{key}" is still the .example placeholder — edit config.yaml and set your real value.')
    return errs


def require_config(root: Path = ROOT):
    """Exit with the shared actionable message if config.yaml is missing/placeholder."""
    errs = config_errors(root)
    if errs:
        for e in errs:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
