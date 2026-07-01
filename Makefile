# Convenience wrapper for the whole pipeline.
#
#   make setup     install Node + Python deps + the browser
#   make auth      one-time interactive SSO login (saves the session)
#   make capture   screenshot + DOM-capture every screen in screens.yaml
#   make draft     LLM-draft a markdown page per captured screen
#   make serve     preview the docs site locally
#   make build     build the static site into ./site
#   make all       capture -> draft -> serve

.PHONY: setup tunnel auth capture draft api serve build deploy all test

setup:
	npm install
	npx playwright install chromium
	uv venv .venv
	uv pip install -p .venv/bin/python -r requirements.txt

# Open an SSH local-forward if your dashboard is only reachable on a remote host.
# Edit HOST/PORT for your setup, then set baseUrl to the forwarded localhost port.
TUNNEL_LOCAL ?= 9200
TUNNEL_REMOTE ?= 127.0.0.1:9200
TUNNEL_HOST ?= user@host
tunnel:
	ssh -N -L $(TUNNEL_LOCAL):$(TUNNEL_REMOTE) $(TUNNEL_HOST)

auth:
	npm run auth

capture:
	npm run capture

draft:
	python draft.py

# Auto-generate the API reference page from the live OpenAPI spec.
api:
	python openapi.py

serve:
	.venv/bin/mkdocs serve

build:
	.venv/bin/mkdocs build

test:
	python3 -m unittest discover -s tests -t . -v

# Deploy the prebuilt static site/ to Vercel as a plain static site.
# We deploy site/ (not the repo root) so Vercel does NOT see package.json and
# try to build it as a Node/Playwright app — it just hosts the static files.
# Requires `vercel login` once. This site contains real PII, so enable
# protection in the Vercel dashboard (Settings > Deployment Protection):
# Vercel Authentication on Hobby (free, owner-only), Password Protection on Pro.
deploy: build
	cd site && vercel deploy --prod

# Full run: screens -> drafts -> API reference -> preview.
# (Requires `make tunnel` open in another terminal.)
all: capture draft api serve
