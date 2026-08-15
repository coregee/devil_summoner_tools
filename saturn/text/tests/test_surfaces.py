from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.surfaces import load_surfaces  # noqa: E402


class SurfaceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_surfaces()

    def test_documented_translation_geometries(self) -> None:
        event = self.catalog.surface("event.dialogue")
        self.assertEqual(
            (event.ja.font, event.ja.rows, event.ja.width.unit, event.ja.width.value),
            ("font16", 3, "glyph_cells", 20),
        )
        self.assertEqual(
            (event.en.font, event.en.rows, event.en.width.unit, event.en.width.value),
            ("font16", 3, "pixels", 300),
        )

        console = self.catalog.surface("battle.console")
        for layout in (console.ja, console.en):
            self.assertEqual(
                (layout.font, layout.rows, layout.width.unit, layout.width.value),
                ("fnt8x12", 3, "glyph_cells", 16),
            )

        field_message = self.catalog.surface("map_3d.field_message")
        self.assertEqual(
            (
                field_message.ja.font,
                field_message.ja.rows,
                field_message.ja.width.unit,
                field_message.ja.width.value,
            ),
            ("font16", 1, "glyph_cells", 14),
        )
        self.assertEqual(
            (
                field_message.en.font,
                field_message.en.rows,
                field_message.en.width.unit,
                field_message.en.width.value,
            ),
            ("font16", 1, "pixels", 224),
        )

    def test_documented_fixed_width_japanese_geometries(self) -> None:
        expected = {
            "battle.help": ("font16", 2, 20),
            "battle.demon_chat": ("font16", 2, 11),
            "automap.marker_popup": ("font16", 3, 6),
            "status.affinity": ("font12", 2, 8),
            "shop.parent_help": ("font16", 1, 20),
        }
        for name, values in expected.items():
            with self.subTest(surface=name):
                layout = self.catalog.surface(name).ja
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    (*values[:2], "glyph_cells", values[2]),
                )

    def test_unmeasured_limits_remain_explicitly_unknown(self) -> None:
        demon_chat_en = self.catalog.surface("battle.demon_chat").en
        self.assertIsNone(demon_chat_en.font)
        self.assertIsNone(demon_chat_en.rows)
        self.assertIsNone(demon_chat_en.width.unit)
        self.assertIsNone(demon_chat_en.width.value)
        self.assertFalse(demon_chat_en.width.known)

        fusion_help_ja = self.catalog.surface("fusion.help").ja
        self.assertEqual((fusion_help_ja.font, fusion_help_ja.rows), ("font12", 1))
        self.assertIsNone(fusion_help_ja.width.unit)
        self.assertIsNone(fusion_help_ja.width.value)

    def test_catalog_is_strict(self) -> None:
        unknown = {
            "font": None,
            "rows": None,
            "width": {"unit": None, "value": None},
        }
        cases = {
            "missing language": {
                "version": 1,
                "surfaces": {"test.surface": {"ja": unknown}},
            },
            "partial width": {
                "version": 1,
                "surfaces": {
                    "test.surface": {
                        "ja": {
                            "font": None,
                            "rows": 1,
                            "width": {"unit": "pixels", "value": None},
                        },
                        "en": unknown,
                    }
                },
            },
            "extra field": {
                "version": 1,
                "surfaces": {
                    "test.surface": {
                        "ja": {**unknown, "note": "not part of the contract"},
                        "en": unknown,
                    }
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "surfaces.json"
            for name, document in cases.items():
                with self.subTest(case=name):
                    path.write_text(
                        json.dumps(document),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        load_surfaces(path)

    def test_duplicate_json_fields_are_rejected(self) -> None:
        document = (
            '{"version":1,"version":1,"surfaces":{"test.surface":'
            '{"ja":{"font":null,"rows":null,"width":'
            '{"unit":null,"value":null}},"en":{"font":null,"rows":null,'
            '"width":{"unit":null,"value":null}}}}}'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "surfaces.json"
            path.write_text(document, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                load_surfaces(path)


if __name__ == "__main__":
    unittest.main()
