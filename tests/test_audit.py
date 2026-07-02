import json
import tempfile
import unittest
from pathlib import Path

import audit

KEY_ELEMENTS_MD = """# Home

## What it's for
Landing page.

## Key elements

| Element | Description |
|---------|-------------|
| **Restart Gateway** | Restarts the gateway service. |
| `Export CSV` | Downloads the table. |
| Frobnicator | Does something invented. |

## Common tasks
Stuff.
"""


class TestParseKeyElements(unittest.TestCase):
    def test_extracts_element_column(self):
        self.assertEqual(
            audit.parse_key_elements(KEY_ELEMENTS_MD),
            ["Restart Gateway", "Export CSV", "Frobnicator"],
        )

    def test_skips_header_and_separator_rows(self):
        rows = audit.parse_key_elements(KEY_ELEMENTS_MD)
        self.assertNotIn("Element", rows)
        self.assertFalse(any(set(r) <= {"-", ":", " "} for r in rows))

    def test_no_section_returns_empty(self):
        self.assertEqual(audit.parse_key_elements("# Home\n\nNo table here.\n"), [])

    def test_stops_at_next_section(self):
        md = KEY_ELEMENTS_MD + "\n## Extra\n| Sneaky | row |\n"
        self.assertNotIn("Sneaky", audit.parse_key_elements(md))


class TestGrounding(unittest.TestCase):
    TEXT = audit.norm("Gateway Status: Online. Restart Gateway. Recent incoming messages.")
    LABELS = ["Restart Gateway", "Export CSV"]

    def test_exact_phrase_in_text(self):
        self.assertTrue(audit._ground_part("Restart Gateway", self.TEXT, []))

    def test_token_overlap_with_control_label(self):
        # "Export" shares >= 50% of its tokens with the "Export CSV" control
        self.assertTrue(audit._ground_part("Export button", self.TEXT, self.LABELS))

    def test_most_tokens_in_text(self):
        # "gateway", "status", "online" all appear -> >= 0.7 present
        self.assertTrue(audit._ground_part("Gateway status online", self.TEXT, []))

    def test_ungrounded(self):
        self.assertFalse(audit._ground_part("Frobnicator", self.TEXT, self.LABELS))

    def test_empty_or_stopword_only_part_is_grounded(self):
        self.assertTrue(audit._ground_part("", self.TEXT, []))
        self.assertTrue(audit._ground_part("the button", self.TEXT, []))

    def test_grounded_whole_phrase(self):
        self.assertTrue(audit.grounded("Restart Gateway", self.TEXT, self.LABELS))

    def test_grounded_split_parts(self):
        # The bundled phrase fails as a whole (token overlap diluted below the
        # thresholds), but every part is grounded individually.
        phrase = "Restart Gateway, Export CSV and Recent messages"
        self.assertFalse(audit._ground_part(phrase, self.TEXT, self.LABELS))
        self.assertTrue(audit.grounded(phrase, self.TEXT, self.LABELS))

    def test_split_fails_if_any_part_ungrounded(self):
        self.assertFalse(
            audit.grounded("Export CSV / Frobnicator Widget Gizmo", self.TEXT, self.LABELS)
        )

    def test_single_ungrounded_part_is_false(self):
        self.assertFalse(audit.grounded("Frobnicator", self.TEXT, self.LABELS))


class TestControlLabel(unittest.TestCase):
    def test_strips_role_prefix(self):
        self.assertEqual(audit.control_label("button: Restart Gateway"), "Restart Gateway")

    def test_no_prefix(self):
        self.assertEqual(audit.control_label("  Plain "), "Plain")


class TestComputeChrome(unittest.TestCase):
    def test_frequent_labels_are_chrome(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for i in range(4):
                controls = ["link: Home", f"button: Unique {i}"]
                if i < 3:
                    controls.append("link: Settings")
                p = root / f"s{i}.json"
                p.write_text(json.dumps({"id": f"s{i}", "controls": controls}))
                paths.append(p)
            chrome = audit.compute_chrome(paths)
        # threshold = max(3, int(0.5 * 4)) = 3
        self.assertIn("home", chrome)      # on 4 screens
        self.assertIn("settings", chrome)  # on exactly 3 screens
        self.assertFalse(any(c.startswith("unique") for c in chrome))


class TestAuditScreen(unittest.TestCase):
    META = {
        "id": "home",
        "text": "Gateway Status Online Restart Gateway Recent Messages",
        "controls": ["button: Restart Gateway", "link: Settings", "button: Export CSV"],
    }
    MD = """# Home

## Key elements

| Element | Description |
|---------|-------------|
| Restart Gateway | Restarts the gateway. |
| Frobnicator | Invented widget. |
| [Message Subject] | One row per message. |
"""

    def _audit(self):
        return audit.audit_screen(self.META, self.MD, chrome={"settings"})

    def test_hallucinated(self):
        self.assertEqual(self._audit()["hallucinated"], ["Frobnicator"])

    def test_templated_not_counted_as_hallucinated(self):
        r = self._audit()
        self.assertEqual(r["templated"], ["[Message Subject]"])
        self.assertNotIn("[Message Subject]", r["hallucinated"])

    def test_undocumented_excludes_chrome(self):
        r = self._audit()
        self.assertEqual(r["undocumented"], ["Export CSV"])  # Settings is chrome

    def test_coverage(self):
        r = self._audit()
        # 2 specific controls (Restart Gateway, Export CSV), 1 undocumented -> 50%
        self.assertEqual(r["specific_control_count"], 2)
        self.assertEqual(r["coverage_pct"], 50)

    def test_documented_for_layer2_excludes_templated(self):
        self.assertEqual(self._audit()["documented"], ["Restart Gateway", "Frobnicator"])

    def test_no_specific_controls_is_100(self):
        meta = {"id": "x", "text": "", "controls": ["link: Settings"]}
        r = audit.audit_screen(meta, "# X\n", chrome={"settings"})
        self.assertEqual(r["coverage_pct"], 100)
        self.assertEqual(r["hallucinated"], [])


if __name__ == "__main__":
    unittest.main()
