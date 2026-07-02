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
import sys
from pathlib import Path

import configcheck
import llm

ROOT = Path(__file__).parent
CAP = ROOT / "capture"
DOCS = ROOT / "docs"

PRODUCT = configcheck.read_key("productDescription") or "this product's dashboard"

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "local")
MODEL = os.environ.get("DOCS_MODEL", "qwen2.5-vl")  # set to your vision model
NO_IMAGE = os.environ.get("DOCS_NO_IMAGE") == "1"

TEMPLATE = """You are writing end-user documentation for a dashboard screen of \
{product}. The documentation also feeds a support chatbot, so be accurate, \
concrete, and self-contained.

Screen name: {name}
Seed note: {note}

Visible controls, given as "label (role)". Use only the label text when referring \
to a control; the role in parentheses is context, not part of the name:
{controls}

Visible page text:
\"\"\"
{text}
\"\"\"

Write a markdown doc page with EXACTLY these sections and headings:

## What it's for
One or two sentences on the purpose of this screen.

## How to get here
Describe the in-app navigation to reach this screen — which sidebar or menu items \
a user clicks (e.g. "Open Settings, then Google"). Do NOT write a URL, web address, \
host, or port; users navigate by clicking, not by typing an address.

## Key elements
A markdown table with columns | Element | What it does |. One row per important \
button, field, tab, or control. In the Element column put ONLY the control's \
visible label text (the exact words a user sees) — no surrounding quotation marks, \
no brackets, and no role word. For example, write the row exactly like:
| Restart Gateway | Restarts the gateway service. |

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


def format_control(c: str) -> str:
    """Present a captured control as its bare visible label with the role as a
    parenthetical, e.g. 'button: Restart Gateway' -> 'Restart Gateway (button)'.
    No surrounding quotes: the model copies label decoration verbatim, so keep the
    label undecorated to avoid leaking quotes/prefixes into the docs."""
    if ":" in c:
        role, label = c.split(":", 1)
        return f"{label.strip()} ({role.strip()})"
    return c.strip()


def build_messages(meta: dict, img_b64: str | None):
    controls = "\n".join(f"- {format_control(c)}" for c in meta.get("controls", [])) or "(none detected)"
    prompt = TEMPLATE.format(
        product=PRODUCT,
        name=meta["name"],
        note=meta.get("note", ""),
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
    return llm.chat(BASE_URL, API_KEY, MODEL, messages, temperature=0.2).strip()


def main():
    configcheck.require_config()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv[1:]

    metas_all = sorted(CAP.glob("*.json"), key=lambda p: p.stem)
    metas = metas_all
    if args:
        stems = {p.stem for p in metas_all}
        unknown = [a for a in args if a not in stems]
        if unknown:
            print(f"  Unknown id(s), no capture found, ignored: {', '.join(unknown)}")
        metas = [p for p in metas_all if p.stem in args]
    if not metas:
        print("  No captures found. Run: npm run capture")
        return

    DOCS.mkdir(exist_ok=True)
    failed = 0
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
            print(f"    re-run just this screen: python draft.py {meta['id']}")
            failed += 1
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

    if failed:
        print(f"\n  {failed}/{len(metas)} screens FAILED to draft (see FAILED lines above).\n", file=sys.stderr)
        sys.exit(1)
    print("\n  Review the drafts in docs/, then: mkdocs serve\n")


if __name__ == "__main__":
    main()
