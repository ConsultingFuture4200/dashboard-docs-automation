# Dashboard Docs Automation

Automatically generate end-user documentation for a web dashboard: real
screenshots + grounded, LLM-drafted explanations for every screen, plus an API
reference generated from the app's OpenAPI spec. Published as a searchable
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site whose markdown
doubles as a knowledge base for a support chatbot (RAG).

Two automated tracks:

```
SCREENS:  screens.yaml ─► capture.js ─► capture/*.png+json ─► draft.py ─► docs/NNN-*.md ─┐
          (screen list)   (Playwright)   (shot + DOM)         (LLM, review)               ├─► mkdocs
API:      /openapi.json ───────────────► openapi.py ───────► docs/900-api-reference.md ──┘  (site + RAG)
          (live spec)                     (exact, no LLM)
```

## What's automated vs. manual

| Stage | Tool | Automated? |
|-------|------|------------|
| List screens | `screens.yaml` | Manual (one file you maintain) |
| Log in (if needed) | `auth.js` | One-time interactive |
| Screenshot + DOM capture | `capture.js` | Fully automated |
| Draft per-screen prose | `draft.py` | Automated (LLM), then you review |
| API reference | `openapi.py` | Fully automated from the spec |
| Build/search site | MkDocs Material | Fully automated |

The LLM drafts get you ~80%. **Review every page before it feeds a customer-facing
chatbot** — that human pass is where accuracy comes from.

## Setup

```bash
make setup                       # Node deps + Playwright Chromium + MkDocs (in a uv venv)
cp config.example.yaml config.yaml
cp screens.example.yaml screens.yaml
```

Then edit `config.yaml` (baseUrl, auth) and list your screens in `screens.yaml`.

## Run the pipeline

```bash
# 1. (Optional) if the app needs a login, save a session once:
make auth

# 2. Capture every screen (screenshot + DOM text + control labels):
make capture

# 3. Draft a markdown page per screen with an LLM (see "Model" below):
OPENAI_BASE_URL=http://localhost:8000/v1 DOCS_MODEL=your-model make draft

# 4. (Optional) generate the API reference from the app's OpenAPI spec:
make api

# 5. Review docs/*.md, then preview:
make serve                       # http://127.0.0.1:8000
```

## Pointing draft.py at a model

`draft.py` talks to any OpenAI-compatible `/chat/completions` endpoint:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1   # your server (vLLM, llama.cpp, OpenAI, ...)
export OPENAI_API_KEY=local                        # most local servers ignore this
export DOCS_MODEL=your-vision-model                # a VISION model gives the best prose
python draft.py
```

Vision-capable models read the screenshot directly and produce the best pages.
Text-only model? Run `DOCS_NO_IMAGE=1 python draft.py` to draft from the captured
DOM text + control labels alone (less accurate, still useful).

## Capture notes

- **Inner-scroll dashboards**: many apps scroll a main panel, not the page body,
  so `fullPage` clips content. `expandScroll` grows inner panels to full height;
  `freezeSelectors` pins persistent side panels so they don't inflate every page;
  `maxHeightPx` caps very tall list/log pages.
- **SPAs**: path-routed apps reach each screen with a single `goto`. For nav-only
  routing, use `click` steps in `screens.yaml`.

## Feeding a support chatbot

The `docs/*.md` files are plain markdown. Point your RAG ingestion at `docs/` so
the chatbot answers from the exact same source humans read.

## Privacy

Screenshots and captured DOM can contain real user data (names, emails, contents
of lists). `capture/`, `docs/img/`, generated `docs/NNN-*.md`, and `site/` are
gitignored so they aren't committed. If you host the site, gate it (auth or
password protection) or redact PII first.

## Files

| File | Purpose |
|------|---------|
| `config.example.yaml` | Template → copy to `config.yaml` (gitignored) |
| `screens.example.yaml` | Template → copy to `screens.yaml` (gitignored) |
| `auth.js` | One-time interactive login → `auth.json` |
| `capture.js` | Playwright capture of screenshots + DOM text + labels |
| `draft.py` | LLM drafts one markdown page per screen |
| `openapi.py` | API reference page from an OpenAPI spec |
| `mkdocs.yml` | Docs site config (Material theme, auto nav, search) |
| `Makefile` | `setup / auth / capture / draft / api / serve / build / deploy` |

## License

MIT
