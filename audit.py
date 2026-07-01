#!/usr/bin/env python3
"""
Audit generated docs for accuracy against the ground truth captured at collection
time. This is Layer 1 of the audit stack: deterministic, no LLM, no app access.

For each screen it compares the drafted page against `capture/<id>.json` (the
screenshot's DOM text + control labels captured by capture.js) and flags:

  * HALLUCINATED  - an element the docs describe that appears nowhere in the
                    captured page text or controls (likely invented).
  * UNDOCUMENTED  - an interactive control that exists on the page but is not
                    mentioned anywhere in the drafted page (coverage gap).

Ground truth is whatever capture.js stored, so the audit is only as fresh as the
last capture. Re-run `make capture` before auditing to check against the live app.

Output: audit/report.md (summary + per-screen) and audit/audit.json (machine
readable, for CI gating). Prints a summary table.

Usage:
    python audit.py                 # audit every screen with a capture + page
    python audit.py home contacts   # only these ids
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CAP = ROOT / "capture"
DOCS = ROOT / "docs"
OUT = ROOT / "audit"

# Words too generic to treat as evidence of a specific element.
STOP = {"the", "a", "an", "to", "of", "and", "or", "in", "on", "for", "your",
        "this", "that", "view", "page", "screen", "click", "select", "here", "with",
        "button", "buttons", "field", "fields", "list", "lists", "section", "sections",
        "menu", "menus", "icon", "icons", "tab", "tabs", "option", "options",
        "link", "links", "toggle", "toggles", "panel", "panels", "area", "column"}

# Controls appearing on at least this fraction of screens are treated as global
# chrome (nav bar, side rails) and excluded from per-screen coverage.
CHROME_FRACTION = 0.5


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def tokens(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", norm(s)) if t not in STOP and len(t) > 1}


def control_label(c: str) -> str:
    # captured controls look like "button: Restart Gateway" -> "Restart Gateway"
    return c.split(":", 1)[1].strip() if ":" in c else c.strip()


def parse_key_elements(md: str):
    """Extract the Element column from the '## Key elements' markdown table."""
    m = re.search(r"##\s*Key elements\s*\n(.*?)(?:\n##\s|\Z)", md, re.S | re.I)
    if not m:
        return []
    rows = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set(cells[0]) <= {"-", ":", " "}:  # separator row
            continue
        if cells[0].lower() in ("element", "elements"):  # header row
            continue
        rows.append(re.sub(r"`|\*\*", "", cells[0]))  # strip md emphasis/code
    return rows


def _ground_part(part: str, haystack_text: str, control_labels: list) -> bool:
    e = norm(part)
    if not e:
        return True
    if e in haystack_text:  # exact phrase appears on the page
        return True
    et = tokens(part)
    if not et:
        return True  # nothing specific left to check
    for cl in control_labels:  # token overlap with any real control label
        ct = tokens(cl)
        if ct and len(et & ct) / len(et) >= 0.5:
            return True
    present = sum(1 for t in et if re.search(rf"\b{re.escape(t)}\b", haystack_text))
    return present / len(et) >= 0.7


def grounded(element: str, haystack_text: str, control_labels: list) -> bool:
    """Grounded if the whole phrase is grounded, or every significant sub-part is.
    Docs often bundle several controls in one cell ('Simple / Full buttons'), so
    we split on separators and require each part to be real."""
    if _ground_part(element, haystack_text, control_labels):
        return True
    parts = re.split(r"\s*(?:/|,|;|&| and | or )\s*", element)
    parts = [p for p in parts if tokens(p)]
    if len(parts) <= 1:
        return False
    return all(_ground_part(p, haystack_text, control_labels) for p in parts)


def audit_screen(meta: dict, md: str, chrome: set):
    text = norm(meta.get("text", ""))
    labels = [control_label(c) for c in meta.get("controls", [])]
    documented = parse_key_elements(md)

    # Bracketed placeholders ('[Project Name] · [Date]') are the model describing a
    # repeating pattern, not an invented element — report separately, not as halluc.
    templated = [e for e in documented if "[" in e and "]" in e]
    checkable = [e for e in documented if e not in templated]
    hallucinated = [e for e in checkable if not grounded(e, text, labels)]

    # Coverage measures SCREEN-SPECIFIC controls only (global nav/side-rail chrome
    # legitimately isn't documented per page), against the whole drafted page.
    page = norm(md)
    specific = [l for l in labels if tokens(l) and norm(l) not in chrome]
    undocumented = []
    for lab in specific:
        lt = tokens(lab)
        if norm(lab) in page:
            continue
        if sum(1 for t in lt if re.search(rf"\b{re.escape(t)}\b", page)) / len(lt) >= 0.6:
            continue
        undocumented.append(lab)

    n = len(specific)
    coverage = round(100 * (n - len(undocumented)) / n) if n else 100
    return {
        "id": meta["id"],
        "documented_count": len(documented),
        "specific_control_count": n,
        "coverage_pct": coverage,
        "hallucinated": hallucinated,
        "templated": templated,
        "undocumented": undocumented,
        # for verify.js (Layer 2): concrete, checkable documented elements
        "documented": [e for e in checkable if tokens(e)],
    }


def find_page(meta_id: str, order):
    ords = str(order).zfill(3)
    p = DOCS / f"{ords}-{meta_id}.md"
    if p.exists():
        return p
    hits = list(DOCS.glob(f"*-{meta_id}.md"))
    return hits[0] if hits else None


def compute_chrome(all_metas):
    """Normalized control labels that appear on >= CHROME_FRACTION of all screens."""
    import collections
    freq = collections.Counter()
    for mp in all_metas:
        labels = {norm(control_label(c)) for c in json.loads(mp.read_text()).get("controls", [])}
        freq.update(l for l in labels if l)
    threshold = max(3, int(CHROME_FRACTION * len(all_metas)))
    return {l for l, n in freq.items() if n >= threshold}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    all_metas = sorted(CAP.glob("*.json"), key=lambda p: p.stem)
    if not all_metas:
        print("  No captures found. Run: make capture")
        return 0
    chrome = compute_chrome(all_metas)          # from ALL screens, so it's stable
    metas = [m for m in all_metas if not args or m.stem in args]

    results, missing = [], []
    for mp in metas:
        meta = json.loads(mp.read_text())
        page = find_page(meta["id"], meta.get("order", 999))
        if not page:
            missing.append(meta["id"])
            continue
        results.append(audit_screen(meta, page.read_text(), chrome))

    results.sort(key=lambda r: (len(r["hallucinated"]), 100 - r["coverage_pct"]), reverse=True)

    OUT.mkdir(exist_ok=True)
    total_h = sum(len(r["hallucinated"]) for r in results)
    avg_cov = round(sum(r["coverage_pct"] for r in results) / len(results)) if results else 0

    lines = ["# Doc Accuracy Audit — Layer 1 (deterministic)", ""]
    lines.append(f"- Screens audited: **{len(results)}**")
    lines.append(f"- Likely hallucinated elements: **{total_h}**")
    lines.append(f"- Average control coverage: **{avg_cov}%**")
    if missing:
        lines.append(f"- Screens with a capture but no drafted page: {', '.join(missing)}")
    lines.append(f"- Chrome controls excluded from coverage: {len(chrome)} (global nav/side-rail)")
    lines += ["", "_Coverage = screen-specific controls documented. Global chrome excluded._", "",
              "| Screen | Coverage | Hallucinated | Undocumented | Templated |",
              "|--------|----------|--------------|--------------|-----------|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['coverage_pct']}% | {len(r['hallucinated'])} | "
                     f"{len(r['undocumented'])} | {len(r['templated'])} |")
    lines.append("")
    for r in results:
        if not (r["hallucinated"] or r["undocumented"] or r["templated"]):
            continue
        lines.append(f"## {r['id']}  ({r['coverage_pct']}% coverage)")
        if r["hallucinated"]:
            lines.append("**Likely hallucinated (documented, not found on page):**")
            lines += [f"- {e}" for e in r["hallucinated"]]
        if r["templated"]:
            lines.append("**Templated/placeholder descriptions (review for a concrete example):**")
            lines += [f"- {e}" for e in r["templated"]]
        if r["undocumented"]:
            lines.append("**Undocumented screen-specific controls:**")
            lines += [f"- {e}" for e in r["undocumented"][:20]]
            if len(r["undocumented"]) > 20:
                lines.append(f"- ...and {len(r['undocumented']) - 20} more")
        lines.append("")

    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    (OUT / "audit.json").write_text(json.dumps(results, indent=2))

    print(f"\n  Layer 1 audit: {len(results)} screens | {total_h} likely hallucinations | {avg_cov}% avg coverage")
    print(f"  Report: audit/report.md\n")
    print(f"  {'screen':26} {'cov':>5}  halluc  undoc")
    for r in results:
        print(f"  {r['id']:26} {str(r['coverage_pct'])+'%':>5}  {len(r['hallucinated']):>6}  {len(r['undocumented']):>5}")
    # exit non-zero if any hallucinations, so CI can gate on it
    return 1 if total_h else 0


if __name__ == "__main__":
    sys.exit(main())
