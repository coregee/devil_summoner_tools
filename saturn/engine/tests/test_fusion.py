from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    EVENT_DIALOGUE_OUTPUT_PATH,
    FUSION_BUILD_MANIFEST_PATH,
    FUSION_OUTPUT_PATH,
    build_event_dialogue,
    build_fusion_surface,
)
from engine.shared.demon_sort import (  # noqa: E402
    dense_rank_table,
    encode_sorted_pool,
    english_name_key,
)
from engine.surfaces.event_dialogue import stock_event  # noqa: E402
from engine.surfaces.fusion import CONFIG_PATH, build_fusion_menu  # noqa: E402


class FusionEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        event = build_event_dialogue()[EVENT_DIALOGUE_OUTPUT_PATH]
        cls.fusion = build_fusion_menu(stock_event(), event)
        cls.outputs = build_fusion_surface()
        cls.manifest = json.loads(cls.outputs[FUSION_BUILD_MANIFEST_PATH])

    def test_proven_runtime_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.fusion.runtime), 5786)
        self.assertEqual(
            hashlib.sha256(self.fusion.runtime).hexdigest(),
            "4b853e181b0c9885d0f59ec21f111b812d4afa194daf48d4f85aea51d98abfd9",
        )

        self.assertEqual(
            self.fusion.addresses,
            {
                "font12_widths": 0x06021800,
                "race_offsets": 0x0602190C,
                "demon_offsets": 0x06021962,
                "character_offsets": 0x06021BE0,
                "race_pool": 0x06021BEC,
                "demon_pool": 0x06021C6D,
                "character_pool": 0x06022642,
                "table_race_offsets": 0x06022690,
                "table_race_pool": 0x060226E6,
                "chart_widths": 0x060227EC,
                "font8_widths": 0x06022817,
                "font8_map": 0x06022917,
                "surface_blitter": 0x06022A18,
                "font8_blitter": 0x06022AC8,
                "name_drawers": 0x06022B74,
                "fusion_preview_race": 0x06022B74,
                "fusion_chart_race": 0x06022BAE,
                "fusion_table_race": 0x06022BF6,
                "fusion_table_demon": 0x06022C2C,
                "fusion_demon_name": 0x06022C30,
                "fusion_preview_demon": 0x06022C34,
                "fusion_character_name": 0x06022C6E,
                "fusion_word_font8_glyph": 0x06022D96,
                "fusion_guide_mixed_glyph": 0x06022DF2,
            },
        )

    def test_shared_english_demon_collation_matches_the_mature_contract(self) -> None:
        self.assertEqual(english_name_key("Jack-o'-Lantern"), "jackolantern")
        self.assertEqual(
            dense_rank_table(("Zed", "Alpha", "Alpha", "Beta"), count=4),
            bytes((2, 0, 0, 1, 0xFF)),
        )

        names = ("Pixie", "Jack Frost", "Pixie")
        codes = {character: ord(character) for character in "PixieJack Frost"}
        offsets, pool = encode_sorted_pool(names, codes)
        self.assertEqual(offsets, struct.pack(">3H", 11, 0, 11))
        self.assertEqual(pool, b"Jack Frost\xffPixie\xff")
        with self.assertRaisesRegex(ValueError, "same English sort key"):
            encode_sorted_pool(
                ("Jack Frost", "Jack-Frost"),
                {character: ord(character) for character in "Jack Frost-"},
            )

    def test_runtime_executable_is_owned_by_readable_assembly(self) -> None:
        self.assertEqual(
            {
                path.relative_to(SATURN_ROOT / "engine").as_posix()
                for path in self.fusion.assembly_files
            },
            {
                "asm/font16_surface_blitter.s",
                "asm/fusion/confirmation_pointer_lookup.s",
                "asm/fusion/confirmation_pointer_lookup_stock.s",
                "asm/fusion/font8_surface_blitter.s",
                "asm/fusion/name_drawers.s",
                "asm/fusion/name_sort.s",
            },
        )
        module_source = Path(__file__).resolve().parents[1] / "surfaces" / "fusion.py"
        self.assertNotIn("bytes.fromhex", module_source.read_text(encoding="utf-8"))

    def test_patch_inventory_is_a_typed_recipe(self) -> None:
        source = CONFIG_PATH.read_text(encoding="utf-8")
        document = json.loads(source)
        rows = [row for group in document["groups"] for row in group["patches"]]
        self.assertEqual(document["version"], 2)
        self.assertEqual(len(rows), 67)
        self.assertNotIn('"replacement"', source)
        self.assertEqual(
            {
                key: sum(key in row for row in rows)
                for key in (
                    "assembly",
                    "generated",
                    "pointer",
                    "linked_pointer",
                    "instruction",
                )
            },
            {
                "assembly": 3,
                "generated": 4,
                "pointer": 1,
                "linked_pointer": 50,
                "instruction": 9,
            },
        )

    def test_composed_event_output_is_deterministic(self) -> None:
        output = self.outputs[FUSION_OUTPUT_PATH]
        self.assertEqual(len(output), 354072)
        self.assertEqual(
            hashlib.sha256(output).hexdigest(),
            "906ffa353eceb0e09ad10f5dde4cbdc08e469dfe11e43d1ff653b2c004f4d826",
        )

    def test_manifest_accounts_for_every_consumer_patch(self) -> None:
        self.assertEqual(self.manifest["surface"], "fusion.menu")
        self.assertEqual(
            self.manifest["patch_config_sha256"],
            hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {
                path.relative_to(SATURN_ROOT.parent).as_posix()
                for path in self.fusion.assembly_files
            },
        )
        self.assertEqual(self.manifest["runtime"]["end"], "0x06022e9a")
        self.assertEqual(self.manifest["patches"], 67)
        self.assertEqual(
            self.manifest["patch_groups"],
            [
                "fusion.runtime",
                "fusion.list",
                "fusion.preview",
                "fusion.table",
                "fusion.guide",
                "fusion.chart",
                "fusion.confirmation",
            ],
        )
        self.assertEqual(len(self.manifest["asset_inputs"]), 8)


if __name__ == "__main__":
    unittest.main()
