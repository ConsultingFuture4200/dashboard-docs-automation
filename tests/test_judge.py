import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import judge

VALID = ('{"accuracy_score": 90, "unsupported_claims": ["x"], '
         '"misleading_or_wrong": [], "notes": "ok"}')


class TestExtractJson(unittest.TestCase):
    def test_valid_json(self):
        v = judge.extract_json(VALID)
        self.assertEqual(v["accuracy_score"], 90)
        self.assertEqual(v["unsupported_claims"], ["x"])

    def test_fenced_json(self):
        v = judge.extract_json(f"Here you go:\n```json\n{VALID}\n```\n")
        self.assertEqual(v["accuracy_score"], 90)

    def test_malformed_json(self):
        v = judge.extract_json("{accuracy_score: ninety}")
        self.assertIsNone(v["accuracy_score"])
        self.assertIn("invalid JSON", v["notes"])
        self.assertIn("_raw", v)

    def test_no_json_at_all(self):
        v = judge.extract_json("I refuse to answer.")
        self.assertIsNone(v["accuracy_score"])
        self.assertIn("could not parse", v["notes"])
        self.assertEqual(v["unsupported_claims"], [])


class TestJudgeOnePrompt(unittest.TestCase):
    META = {
        "id": "home",
        "controls": ["button: Restart Gateway"],
        "text": "Gateway Status Online",
    }
    DOC = "# Home\n\nThe home screen."

    def _judge(self, no_image, png_bytes=None):
        captured = {}

        def fake_call(messages):
            captured["messages"] = messages
            return VALID

        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp)
            if png_bytes is not None:
                (cap / "home.png").write_bytes(png_bytes)
            with mock.patch.object(judge, "CAP", cap), \
                 mock.patch.object(judge, "NO_IMAGE", no_image), \
                 mock.patch.object(judge, "call_model", fake_call):
                result = judge.judge_one(self.META, self.DOC)
        return result, captured["messages"]

    def test_prompt_contains_chrome_instruction(self):
        _, messages = self._judge(no_image=True)
        prompt = messages[0]["content"][0]["text"]
        self.assertIn("EVERY screen", prompt)
        self.assertIn("left navigation sidebar", prompt)
        self.assertIn("chat/terminal panel", prompt)

    def test_prompt_contains_evidence_doc_and_schema(self):
        _, messages = self._judge(no_image=True)
        prompt = messages[0]["content"][0]["text"]
        self.assertIn("- button: Restart Gateway", prompt)
        self.assertIn("Gateway Status Online", prompt)
        self.assertIn("The home screen.", prompt)
        self.assertIn('"accuracy_score"', prompt)

    def test_no_image_mode(self):
        result, messages = self._judge(no_image=True, png_bytes=b"\x89PNG")
        content = messages[0]["content"]
        self.assertEqual(len(content), 1)  # no image even though the png exists
        self.assertNotIn("screenshot", content[0]["text"])
        self.assertEqual(result["accuracy_score"], 90)

    def test_image_attached_when_present(self):
        _, messages = self._judge(no_image=False, png_bytes=b"\x89PNG")
        content = messages[0]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[1]["type"], "image_url")
        url = content[1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), b"\x89PNG")
        self.assertIn("and a screenshot", content[0]["text"])

    def test_image_mode_without_png_falls_back_to_text(self):
        _, messages = self._judge(no_image=False)
        self.assertEqual(len(messages[0]["content"]), 1)

    def test_missing_controls_renders_none(self):
        captured = {}

        def fake_call(messages):
            captured["messages"] = messages
            return VALID

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(judge, "CAP", Path(tmp)), \
                 mock.patch.object(judge, "NO_IMAGE", True), \
                 mock.patch.object(judge, "call_model", fake_call):
                judge.judge_one({"id": "x", "controls": [], "text": ""}, "# X")
        self.assertIn("(none)", captured["messages"][0]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
