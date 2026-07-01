#!/usr/bin/env python3
"""
Audit Layer 3: semantic accuracy via an LLM judge.

Layer 1 (audit.py) proves elements exist; it cannot tell whether the DESCRIPTION
of what an element does is correct. This layer shows a model each drafted page
alongside the ground truth captured at collection time (the screenshot and/or the
page's real DOM text + control labels) and asks it to flag claims that are NOT
supported by that evidence.

Uses the same OpenAI-compatible endpoint as draft.py:
    OPENAI_BASE_URL, OPENAI_API_KEY, DOCS_MODEL
A vision model reads the screenshot; set DOCS_NO_IMAGE=1 for a text-only model
(judges the page against the captured DOM text + labels).

Output: audit/semantic/<id>.json (per screen) and audit/semantic-report.md.

Usage:
    python judge.py                 # judge every screen with a capture + page
    python judge.py home contacts
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
OUT = ROOT / "audit" / "semantic"

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "local")
MODEL = os.environ.get("DOCS_MODEL", "qwen2.5-vl")
NO_IMAGE = os.environ.get("DOCS_NO_IMAGE") == "1"

SCHEMA_HINT = (
    'Respond with ONLY a JSON object: {"accuracy_score": 0-100, '
    '"unsupported_claims": ["..."], "misleading_or_wrong": ["..."], '
    '"notes": "one short sentence"}. '
    "accuracy_score 100 = every claim supported by the evidence; lower it for each "
    "claim the evidence does not support."
)

PROMPT = """You are auditing end-user documentation for accuracy. Below is a drafted \
doc page for a dashboard screen, and the GROUND TRUTH captured from the live screen \
(its visible text and the exact labels of its interactive controls){img}.

Flag only claims in the doc that are NOT supported by the ground truth: invented \
features, wrong descriptions of what a control does, incorrect navigation, or steps \
that reference things not present. Do not flag reasonable phrasing differences.

GROUND TRUTH — control labels:
{controls}

GROUND TRUTH — visible page text:
\"\"\"{text}\"\"\"

DRAFTED DOC PAGE:
\"\"\"{doc}\"\"\"

{schema}"""


def call_model(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "temperature": 0.1}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def extract_json(s: str):
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return {"accuracy_score": None, "unsupported_claims": [], "misleading_or_wrong": [],
                "notes": "could not parse judge output", "_raw": s[:400]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"accuracy_score": None, "unsupported_claims": [], "misleading_or_wrong": [],
                "notes": "invalid JSON from judge", "_raw": m.group(0)[:400]}


def find_page(meta_id, order):
    p = DOCS / f"{str(order).zfill(3)}-{meta_id}.md"
    if p.exists():
        return p
    hits = list(DOCS.glob(f"*-{meta_id}.md"))
    return hits[0] if hits else None


def judge_one(meta, doc_md):
    controls = "\n".join(f"- {c}" for c in meta.get("controls", [])) or "(none)"
    prompt = PROMPT.format(
        img="" if NO_IMAGE else " and a screenshot",
        controls=controls[:4000],
        text=meta.get("text", "")[:5000],
        doc=doc_md[:6000],
        schema=SCHEMA_HINT,
    )
    content = [{"type": "text", "text": prompt}]
    png = CAP / f"{meta['id']}.png"
    if not NO_IMAGE and png.exists():
        b64 = base64.b64encode(png.read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    return extract_json(call_model([{"role": "user", "content": content}]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    metas = sorted(CAP.glob("*.json"), key=lambda p: p.stem)
    metas = [m for m in metas if not args or m.stem in args]
    if not metas:
        print("  No captures found. Run: make capture")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for mp in metas:
        meta = json.loads(mp.read_text())
        page = find_page(meta["id"], meta.get("order", 999))
        if not page:
            continue
        print(f"  judging {meta['id']} ... ", end="", flush=True)
        try:
            v = judge_one(meta, page.read_text())
        except Exception as e:
            print(f"FAILED: {e}")
            continue
        (OUT / f"{meta['id']}.json").write_text(json.dumps(v, indent=2))
        n = len(v.get("unsupported_claims", [])) + len(v.get("misleading_or_wrong", []))
        rows.append((meta["id"], v.get("accuracy_score"), n, v))
        print(f"score={v.get('accuracy_score')} flags={n}")

    rows.sort(key=lambda r: (r[1] is None, r[1] if r[1] is not None else 0))
    lines = ["# Doc Accuracy Audit — Layer 3 (semantic LLM judge)", "",
             f"Model: `{MODEL}`  |  mode: {'text-only' if NO_IMAGE else 'vision'}", "",
             "| Screen | Accuracy | Flags |", "|--------|----------|-------|"]
    for sid, score, n, _ in rows:
        lines.append(f"| {sid} | {score if score is not None else '?'} | {n} |")
    lines.append("")
    for sid, score, n, v in rows:
        flags = (v.get("unsupported_claims") or []) + (v.get("misleading_or_wrong") or [])
        if not flags:
            continue
        lines.append(f"## {sid}  (accuracy {score})")
        if v.get("notes"):
            lines.append(f"_{v['notes']}_")
        lines += [f"- {f}" for f in flags]
        lines.append("")
    (ROOT / "audit" / "semantic-report.md").write_text("\n".join(lines) + "\n")
    print(f"\n  Layer 3 done: {len(rows)} screens judged. Report: audit/semantic-report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
