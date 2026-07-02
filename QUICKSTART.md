# Quickstart: clone to your first generated docs page

This is the honest end-to-end path. Budget ~10 minutes, assuming your dashboard
is already running and you have some LLM endpoint (OpenAI, Ollama, vLLM, or
llama.cpp — all covered in step 6).

You need: Node 18+, Python 3.10+, [uv](https://docs.astral.sh/uv/), and a web
dashboard you can reach from this machine.

## 1. Clone and install

```bash
git clone https://github.com/ConsultingFuture4200/dashboard-docs-automation.git
cd dashboard-docs-automation
make setup
```

This installs the Node deps, the Playwright Chromium browser (~150 MB, the slow
part), and a Python venv with MkDocs.

**You should see:** `make setup` finish without errors, and `.venv/bin/mkdocs
--version` print a version.

## 2. Create and edit the two config files

```bash
make init
```

This copies `config.example.yaml → config.yaml` and `screens.example.yaml →
screens.yaml` (skipping any that already exist). Both are gitignored — your
URLs and routes never get committed.

**Edit `config.yaml`:**

- `baseUrl` — the root URL of your running dashboard, e.g. `http://localhost:3000`.
  If the app only runs on another host, open a tunnel first (`make tunnel`, edit
  the `TUNNEL_*` vars in the Makefile) and point `baseUrl` at the forwarded port.
- `auth` — `true` if the app needs a login (you'll run `make auth` once),
  `false` if it's open.
- `productDescription` — one accurate line about what the dashboard does. This
  goes into the LLM prompt; a wrong description makes the model invent features.
- `openapiUrl` — set it if the app serves an OpenAPI spec, otherwise leave blank.

**Edit `screens.yaml` — a worked example of finding your screens:**

Open your dashboard in a normal browser and click through the navigation,
noting the URL for each screen. Say you find:

| Screen | URL after clicking |
|--------|--------------------|
| Home | `http://localhost:3000/` |
| Jobs list | `http://localhost:3000/jobs` |
| Settings | `http://localhost:3000/settings` |

That becomes this `screens.yaml` (paths are relative to `baseUrl`; `waitFor`
is a CSS selector that proves the screen rendered — `#root`, `main`, or any
element you see in devtools):

```yaml
- id: home
  name: "Home"
  order: 10
  note: "Landing screen; overview of recent activity."
  steps:
    - goto: "/"
    - waitFor: "#root"

- id: jobs
  name: "Jobs"
  order: 20
  note: "List of jobs with status and filters."
  steps:
    - goto: "/jobs"
    - waitFor: "#root"

- id: settings
  name: "Settings"
  order: 30
  note: "Settings hub."
  steps:
    - goto: "/settings"
    - waitFor: "#root"
```

Screens that need clicks (modals, tabs) can use `click:`/`fill:` steps — see
the comments in `screens.example.yaml`.

**You should see:** `config.yaml` with your real `baseUrl` and `screens.yaml`
with 2–3 real screens. Start small; add more screens later.

## 3. Preflight

```bash
make doctor
```

**You should see:** all `✓` lines, in particular `baseUrl reachable`. A `!`
warning about `OPENAI_BASE_URL not set` is fine at this point — you set it in
step 6. Any `✗` line tells you exactly what to fix.

## 4. Log in (only if `auth: true`)

```bash
make auth
```

A real browser window opens; log in through your SSO/login flow, then press
Enter in the terminal. The session is saved to `auth.json` (gitignored).

**You should see:** `auth.json` created, and no login screen when capture runs.

## 5. Capture

```bash
make capture
```

Playwright walks every screen in `screens.yaml` and saves a screenshot plus the
real DOM text and control labels.

**You should see:** one line per screen, and `capture/<id>.png` +
`capture/<id>.json` for each. Open a `.png` — it should look like the screen a
user sees, fully loaded. If shots look half-rendered, raise `settleMs` in
`config.yaml`.

## 6. Draft — point `draft.py` at your LLM

`draft.py` talks to any OpenAI-compatible endpoint via three env vars:

| Env var | Meaning | Default |
|---------|---------|---------|
| `OPENAI_BASE_URL` | endpoint base, ending in `/v1` | `http://localhost:8000/v1` |
| `OPENAI_API_KEY` | API key | `local` (local servers ignore it) |
| `DOCS_MODEL` | model name | `qwen2.5-vl` |
| `DOCS_NO_IMAGE` | set `1` for text-only models | unset (send screenshot) |

Pick your provider:

**OpenAI API:**

```bash
OPENAI_BASE_URL=https://api.openai.com/v1 \
OPENAI_API_KEY=sk-your-key \
DOCS_MODEL=gpt-4o-mini \
make draft
```

**Ollama** (serves an OpenAI-compatible API at `/v1`; no key needed):

```bash
ollama pull qwen2.5vl        # a vision model
OPENAI_BASE_URL=http://localhost:11434/v1 \
DOCS_MODEL=qwen2.5vl \
make draft
```

**vLLM or llama.cpp** (self-hosted; `DOCS_MODEL` must match the name your
server reports at `GET /v1/models`):

```bash
# vLLM default port is 8000, llama.cpp (llama-server) default is 8080
OPENAI_BASE_URL=http://localhost:8000/v1 \
DOCS_MODEL=your-served-model-name \
make draft
```

If your model is **text-only** (no vision), add `DOCS_NO_IMAGE=1` — it drafts
from the captured DOM text and labels alone. Less accurate, still useful.

**You should see:** `drafting <id> ... wrote NNN-<id>.md` per screen, then
files in `docs/` each starting with the screenshot and five sections (What
it's for / How to get here / Key elements / Common tasks / Troubleshooting).
A local model takes roughly 30–90 s per screen.

## 7. (Optional) API reference

```bash
make api
```

**You should see:** `docs/900-api-reference.md` generated from your OpenAPI
spec. If your app has no OpenAPI spec, leave `openapiUrl` blank in
`config.yaml` — `make api` then prints `openapiUrl is not set … skipping` and
exits cleanly.

## 8. Serve

```bash
make serve
```

**You should see:** the docs site at http://127.0.0.1:8000 — one nav entry per
screen, screenshots at the top, working search. If a local LLM already occupies
port 8000, run `.venv/bin/mkdocs serve -a 127.0.0.1:8001` instead.

That's the first page. From here: review each draft (they're ~80% right),
add more screens to `screens.yaml`, and see the README for the accuracy-audit
layers (`make audit` / `judge` / `verify`).

## The 3 most likely failures

1. **`✗ config.yaml: "baseUrl" is still the .example placeholder`** (from
   `make doctor` or any script). You edited `config.example.yaml` instead of
   `config.yaml`, or didn't edit at all. Fix: edit `config.yaml` and set your
   real `baseUrl` and `productDescription`.

2. **`baseUrl not reachable`** / capture times out on the first `goto`. The
   dashboard isn't running, or it lives on another host and the tunnel isn't
   open. Fix: confirm you can open `baseUrl` in a normal browser from this
   machine; for remote apps run `make tunnel` in another terminal and point
   `baseUrl` at the forwarded local port.

3. **Draft fails with a 400 error mentioning images/content, or the model
   describes a blank screen.** Your model is text-only — it can't read the
   screenshot. Fix: re-run with `DOCS_NO_IMAGE=1`, or switch `DOCS_MODEL` to a
   vision-capable model.
