# Convenience wrapper for the whole pipeline.
#
#   make setup     install Node + Python deps + the browser
#   make auth      one-time interactive SSO login (saves the session)
#   make capture   screenshot + DOM-capture every screen in screens.yaml
#   make draft     LLM-draft a markdown page per captured screen
#   make serve     preview the docs site locally
#   make build     build the static site into ./site
#   make all       capture -> draft -> api -> serve

.PHONY: setup init doctor tunnel auth capture draft api serve build deploy all test

setup:
	npm install
	npx playwright install chromium
	uv venv .venv
	uv pip install -p .venv/bin/python -r requirements.txt

# Create config.yaml + screens.yaml from the .example templates (skips existing).
init:
	@if [ -f config.yaml ]; then \
		echo "  config.yaml already exists — left untouched"; \
	else \
		cp config.example.yaml config.yaml; \
		echo "  created config.yaml — edit baseUrl, auth, productDescription"; \
	fi
	@if [ -f screens.yaml ]; then \
		echo "  screens.yaml already exists — left untouched"; \
	else \
		cp screens.example.yaml screens.yaml; \
		echo "  created screens.yaml — list your real screens (see QUICKSTART.md)"; \
	fi
	@echo "  then run: make doctor"

# Preflight: check tools, config, and connectivity before running the pipeline.
doctor:
	python3 doctor.py

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
	python3 draft.py

# Auto-generate the API reference page from the live OpenAPI spec.
api:
	python3 openapi.py

# --- Accuracy audits (compare docs to the ground truth captured at collection) ---
# Layer 1: deterministic element cross-check (no LLM, no app access).
audit:
	python3 audit.py

# Layer 3: semantic LLM judge (uses the same endpoint as draft).
judge:
	python3 judge.py

# Layer 2: live verification of navigation + documented elements (needs the app;
# open `make tunnel` first). Runs audit first so it has the documented-element list.
verify: audit
	npm run verify

# Full audit stack. Layer 2 (verify) needs the tunnel open.
audit-all: audit judge verify

serve:
	.venv/bin/mkdocs serve

build:
	.venv/bin/mkdocs build

test:
	python3 -m unittest discover -s tests -t . -v

# Deploy the prebuilt static site/ to Vercel as a plain static site.
# We deploy site/ (not the repo root) so Vercel does NOT see package.json and
# try to build it as a Node/Playwright app — it just hosts the static files.
# Requires `vercel login` once.
#
# WARNING — verified the hard way: on Vercel's free (Hobby) plan the production
# domain <project>.vercel.app CANNOT be protected (Vercel Authentication covers
# it only on paid plans), and Vercel points that domain at the FIRST deployment
# of a new project even without --prod. If your captured screens contain real
# user data, a Hobby deploy makes it PUBLIC. Either use a paid plan with
# Password Protection, redact PII screens first, or host privately instead
# (e.g. `make serve` behind a VPN/tailnet).
#
# This target therefore requires explicit acknowledgement:
#     make deploy DEPLOY_PUBLIC=1
deploy: build
ifndef DEPLOY_PUBLIC
	@echo "Refusing to deploy: the production URL will be PUBLIC on Vercel's free plan."
	@echo "Read the WARNING above this target in the Makefile, then re-run:"
	@echo "    make deploy DEPLOY_PUBLIC=1"
	@exit 1
else
	cd site && vercel deploy --prod
endif

# Full run: screens -> drafts -> API reference -> preview.
# (Requires `make tunnel` open in another terminal.)
all: capture draft api serve
