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
        expected_references = {
            character: code for code, character in enumerate(expected)
        }
        expected_references["-"] = 174
        expected_references["."] = 176
        expected_references["/"] = 198
        self.assertEqual(len(references), 66)
        self.assertEqual(references, expected_references)
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
        self.assertEqual(
            result.data[174 * stride : 175 * stride],
            source[174 * stride : 175 * stride],
        )
        self.assertEqual(
            result.data[176 * stride : 177 * stride],
            source[176 * stride : 177 * stride],
        )
        self.assertEqual(
            result.data[198 * stride : 199 * stride],
            source[198 * stride : 199 * stride],
        )
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
            with self.assertRaisesRegex(ValueError, "remapped glyph 63"):
                load_definition(path, "game")

    def test_reference_set_can_publish_an_ascii_alias_for_stock_punctuation(self) -> None:
        references = self.definition.reference_sets["stock_latin"]
        self.assertEqual(references["-"], 174)
        self.assertEqual(references["."], 176)
        self.assertEqual(references["/"], 198)
        self.assertNotIn("・", references)
        self.assertNotIn("．", references)
        self.assertNotIn("／", references)
        self.assertEqual(self.definition.glyphs[174], "・")
        self.assertEqual(self.definition.glyphs[176], "．")
        self.assertEqual(self.definition.glyphs[198], "／")

    def test_compound_facility_tiles_are_documented_as_healer_labels(self) -> None:
        document = json.loads(
            (CONFIG_ROOT / "game" / "font8.json").read_text(encoding="utf-8")
        )
        description = document["description"]
        self.assertIn("healer screen", description)
        self.assertIn("former compound cells", description)
        self.assertIn("stock_latin", description)
        self.assertNotIn("REVIEW", description)

    def test_direct_gui_consumers_preserve_overloaded_font8_cells(self) -> None:
        self.assertEqual(
            self.definition.source_consumers,
            {
                "shop_equipped_marker": ("{equip_symbol}",),
            },
        )


class KanjiNameEntryReferenceSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = load_definition(
            CONFIG_ROOT / "game" / "kanji.json",
            "game",
        )

    def test_ark_name_entry_latin_reuses_the_explicit_grid_codes(self) -> None:
        expected = {
            **{character: 203 + index for index, character in enumerate("0123456789")},
            **{
                character: 220 + index
                for index, character in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            },
            **{
                character: 252 + index
                for index, character in enumerate("abcdefghijklmnopqrstuvwxyz")
            },
            ",": 3,
            ".": 4,
            ":": 6,
            "?": 8,
            "!": 9,
            " ": 17,
            "-": 29,
            "/": 30,
            "'": 38,
            "&": 84,
        }
        references = self.definition.reference_sets["ark_latin"]
        self.assertEqual(len(references), 72)
        self.assertEqual(references, expected)
        self.assertEqual(set(references.values()), set(self.definition.replacements))
        self.assertEqual(
            {code: self.definition.glyphs[code] for code in expected.values()},
            {code: character for character, code in expected.items()},
        )

    def test_repack_publishes_origin_aligned_16px_ark_ink_bounds(self) -> None:
        source = self.definition.source_path.read_bytes()
        result = repack_font(source, self.definition)
        self.assertNotEqual(result.data, source)
        self.assertIsNotNone(result.metrics)
        metrics = json.loads(result.metrics or "")
        self.assertEqual(len(metrics["glyphs"]), 72)
        self.assertEqual(metrics["missing_codes"], [])
        self.assertTrue(metrics["complete"])
        ark = metrics["reference_sets"]["ark_latin"]
        self.assertEqual(
            {row["text"]: row["code"] for row in ark},
            dict(self.definition.reference_sets["ark_latin"]),
        )
        self.assertTrue(all(type(row["advance"]) is int for row in ark))
        self.assertTrue(
            all(0 <= row["ink_left"] <= row["ink_right"] <= 16 for row in ark)
        )
        visible = [row for row in ark if row["ink_right"] > row["ink_left"]]
        self.assertTrue(any(row["ink_left"] == 0 for row in visible))

    def test_end_action_compound_is_named_but_not_replaced(self) -> None:
        font16 = load_definition(CONFIG_ROOT / "game" / "font16.json", "game")
        self.assertEqual(
            (font16.glyphs[1870], font16.glyphs[1871]),
            ("{input_end_prefix}", "{input_end_symbol}"),
        )
        self.assertNotIn(1870, font16.replacements)
        self.assertNotIn(1871, font16.replacements)


if __name__ == "__main__":
    unittest.main()
