"""Unit tests for taxonomy path resolution (no API)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.extract import parse_assignments
from src.themes import ThemeTaxonomy


def _load_taxonomy() -> ThemeTaxonomy:
    path = ROOT / "data" / "themes.json"
    if not path.is_file():
        path = ROOT / "out" / "themes" / "theme-20260731_184419" / "themes.json"
    with path.open(encoding="utf-8") as fh:
        return ThemeTaxonomy(json.load(fh))


class ResolveAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = _load_taxonomy()
        cls.assertTrue(cls.tax.paths, "taxonomy must have paths")

    def test_exact_match(self) -> None:
        path = self.tax.paths[0]
        hit = self.tax.resolve_assignment(path.strategic, path.midlevel, path.specific)
        self.assertEqual(hit, path)

    def test_garbled_duplicated_tiers(self) -> None:
        hit = self.tax.resolve_assignment(
            "Customer Support",
            "Customer Support > Response Times > Customer Support > Response Times",
            "Unanswered Questions & Chatbot Loops",
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.specific, "Unanswered Questions & Chatbot Loops")
        self.assertEqual(hit.strategic, "Customer Support")

    def test_garbled_warning_string_segments(self) -> None:
        # Real warning from run 20260731_184611
        hit = self.tax.resolve_assignment(
            "Customer Support > Customer Support > Response Times > Customer Support > Response Times > Unanswered Questions & Chatbot Loops",
            "",
            "",
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.specific, "Unanswered Questions & Chatbot Loops")

    def test_unique_specific_only(self) -> None:
        hit = self.tax.resolve_assignment("", "", "Funds Arriving Later Than Promised")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.specific, "Funds Arriving Later Than Promised")
        self.assertEqual(hit.midlevel, "Disbursement Timeliness")

    def test_path_label_enum_style(self) -> None:
        path = self.tax.paths[0]
        hit = self.tax.resolve_path_label(path.label)
        self.assertEqual(hit, path)

    def test_unknown_still_rejects(self) -> None:
        hit = self.tax.resolve_assignment(
            "Made Up Strategic",
            "Made Up Mid",
            "Definitely Not A Theme",
        )
        self.assertIsNone(hit)

    def test_parse_assignments_repairs_legacy_triple(self) -> None:
        review = {"id": "rev-test"}
        payload = json.dumps(
            {
                "assignments": [
                    {
                        "strategic_theme": "Staff & Advisory",
                        "midlevel_theme": "Staff & Advisory > Advisor Conduct",
                        "specific_theme": "Helpfulness Versus Sales Pressure",
                    }
                ]
            }
        )
        rows, warnings = parse_assignments(payload, review, self.tax)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["specific_theme"], "Helpfulness Versus Sales Pressure")
        self.assertEqual(warnings, [])

    def test_parse_assignments_path_field(self) -> None:
        path = next(
            p
            for p in self.tax.paths
            if p.specific == "Unanswered Questions & Chatbot Loops"
        )
        review = {"id": "rev-test-2"}
        payload = json.dumps({"assignments": [{"path": path.label}]})
        rows, warnings = parse_assignments(payload, review, self.tax)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["specific_theme"], path.specific)
        self.assertEqual(warnings, [])

    def test_parse_unknown_warns(self) -> None:
        review = {"id": "rev-test-3"}
        payload = json.dumps(
            {"assignments": [{"path": "Nope > Nope > Definitely Fake Theme"}]}
        )
        rows, warnings = parse_assignments(payload, review, self.tax)
        self.assertEqual(rows, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("rejected unknown path", warnings[0])


if __name__ == "__main__":
    unittest.main()
