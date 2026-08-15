from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


EXPECTED_TRANSLATIONS = {
    "battle_messages.label": "Battle Messages",
    "auto_mapping.label": "Auto Map",
    "party_panel.label": "Party Panel",
    "demon_analyze.label": "Demon Analyze",
    "sound.label": "Sound",
    "magic_order.label": "Magic Order",
    "item_order.label": "Item Order",
    "message_speed.fast": "Fast",
    "message_speed.normal": "Normal",
    "message_speed.slow": "Slow",
    "auto_mapping_mode.fixed": "Fixed",
    "auto_mapping_mode.free": "Free",
    "party_panel_mode.graph": "Graph",
    "party_panel_mode.maximum": "MAX",
    "analyze_display.normal": "Normal",
    "analyze_display.reverse": "Reverse",
    "sound_mode.stereo": "Stereo",
    "sound_mode.mono": "Mono",
    "controller.label": "Controls",
    "controller.normal": "Normal",
    "controller.custom": "Custom",
    "magic_sort.recovery": "Recovery",
    "magic_sort.special": "Special",
    "magic_sort.attack": "Attack",
    "magic_sort.debuff": "Debuff",
    "item_sort.consumable": "Consumable",
    "item_sort.jewel": "Jewel",
    "item_sort.equipment": "Equipment",
    "controller_actions.full_cancel": "Full Cancel",
    "controller_actions.cancel": "Cancel",
    "controller_actions.confirm": "Confirm",
    "controller_actions.show_help": "Show Help",
    "controller_actions.auto_recover": "Auto Recover",
    "controller_actions.command": "Command",
    "controller_actions.auto_map": "Auto Map",
    "controller_actions.demon_analyze": "Demon Analyze",
    "controller_footer.assign": "START: Assign",
    "controller_footer.finish": "START: End",
}


class OptionsAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("ui/options.json")
        cls.binding = load_binding(BINDING_ROOT / "options.json")
        cls.surfaces = load_surfaces()
        cls.physical = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "config_static.json"
            ).read_text(encoding="utf-8")
        )

    def test_complete_menu_uses_the_mature_saturn_output(self) -> None:
        self.assertEqual(len(EXPECTED_TRANSLATIONS), 38)
        self.assertEqual(
            {
                asset_ref: self.catalog.field(asset_ref).translation
                for asset_ref in EXPECTED_TRANSLATIONS
            },
            EXPECTED_TRANSLATIONS,
        )
        self.assertEqual(
            {
                f"{entry_name}.{field_name}"
                for entry_name, entry in self.catalog.entries.items()
                for field_name in entry.fields
            },
            set(EXPECTED_TRANSLATIONS),
        )

    def test_all_38_physical_records_have_one_semantic_owner(self) -> None:
        physical_ids = {row["id"] for row in self.physical}
        self.assertEqual(len(physical_ids), 38)
        self.assertEqual(set(self.binding.records), physical_ids)
        self.assertEqual(set(self.binding.records.values()), set(EXPECTED_TRANSLATIONS))
        self.assertEqual(dict(self.binding.variants), {})
        self.assertEqual(dict(self.binding.composition), {})
        self.assertEqual(dict(self.binding.unresolved), {})

    def test_surface_partition_matches_the_two_page_menu(self) -> None:
        counts: dict[str, int] = {}
        for surfaces in self.binding.record_surfaces.values():
            self.assertEqual(len(surfaces), 1)
            counts[surfaces[0]] = counts.get(surfaces[0], 0) + 1
        self.assertEqual(
            counts,
            {
                "options.primary_label": 8,
                "options.value": 13,
                "options.ordering_popup": 7,
                "options.controller_action": 8,
                "options.footer": 2,
            },
        )

    def test_surface_limits_separate_screen_geometry_from_unknowns(self) -> None:
        expected = {
            "options.primary_label": (
                ("font16", 1, "glyph_cells", 9),
                (None, None, None, None),
            ),
            "options.value": (
                ("font16", 1, "glyph_cells", 4),
                (None, None, None, None),
            ),
            "options.ordering_popup": (
                ("font16", 4, "glyph_cells", 5),
                ("font16", 4, "pixels", 80),
            ),
            "options.controller_action": (
                ("font12", 1, "glyph_cells", 8),
                ("font12", 1, "pixels", 128),
            ),
            "options.footer": (
                ("font16", 1, "glyph_cells", 9),
                ("font16", 1, "pixels", 144),
            ),
        }
        for name, (ja, en) in expected.items():
            with self.subTest(surface=name):
                surface = self.surfaces.surface(name)
                self.assertEqual(
                    (surface.ja.font, surface.ja.rows, surface.ja.width.unit, surface.ja.width.value),
                    ja,
                )
                self.assertEqual(
                    (surface.en.font, surface.en.rows, surface.en.width.unit, surface.en.width.value),
                    en,
                )

    def test_compound_render_fragments_are_not_authored_text(self) -> None:
        translations = set(EXPECTED_TRANSLATIONS.values())
        self.assertTrue(
            {
                "AR",
                " A",
                "ign",
                "Re",
                "co",
                "ve",
                "Sp",
                "ec",
                "At",
                "De",
                "Co",
                "ns",
                "um",
                "ab",
                "le",
                "Eq",
                "ui",
                "pm",
                "en",
            }.isdisjoint(translations)
        )

    def test_proven_psp_reuse_does_not_copy_identical_fields(self) -> None:
        psp_label = self.catalog.field("battle_messages.label").resolve("psp")
        self.assertEqual(psp_label[:2], ("戦闘中メッセージ", "Battle Messages"))
        self.assertEqual(
            self.catalog.field("auto_mapping.label").resolve()[:2],
            ("オートマッピング", "Auto Map"),
        )
        self.assertEqual(
            {
                self.catalog.field(f"message_speed.{name}").translation
                for name in ("fast", "normal", "slow")
            },
            {"Fast", "Normal", "Slow"},
        )


if __name__ == "__main__":
    unittest.main()
