import unittest

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
        # Controls are reformatted as "label" (role) so the raw "role: label"
        # prefix no longer leaks into the drafted docs.
        self.assertIn('"Save" (button)', text)
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


if __name__ == "__main__":
    unittest.main()
