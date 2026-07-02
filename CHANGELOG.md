# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-02

### Added

- **Capture** (`capture.js` + `auth.js`): Playwright screenshots + real DOM
  text/control labels for every screen in `screens.yaml`, with inner-scroll
  expansion, frozen side rails, and height capping.
- **Drafting** (`draft.py` + `llm.py`): one grounded Markdown page per captured
  screen via any OpenAI-compatible LLM endpoint (vision or DOM-only), with
  retry/backoff.
- **API reference** (`openapi.py`): deterministic `docs/900-api-reference.md`
  generated straight from the app's OpenAPI spec.
- **Three-layer accuracy audit**: deterministic element cross-check
  (`audit.py`), live navigation/element verification (`verify.js`), and a
  semantic LLM judge (`judge.py`), each writing a report under `audit/`.
- **Preflight** (`doctor.py` + `configcheck.py`): `make doctor` checks tools,
  config sanity, and connectivity before a run; `make init` scaffolds
  `config.yaml` / `screens.yaml` from the examples.
- **Site**: MkDocs Material config with auto-built nav; `make serve` /
  `make build` / `make deploy` (Vercel static hosting).
- **CI**: GitHub Actions running the Python unit tests, `node --check` on all
  JS, and Python byte-compilation on every push/PR.
- **Docs**: README, QUICKSTART walkthrough, CONTRIBUTING, MIT license.

[0.1.0]: https://github.com/ConsultingFuture4200/dashboard-docs-automation/releases/tag/v0.1.0
