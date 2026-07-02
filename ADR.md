# ADR 0001: Packaging the pipeline as an installable CLI

- **Status:** Proposed (plan only — nothing here is implemented yet)
- **Date:** 2026-07-02

## Context

The pipeline is a deliberate two-language hybrid, driven from a Makefile in a
cloned repo:

- **Node (ESM)** for everything that touches a browser: `capture.js`,
  `auth.js`, `verify.js`. Playwright's first-class API is the Node one, and
  `npx playwright install chromium` handles browser provisioning.
- **Python (stdlib-only)** for everything else: `draft.py`, `judge.py`,
  `audit.py`, `openapi.py`, `doctor.py`. Zero pip dependencies means any
  system `python3` works. MkDocs is the one Python extra, isolated in a uv
  venv and only needed for `make serve`/`make build`.

"Clone + `make setup`" works, but "installable by anyone" means a single
install command and a single `dashboard-docs <subcommand>` entry point.

## Options considered

### A. pip package wrapping Node

Publish to PyPI; a Python entry point shells out to the bundled JS.

- Pro: Python users get `pipx install`; MkDocs could become a real dependency.
- Con: inverts the dependency story — the pure-stdlib side (which needs no
  packaging) would carry the packaging, while the side that genuinely needs a
  package manager (Playwright) sits outside pip's reach. The installer still
  has to run `npm install` + browser download out-of-band, so pip alone never
  yields a working tool. Shipping JS inside a wheel is awkward to test.

### B. npm package wrapping Python (recommended)

Publish to npm; a `bin` script dispatches subcommands, running the Python
scripts via `child_process` with the system `python3`.

- Pro: npm already owns the hard dependency (Playwright + Chromium download
  via a `postinstall` hint or first-run prompt), and Node is required no
  matter what. The Python side needs nothing from a package manager — any
  `python3 >= 3.9` runs it as-is, which is exactly what stdlib-only bought us.
  `npx dashboard-docs doctor` becomes the preflight that verifies `python3`
  and (optionally) MkDocs.
- Con: Python users may not expect an npm install; MkDocs remains a
  documented external step (as today).

### C. Single-language rewrite

Rewrite capture in Python (playwright-python) or drafting/audit in Node.

- Pro: one runtime, simplest packaging story.
- Con: highest risk for zero user-visible gain — capture.js encodes hard-won
  behavior (inner-scroll expansion, freeze selectors, login detection) and
  the Python side is small, tested, and dependency-free. A rewrite discards
  working code and its tests to solve a packaging problem that Option B
  solves with a thin shim. Rejected.

## Decision

Option B: an npm package whose `bin` wraps the existing scripts. It is the
smallest change that makes the tool installable, keeps both halves exactly as
they are, and puts the packaging burden on the runtime that already needs it.

## What would have to change

1. `package.json`: drop `"private": true`, add `"bin": {"dashboard-docs": "cli.js"}`
   and a `files` whitelist (scripts, `*.example.yaml`, templates — never
   config/captures).
2. New `cli.js`: subcommand dispatch (`init`, `doctor`, `auth`, `capture`,
   `draft`, `api`, `audit`, `judge`, `verify`, `serve`, `build`) mirroring
   today's Makefile targets; resolves script paths relative to the package
   install, runs in the user's cwd.
3. Path handling: Python/JS scripts read `config.yaml`/`screens.yaml`/output
   dirs from the invoking cwd instead of the repo root (today they assume
   `Path(__file__).parent`).
4. `doctor.py`: check the system `python3` version and MkDocs availability,
   since the venv is no longer guaranteed.
5. Release workflow: extend `release.yml` with an `npm publish` step gated on
   the existing test job (registry publishing is deliberately out of scope
   for 0.1.0).
