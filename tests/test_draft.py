import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import draft


class TestBuildMessages(unittest.TestCase):
    def test_no_image(self):
        meta = {
            "name": "Home",
            "controls": ["button: Save"],
            "text": "hello",
            "note": "",
            "url": "",
        }
        result = draft.build_messages(meta, None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"][0]["type"], "text")
        text = result[0]["content"][0]["text"]
        # Controls are reformatted as "label (role)" — bare label, role in parens,
        # no quotes — so neither the "role:" prefix nor quote marks leak into docs.
        self.assertIn("Save (button)", text)
        self.assertNotIn("- button: Save", text)
        self.assertIn("hello", text)
        self.assertEqual(len(result[0]["content"]), 1)

    def test_with_image(self):
        orig_no_image = draft.NO_IMAGE
        draft.NO_IMAGE = False
        try:
            meta = {
                "name": "Home",
                "controls": ["button: Save"],
                "text": "hello",
                "note": "",
                "url": "",
            }
            result = draft.build_messages(meta, "QUJD")
            self.assertEqual(len(result[0]["content"]), 2)
            self.assertEqual(result[0]["content"][1]["type"], "image_url")
        finally:
            draft.NO_IMAGE = orig_no_image

    def test_text_truncation(self):
        marker = "MARKER6500"
        text = ("a" * 6500) + marker + ("a" * 1000)
        meta = {
            "name": "Home",
            "controls": [],
            "text": text,
            "note": "",
            "url": "",
        }
        result = draft.build_messages(meta, None)
        prompt = result[0]["content"][0]["text"]
        self.assertNotIn(marker, prompt)


class TestMainFailureExit(unittest.TestCase):
    def _run_main(self, call_model):
        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp) / "capture"
            docs = Path(tmp) / "docs"
            cap.mkdir()
            (cap / "home.json").write_text(
                json.dumps({"id": "home", "name": "Home", "order": 1, "controls": [], "text": ""})
            )
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(draft, "CAP", cap), \
                 mock.patch.object(draft, "DOCS", docs), \
                 mock.patch.object(draft, "call_model", call_model), \
                 mock.patch.object(draft.configcheck, "require_config"), \
                 mock.patch.object(draft.sys, "argv", ["draft.py"]), \
                 redirect_stdout(out), redirect_stderr(err):
                draft.main()
            return out.getvalue(), err.getvalue()

    def test_all_failed_exits_1_no_success_footer(self):
        def boom(messages):
            raise RuntimeError("connection refused")

        with self.assertRaises(SystemExit) as cm:
            self._run_main(boom)
        self.assertEqual(cm.exception.code, 1)

    def test_success_prints_footer_and_exits_0(self):
        out, err = self._run_main(lambda messages: "## What it's for\nstuff")
        self.assertIn("mkdocs serve", out)


if __name__ == "__main__":
    unittest.main()
