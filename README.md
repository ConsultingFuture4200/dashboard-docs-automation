# Dashboard Docs Automation

Generate end-user documentation for a web dashboard automatically: real screenshots and grounded, LLM-written explanations for every screen, plus an API reference built from the app's OpenAPI spec. The output is a searchable [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site whose Markdown doubles as a knowledge base for a support chatbot (RAG).

The mechanical work (capturing every screen, drafting first-pass prose, assembling the site) is automated. You supply a list of screens and a review pass.

## Features

- **Full-screen capture** with [Playwright](https://playwright.dev): screenshot plus the page's real DOM text and control labels, so drafts use your actual button and field names instead of guessing from pixels.
- **Inner-scroll aware**: expands panels that scroll independently of the page body, freezes persistent side rails, and caps very tall list/log pages.
- **LLM drafting** against any OpenAI-compatible endpoint (local or hosted), grounded on the captured labels. Vision models read the screenshot directly; text-only models draft from the DOM.
- **API reference** generated directly from an OpenAPI spec: exact, no LLM, regenerates instantly.
- **Markdown-first**: the same files render the docs site and feed a chatbot's retrieval index.

## How it works

```
SCREENS:  screens.yaml -> capture.js -> capture/*.png + *.json -> draft.py -> docs/NNN-*.md --.
          (screen list)   (Playwright)   (shot + DOM labels)      (LLM)       (review)         |--> mkdocs
API:      /openapi.json -----------------> openapi.py ----------> docs/900-api-reference.md ---'    (site + RAG)
          (live spec)                       (exact, no LLM)
```

| Stage | Tool | Automated |
| --- | --- | --- |
| List screens | `screens.yaml` | Manual (the one file you maintain) |
| Log in, if needed | `auth.js` | One-time interactive |
| Screenshot + DOM capture | `capture.js` | Yes |
| Draft per-screen pages | `draft.py` | Yes (LLM), then you review |
| API reference | `openapi.py` | Yes, from the spec |
| Build and search | MkDocs Material | Yes |

## Getting started

### Prerequisites

- [Node.js](https://nodejs.org) 18+
- [uv](https://docs.astral.sh/uv/) (for the Python tooling and MkDocs)
- An OpenAI-compatible LLM endpoint (a local server such as vLLM or llama.cpp works)

### Install

```bash
make setup                          # Node deps + Playwright Chromium + MkDocs (in a uv venv)
cp config.example.yaml config.yaml
cp screens.example.yaml screens.yaml
```

Edit `config.yaml` (set `baseUrl` and whether the app needs auth) and list your screens in `screens.yaml`.

### Run

```bash
make auth                           # optional: save a login session if the app requires it
make capture                        # screenshot + DOM capture of every screen

OPENAI_BASE_URL=http://localhost:8000/v1 DOCS_MODEL=your-model make draft

make api                            # optional: API reference from the OpenAPI spec
make serve                          # preview at http://127.0.0.1:8000
```

> [!TIP]
> A vision-capable model produces the best pages because it reads the screenshot. With a text-only model, run `DOCS_NO_IMAGE=1 python draft.py` to draft from the captured DOM text and labels alone.

## Configuration

`config.yaml` controls capture and drafting. The most useful keys:

| Key | Purpose |
| --- | --- |
| `baseUrl` | Root URL of the running dashboard |
| `auth` | `true` to require a saved login session, `false` for open apps |
| `expandScroll` | Grow inner-scrolling panels to full height before shooting |
| `freezeSelectors` | CSS selectors of side panels to pin so they don't inflate every page |
| `maxHeightPx` | Cap screenshot height so long lists stay doc-sized |
| `openapiUrl` | OpenAPI spec URL for the API reference (optional) |
| `productDescription` | One line injected into the drafting prompt so pages describe the right product |

Screens are defined in `screens.yaml`, one entry per screen with the steps to reach it (`goto`, `click`, `fill`, `waitFor`, and more). Path-routed SPAs usually need a single `goto`; nav-only apps use `click` steps.

## Pointing at a model

`draft.py` talks to any OpenAI-compatible `/chat/completions` endpoint:

```bash
export OPENAI_BASE_URL=http://localhost:8000/v1   # your server
export OPENAI_API_KEY=local                        # most local servers ignore this
export DOCS_MODEL=your-vision-model
python draft.py
```

## Feeding a support chatbot

The generated `docs/*.md` files are plain Markdown. Point a RAG pipeline at the `docs/` folder so the chatbot answers from the exact source your users read.

> [!WARNING]
> Screenshots and captured DOM can contain real user data (names, emails, list contents). `capture/`, `docs/img/`, generated `docs/NNN-*.md`, and `site/` are gitignored so they are never committed. If you host the site, gate it behind authentication or redact PII first.

## Commands

All steps are wrapped in the `Makefile`:

```
make setup     Node + Python deps + browser
make auth      one-time login, saves a session
make capture   screenshot + DOM capture every screen
make draft     LLM-draft a page per screen
make api       API reference from the OpenAPI spec
make serve     preview the docs site
make build     build the static site into ./site
make deploy    build and deploy ./site to Vercel
```
