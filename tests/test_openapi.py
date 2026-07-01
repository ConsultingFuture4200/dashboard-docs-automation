import unittest

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


if __name__ == "__main__":
    unittest.main()
