# Contributing

## Dev setup

```bash
make setup    # Node deps + Playwright Chromium + Python venv (uv)
```

The codebase is intentionally plain: stdlib-only Python scripts and ESM Node
scripts, no frameworks. Match that style — prefer small surgical changes over
abstractions.

## Running tests

```bash
make test                                      # Python unit tests (no network needed)
node --check capture.js verify.js auth.js config-check.js   # syntax-check touched JS
```

Tests must not require the dashboard, a tunnel, or an LLM endpoint.

## Privacy rule (the important one)

Captured screenshots and DOM dumps can contain **real user data / PII**. These
paths are gitignored and must never be committed:

`config.yaml`, `screens.yaml`, `auth.json`, `capture/`, `docs/img/`, generated
`docs/NNN-*.md`, `audit/`, `site/`, `*.log`

Run `git status` before committing; if any of these show up staged, stop and
unstage them. App-agnostic templates go in the `.example` files instead.

## Commit style

- Imperative, descriptive subject line (e.g. "Add retry to LLM calls").
- One logical change per commit.
- Make sure `make test` passes before committing.
