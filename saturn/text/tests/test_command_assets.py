from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEXT_ROOT.parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.glyph_sets import load_glyph_sets  # noqa: E402


def _corpus(name: str) -> list[dict[str, object]]:
    return json.loads(
        (TEXT_ROOT / "corpus" / "game" / "addressed" / name).read_text(
            encoding="utf-8"
        )
    )


class CommandAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.battle = load_asset("battle/commands.json")
        cls.battle_binding = load_binding(BINDING_ROOT / "battle_commands.json")
        cls.comp = load_asset("ui/comp_commands.json")
        cls.comp_binding = load_binding(BINDING_ROOT / "comp_commands.json")
        cls.common = load_asset("facilities/common.json")
        cls.shop = load_asset("facilities/shop.json")
        cls.bar = load_asset("facilities/bar.json")
        cls.healer = load_asset("facilities/healer.json")
        cls.facility_bindings = (
            load_binding(BINDING_ROOT / "facilities_common.json"),
            load_binding(BINDING_ROOT / "facilities_shop.json"),
            load_binding(BINDING_ROOT / "facilities_bar.json"),
            load_binding(BINDING_ROOT / "facilities_healer.json"),
        )

    def test_battle_commands_preserve_the_mature_visible_vocabulary(self) -> None:
        expected = {
            "fight": "FIGHT",
            "talk": "TALK",
            "escape": "ESCAPE",
            "auto": "AUTO",
            "sword": "SWORD",
            "attack": "ATTACK",
            "gun": "GUN",
            "guard": "GUARD",
            "go": "GO",
            "offense": "OFFENSE",
            "defense": "DEFENSE",
            "comp": "COMP",
            "magic": "MAGIC",
            "item": "ITEM",
            "move": "MOVE",
            "return": "RETURN",
            "extra": "EXTRA",
            "preset": "PRESET",
            "repeat": "REPEAT",
        }
        self.assertEqual(
            {
                key: entry.fields["name"].translation
                for key, entry in self.battle.entries.items()
            },
            expected,
        )
        self.assertEqual(
            self.battle.field("offense.name").resolve("battle_table")[:2],
            ("OFFENCE", "OFFENCE"),
        )
        self.assertEqual(
            self.battle.field("defense.name").resolve("battle_table")[:2],
            ("DEFENCE", "DEFENCE"),
        )

    def test_battle_tables_are_extracted_without_collapsing_physical_uses(self) -> None:
        corpus = _corpus("battle_command_labels.json")
        corpus_ids = {row["id"] for row in corpus}
        physical_bindings = {
            physical_id
            for physical_id in self.battle_binding.records
            if physical_id.startswith("game.battle_command_labels.")
        }
        self.assertEqual(len(corpus), 20)
        self.assertEqual(physical_bindings, corpus_ids)
        self.assertEqual(len(self.battle_binding.records), 27)
        self.assertEqual(
            dict(self.battle_binding.variants),
            {
                "game.battle_command_labels.o050674": "battle_table",
                "game.battle_command_labels.o05067c": "battle_table",
            },
        )

        manifest = json.loads(
            (
                TEXT_ROOT / "config" / "sources" / "game" / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        source = next(
            item for item in manifest["sources"] if item["id"] == "battle_command_labels"
        )
        container = source["container"]
        self.assertEqual(container["tables"][0]["count"], 4)
        self.assertEqual(len(container["records"]), 16)
        self.assertTrue(
            all(
                len(record["locations"]) == 3
                and record["require_identical_bytes"] is True
                for record in container["records"]
            )
        )

    def test_unlocated_primary_battle_selectors_remain_explicit_debt(self) -> None:
        bound_refs = set(self.battle_binding.records.values())
        self.assertEqual(
            {
                f"{key}.name"
                for key in self.battle.entries
                if f"{key}.name" not in bound_refs
            },
            {
                "fight.name",
                "talk.name",
                "escape.name",
                "auto.name",
                "preset.name",
                "repeat.name",
            },
        )

    def test_comp_commands_are_one_editable_surface_catalog(self) -> None:
        expected = {
            "comp": "COMP",
            "magic": "MAGIC",
            "item": "ITEM",
            "equip": "EQUIP",
            "status": "STATUS",
        }
        self.assertEqual(
            {
                key: entry.fields["text"].translation
                for key, entry in self.comp.entries.items()
            },
            expected,
        )
        self.assertEqual(
            set(self.comp_binding.records),
            {row["id"] for row in _corpus("comp_command_labels.json")},
        )
        self.assertEqual(dict(self.comp_binding.field_surfaces), {"text": ("comp.command",)})

    def test_facility_commands_are_owned_by_their_human_facing_catalogs(self) -> None:
        expected = {
            "facilities/common.json": {"exit.text": "EXIT", "status.text": "STATUS"},
            "facilities/shop.json": {
                "command_buy.text": "BUY",
                "command_sell.text": "SELL",
                "command_equip.text": "EQUIP",
            },
            "facilities/bar.json": {
                "command_order.text": "ORDER",
                "command_talk.text": "TALK",
            },
            "facilities/healer.json": {
                "command_all.text": "ALL",
                "command_heal.text": "HEAL",
                "command_cure.text": "CURE",
                "command_curse.text": "CURSE",
                "command_revive.text": "REVIVE",
            },
        }
        catalogs = {
            "facilities/common.json": self.common,
            "facilities/shop.json": self.shop,
            "facilities/bar.json": self.bar,
            "facilities/healer.json": self.healer,
        }
        for asset, fields in expected.items():
            with self.subTest(asset=asset):
                self.assertEqual(
                    {
                        asset_ref: catalogs[asset].field(asset_ref).translation
                        for asset_ref in fields
                    },
                    fields,
                )

        corpus_ids = {row["id"] for row in _corpus("facility_command_labels.json")}
        owners: dict[str, int] = {physical_id: 0 for physical_id in corpus_ids}
        for binding in self.facility_bindings:
            for physical_id in set(binding.records) & corpus_ids:
                owners[physical_id] += 1
        self.assertEqual(owners, {physical_id: 1 for physical_id in corpus_ids})
        self.assertEqual(
            dict(self.facility_bindings[0].glyph_equivalence),
            {"e0": "S", "e1": "T", "e2": "A", "e3": "T", "e4": "U", "e5": "S"},
        )
        self.assertEqual(
            dict(self.facility_bindings[3].glyph_equivalence),
            {"da": "R", "db": "E", "dc": "V", "dd": "I", "de": "V", "df": "E"},
        )

    def test_every_command_surface_selects_the_preserved_stock_alphabet(self) -> None:
        catalog = load_glyph_sets()
        for surface in (
            "battle.command",
            "comp.command",
            "shop.command",
            "bar.command",
            "healer.command",
            "status.auto_command",
            "status.auto_setting",
        ):
            with self.subTest(surface=surface):
                handler = catalog.for_surface(surface)
                self.assertIsNotNone(handler)
                self.assertEqual((handler.font, handler.reference_set), ("font8", "stock_latin"))


if __name__ == "__main__":
    unittest.main()
