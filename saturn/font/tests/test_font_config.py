from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


FONT_ROOT = Path(__file__).resolve().parents[1]
if str(FONT_ROOT) not in sys.path:
    sys.path.insert(0, str(FONT_ROOT))

from util.codec import repack_font  # noqa: E402
from util.definitions import CONFIG_ROOT, load_definition  # noqa: E402


class FontReferenceSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = load_definition(CONFIG_ROOT / "game" / "font8.json", "game")

    def test_stock_latin_is_a_distinct_preserved_reference_set(self) -> None:
        references = self.definition.reference_sets["stock_latin"]
        expected = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        self.assertEqual(len(references), 63)
        self.assertEqual(
            references,
            {character: code for code, character in enumerate(expected)},
        )
        self.assertFalse(set(references.values()) & set(self.definition.replacements))

    def test_repacked_metrics_publish_both_english_code_maps(self) -> None:
        source = self.definition.source_path.read_bytes()
        result = repack_font(source, self.definition)
        self.assertIsNotNone(result.metrics)
        metrics = json.loads(result.metrics or "")
        stock = metrics["reference_sets"]["stock_latin"]
        self.assertEqual(
            {row["text"]: row["code"] for row in stock},
            dict(self.definition.reference_sets["stock_latin"]),
        )
        self.assertTrue(all(type(row["advance"]) is int for row in stock))

        stride = self.definition.format.glyph_stride
        preserved_end = 63 * stride
        self.assertEqual(result.data[:preserved_end], source[:preserved_end])
        default_codes = {
            row["text"]: row["code"] for row in metrics["glyphs"]
        }
        self.assertNotEqual(default_codes["A"], stock[11]["code"])

    def test_reference_sets_cannot_claim_a_replaced_cell(self) -> None:
        document = json.loads(
            (CONFIG_ROOT / "game" / "font8.json").read_text(encoding="utf-8")
        )
        document["reference_sets"]["stock_latin"] = [
            {"start": 63, "characters": "あ"}
        ]
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "font8.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaced glyph 63"):
                load_definition(path, "game")


if __name__ == "__main__":
    unittest.main()
