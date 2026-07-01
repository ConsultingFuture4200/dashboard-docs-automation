#!/usr/bin/env python3
"""
Turn each captured screen into a grounded markdown doc page.

For every capture/<id>.json it sends the screenshot + the REAL DOM text and
control labels to a vision-capable, OpenAI-compatible model, using a fixed
template so every page is consistent and chatbot-friendly. Output:

    docs/<order>-<id>.md      with the screenshot embedded at the top

Config via environment variables (point these at your local server or any
OpenAI-compatible endpoint):

    OPENAI_BASE_URL   default http://localhost:8000/v1
    OPENAI_API_KEY    default "local" (most local servers ignore it)
    DOCS_MODEL        default the value below; must be VISION-capable

Usage:
    python draft.py                      # draft every captured screen
    python draft.py dashboard-home       # just these ids
    python draft.py --force              # overwrite existing .md (default: skip)

Notes:
  * If your local model is text-only, set DOCS_NO_IMAGE=1 — it will draft from
    the DOM text + control labels alone (less accurate, still useful).
  * Review every page. The draft is ~80%; accuracy is your job before it feeds
    a customer-facing chatbot.
"""
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CAP = ROOT / "capture"
DOCS = ROOT / "docs"


def product_description():
    """Read the product description from config.yaml (one-line value)."""
    try:
        text = (ROOT / "config.yaml").read_text()
        m = re.search(r'^productDescription:\s*"?(.+?)"?\s*$', text, re.M)
        if m:
            return m.group(1).strip()
    except OSError:
        pass
    return "this product's dashboard"


PRODUCT = product_description()

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "local")
MODEL = os.environ.get("DOCS_MODEL", "qwen2.5-vl")  # set to your vision model
NO_IMAGE = os.environ.get("DOCS_NO_IMAGE") == "1"

TEMPLATE = """You are writing end-user documentation for a dashboard screen of \
{product}. The documentation also feeds a support chatbot, so be accurate, \
concrete, and self-contained.

Screen name: {name}
Seed note: {note}
URL: {url}

EXACT visible control labels (use these verbatim; do NOT invent controls):
{controls}

Visible page text:
\"\"\"
{text}
\"\"\"

Write a markdown doc page with EXACTLY these sections and headings:

## What it's for
One or two sentences on the purpose of this screen.

## How to get here
The navigation path to reach this screen.

## Key elements
A markdown table with columns | Element | What it does |. One row per important \
button, field, tab, or control, using the exact labels above.

## Common tasks
Numbered step-by-step instructions for the 2-4 most common things a user does here.

## Troubleshooting
A short bullet list of likely problems on this screen and how to resolve them.

Rules:
- Use ONLY the provided labels and text. If something is unclear, write a brief \
[REVIEW: ...] note instead of guessing.
- Do not output a top-level # title; the page title is added separately.
- Do not wrap the whole response in a code fence.
"""


def build_messages(meta: dict, img_b64: str | None):
    controls = "\n".join(f"- {c}" for c in meta.get("controls", [])) or "(none detected)"
    prompt = TEMPLATE.format(
        product=PRODUCT,
        name=meta["name"],
        note=meta.get("note", ""),
        url=meta.get("url", ""),
        controls=controls,
        text=meta.get("text", "")[:6000],
    )
    content = [{"type": "text", "text": prompt}]
    if img_b64 and not NO_IMAGE:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        )
    return [{"role": "user", "content": content}]


def call_model(messages) -> str:
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": 0.2}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv[1:]

    metas = sorted(CAP.glob("*.json"), key=lambda p: p.stem)
    if args:
        metas = [p for p in metas if p.stem in args]
    if not metas:
        print("  No captures found. Run: npm run capture")
        return

    DOCS.mkdir(exist_ok=True)
    for mp in metas:
        meta = json.loads(mp.read_text())
        order = str(meta.get("order", 999)).zfill(3)
        out = DOCS / f"{order}-{meta['id']}.md"
        if out.exists() and not force:
            print(f"  skip {meta['id']} (exists; use --force to overwrite)")
            continue

        png = CAP / f"{meta['id']}.png"
        img_b64 = base64.b64encode(png.read_bytes()).decode() if png.exists() else None

        print(f"  drafting {meta['id']} ... ", end="", flush=True)
        try:
            md = call_model(build_messages(meta, img_b64))
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        # Copy the screenshot into docs/img/ so MkDocs serves it (it only serves
        # files inside docs/), and reference it relatively.
        img_dir = DOCS / "img"
        img_dir.mkdir(exist_ok=True)
        if png.exists():
            (img_dir / f"{meta['id']}.png").write_bytes(png.read_bytes())
        page = f"# {meta['name']}\n\n![{meta['name']}](img/{meta['id']}.png)\n\n{md}\n"
        out.write_text(page)
        print(f"wrote {out.name}")

    print("\n  Review the drafts in docs/, then: mkdocs serve\n")


if __name__ == "__main__":
    main()
