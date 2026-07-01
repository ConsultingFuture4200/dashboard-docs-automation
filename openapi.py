#!/usr/bin/env python3
"""
Generate an API reference page for the docs site directly from the app's live
OpenAPI spec. No screenshots, no LLM — the spec IS the source of truth, so this
is exact and regenerates instantly.

Reads `openapiUrl` from config.yaml, groups the operations by URL prefix (works
even when the spec is untagged), and writes:

    docs/900-api-reference.md

Usage:
    python openapi.py
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"


def load_config():
    try:
        text = (ROOT / "config.yaml").read_text()
    except OSError:
        sys.exit("  No config.yaml found. Copy it first: cp config.example.yaml config.yaml")
    # tiny single-line "key: value" reader so we don't need PyYAML here
    m = re.search(r'^openapiUrl:\s*"?([^"\n]+)"?\s*$', text, re.M)
    return m.group(1).strip() if m else "http://localhost:9200/openapi.json"


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def ref_name(schema):
    """Return a readable type for a schema node (handles $ref, arrays, primitives)."""
    if not isinstance(schema, dict):
        return ""
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if schema.get("type") == "array":
        return f"{ref_name(schema.get('items', {}))}[]"
    if "anyOf" in schema:
        return " | ".join(filter(None, (ref_name(s) for s in schema["anyOf"]))) or "any"
    return schema.get("type", "")


def group_key(path):
    segs = [s for s in path.strip("/").split("/") if s]
    if not segs:
        return "Root"
    if segs[0] == "api" and len(segs) > 1:
        return segs[1].replace("-", " ").title()
    return segs[0].replace("-", " ").title()


def render_operation(method, path, op):
    out = [f"### `{method.upper()} {path}`\n"]
    if op.get("summary"):
        out.append(f"**{op['summary']}**\n")
    if op.get("description"):
        out.append(op["description"].strip() + "\n")

    params = op.get("parameters") or []
    if params:
        out.append("**Parameters**\n")
        out.append("| Name | In | Required | Type |")
        out.append("|------|----|----------|------|")
        for p in params:
            out.append(
                f"| `{p.get('name','')}` | {p.get('in','')} | "
                f"{'yes' if p.get('required') else 'no'} | {ref_name(p.get('schema', {})) or '—'} |"
            )
        out.append("")

    body = op.get("requestBody", {}).get("content", {})
    if body:
        schema = next(iter(body.values()), {}).get("schema", {})
        t = ref_name(schema)
        if t:
            out.append(f"**Request body:** `{t}`\n")

    responses = op.get("responses") or {}
    if responses:
        out.append("**Responses**\n")
        out.append("| Code | Description |")
        out.append("|------|-------------|")
        for code, r in responses.items():
            desc = (r.get("description") or "").replace("\n", " ").strip()
            out.append(f"| {code} | {desc} |")
        out.append("")

    return "\n".join(out)


def main():
    url = load_config()
    try:
        spec = fetch(url)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        sys.exit(f"  Could not fetch the OpenAPI spec from {url}\n  {e}\n"
                 f"  Is the app running / the tunnel open? (see config.yaml openapiUrl)")
    info = spec.get("info", {})
    paths = spec.get("paths", {})

    groups = {}
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            groups.setdefault(group_key(path), []).append((path, method, op))

    lines = [
        "# API Reference",
        "",
        f"Auto-generated from the `{info.get('title','API')}` OpenAPI spec "
        f"(v{info.get('version','?')}). Regenerate with `python openapi.py`.",
        "",
        "!!! info",
        "    This page documents the HTTP API behind the dashboard. For the visual",
        "    screens, see the sections above. Both come from the same live system.",
        "",
    ]

    for group in sorted(groups):
        ops = sorted(groups[group], key=lambda x: (x[0], x[1]))
        lines.append(f"## {group}\n")
        for path, method, op in ops:
            lines.append(render_operation(method, path, op))

    DOCS.mkdir(exist_ok=True)
    out = DOCS / "900-api-reference.md"
    out.write_text("\n".join(lines).rstrip() + "\n")
    total = sum(len(v) for v in groups.values())
    print(f"  Wrote {out.name}: {total} operations across {len(groups)} groups.")


if __name__ == "__main__":
    main()
