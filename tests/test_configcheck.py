import tempfile
import unittest
from pathlib import Path

import configcheck

VALID = (
    'baseUrl: "http://localhost:9200"\n'
    'productDescription: "AgentBOX, a mailbox automation dashboard"\n'
)


class TestConfigErrors(unittest.TestCase):
    def _errors(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if content is not None:
                (root / "config.yaml").write_text(content)
            return configcheck.config_errors(root)

    def test_missing_file(self):
        errs = self._errors(None)
        self.assertEqual(len(errs), 1)
        self.assertIn("config.yaml not found", errs[0])
        self.assertIn("cp config.example.yaml config.yaml", errs[0])

    def test_placeholder_base_url(self):
        errs = self._errors(
            'baseUrl: "https://your-dashboard.example.com"\n'
            'productDescription: "a real product"\n'
        )
        self.assertEqual(len(errs), 1)
        self.assertIn('"baseUrl"', errs[0])
        self.assertIn("placeholder", errs[0])

    def test_placeholder_product_description(self):
        errs = self._errors(
            'baseUrl: "http://localhost:9200"\n'
            'productDescription: "your product, a one-line description of what the dashboard does"\n'
        )
        self.assertEqual(len(errs), 1)
        self.assertIn('"productDescription"', errs[0])

    def test_missing_key(self):
        errs = self._errors('baseUrl: "http://localhost:9200"\n')
        self.assertEqual(len(errs), 1)
        self.assertIn('"productDescription"', errs[0])
        self.assertIn("missing", errs[0])

    def test_valid(self):
        self.assertEqual(self._errors(VALID), [])


class TestRequireConfig(unittest.TestCase):
    def test_exits_on_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                configcheck.require_config(Path(tmp))

    def test_passes_on_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(VALID)
            configcheck.require_config(root)  # must not raise


class TestReadKey(unittest.TestCase):
    def test_reads_quoted_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(VALID)
            self.assertEqual(configcheck.read_key("baseUrl", root), "http://localhost:9200")

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(configcheck.read_key("baseUrl", Path(tmp)), "")

    def test_empty_quoted_value_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text('openapiUrl: ""\n')
            self.assertEqual(configcheck.read_key("openapiUrl", root), "")

    def test_bare_key_does_not_leak_next_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text("openapiUrl:\n# a comment line\n")
            self.assertEqual(configcheck.read_key("openapiUrl", root), "")

    def test_reads_unquoted_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text("auth: true\n")
            self.assertEqual(configcheck.read_key("auth", root), "true")


if __name__ == "__main__":
    unittest.main()
