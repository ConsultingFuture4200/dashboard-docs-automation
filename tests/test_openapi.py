import tempfile
import unittest
import urllib.error
from pathlib import Path

import openapi


class TestRefName(unittest.TestCase):
    def test_ref(self):
        self.assertEqual(
            openapi.ref_name({"$ref": "#/components/schemas/Pet"}), "Pet"
        )

    def test_array(self):
        self.assertEqual(
            openapi.ref_name({"type": "array", "items": {"$ref": "#/c/s/Pet"}}),
            "Pet[]",
        )

    def test_any_of(self):
        self.assertEqual(
            openapi.ref_name(
                {"anyOf": [{"$ref": "#/c/s/Pet"}, {"type": "null"}]}
            ),
            "Pet | null",
        )

    def test_primitive(self):
        self.assertEqual(openapi.ref_name({"type": "string"}), "string")

    def test_not_a_dict(self):
        self.assertEqual(openapi.ref_name("not a dict"), "")

    def test_all_of_single(self):
        self.assertEqual(
            openapi.ref_name({"allOf": [{"$ref": "#/c/s/Pet"}]}), "Pet"
        )

    def test_all_of_multiple(self):
        self.assertEqual(
            openapi.ref_name(
                {"allOf": [{"$ref": "#/c/s/Pet"}, {"$ref": "#/c/s/Timestamped"}]}
            ),
            "Pet & Timestamped",
        )

    def test_one_of(self):
        self.assertEqual(
            openapi.ref_name(
                {"oneOf": [{"$ref": "#/c/s/Cat"}, {"$ref": "#/c/s/Dog"}]}
            ),
            "Cat | Dog",
        )

    def test_all_of_empty(self):
        self.assertEqual(openapi.ref_name({"allOf": []}), "object")


class TestGroupKey(unittest.TestCase):
    def test_api_prefixed(self):
        self.assertEqual(
            openapi.group_key("/api/appointments/list"), "Appointments"
        )

    def test_api_only(self):
        self.assertEqual(openapi.group_key("/api"), "Api")

    def test_non_api(self):
        self.assertEqual(openapi.group_key("/health"), "Health")

    def test_root(self):
        self.assertEqual(openapi.group_key("/"), "Root")


class TestRenderOperation(unittest.TestCase):
    def test_basic(self):
        result = openapi.render_operation(
            "get",
            "/api/x",
            {"summary": "List x", "responses": {"200": {"description": "ok"}}},
        )
        first_line = result.split("\n")[0]
        self.assertEqual(first_line, "### `GET /api/x`")
        self.assertIn("**List x**", result)
        self.assertIn("| Code | Description |", result)
        self.assertIn("| 200 | ok |", result)


class TestErrorHandling(unittest.TestCase):
    def test_load_config_missing_file(self):
        orig_root = openapi.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            openapi.ROOT = Path(tmp)
            try:
                with self.assertRaises(SystemExit):
                    openapi.load_config()
            finally:
                openapi.ROOT = orig_root

    def _load_config_with(self, openapi_line):
        orig_root = openapi.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                'baseUrl: "http://localhost:9200"\n'
                'productDescription: "a real product"\n'
                + openapi_line
            )
            openapi.ROOT = root
            try:
                return openapi.load_config()
            finally:
                openapi.ROOT = orig_root

    def test_load_config_blank_url_returns_empty(self):
        self.assertEqual(self._load_config_with('openapiUrl: ""\n'), "")

    def test_load_config_bare_key_returns_empty(self):
        self.assertEqual(self._load_config_with("openapiUrl:\n# comment\n"), "")

    def test_load_config_missing_key_returns_empty(self):
        self.assertEqual(self._load_config_with(""), "")

    def test_load_config_placeholder_returns_empty(self):
        self.assertEqual(
            self._load_config_with(
                'openapiUrl: "https://your-dashboard.example.com/openapi.json"\n'
            ),
            "",
        )

    def test_load_config_real_url(self):
        self.assertEqual(
            self._load_config_with('openapiUrl: "http://localhost:1234/openapi.json"\n'),
            "http://localhost:1234/openapi.json",
        )

    def test_main_skips_cleanly_when_url_unset(self):
        orig_fetch = openapi.fetch
        orig_load_config = openapi.load_config
        openapi.fetch = lambda url: self.fail("fetch must not be called on skip")
        openapi.load_config = lambda: ""
        try:
            openapi.main()  # must not raise / exit
        finally:
            openapi.fetch = orig_fetch
            openapi.load_config = orig_load_config

    def test_main_fetch_failure(self):
        orig_fetch = openapi.fetch
        orig_load_config = openapi.load_config
        openapi.fetch = lambda url: (_ for _ in ()).throw(urllib.error.URLError("boom"))
        openapi.load_config = lambda: "http://example.invalid/openapi.json"
        try:
            with self.assertRaises(SystemExit):
                openapi.main()
        finally:
            openapi.fetch = orig_fetch
            openapi.load_config = orig_load_config


if __name__ == "__main__":
    unittest.main()
