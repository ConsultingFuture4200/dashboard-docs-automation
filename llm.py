#!/usr/bin/env python3
"""
Shared OpenAI-compatible chat call for draft.py and judge.py (stdlib only).

Local model servers drop connections, restart, and time out; a single 600s
attempt loses a whole run to one blip. `chat()` retries a bounded number of
times with backoff on timeouts, 5xx responses, and connection errors. 4xx
responses (bad model name, bad request) fail immediately.
"""
import http.client
import json
import time
import urllib.error
import urllib.request

RETRIES = 2      # extra attempts after the first
BACKOFF_S = 5    # first retry delay; doubles each retry
TIMEOUT_S = 600


def chat(base_url, api_key, model, messages, temperature):
    """POST to /chat/completions and return the message content (unstripped)."""
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    last = None
    for attempt in range(RETRIES + 1):
        if attempt:
            wait = BACKOFF_S * 2 ** (attempt - 1)
            print(f"retry {attempt}/{RETRIES} in {wait}s ({last}) ... ", end="", flush=True)
            time.sleep(wait)
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code < 500:
                raise  # client error — retrying won't help
            last = e
        except (http.client.HTTPException, OSError) as e:
            # OSError covers URLError, timeouts, and connection resets.
            last = e
    raise last
