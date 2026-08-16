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


def physical(relative_path: str) -> list[dict[str, object]]:
    return json.loads(
        (TEXT_ROOT / "corpus" / "game" / relative_path).read_text(
            encoding="utf-8"
        )
    )


class BattleAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.console = load_asset("battle/console.json")
        cls.console_binding = load_binding(BINDING_ROOT / "battle_console.json")
        cls.demon_chat = load_asset("battle/demon_chat.json")
        cls.demon_chat_binding = load_binding(
            BINDING_ROOT / "battle_demon_chat.json"
        )
        cls.conditions = load_asset("battle/condition_fallbacks.json")
        cls.condition_binding = load_binding(
            BINDING_ROOT / "battle_condition_fallbacks.json"
        )
        cls.boss_dialogue = load_asset("battle/boss_dialogue.json")
        cls.boss_dialogue_binding = load_binding(
            BINDING_ROOT / "battle_boss_dialogue.json"
        )
        cls.battle_help = load_asset("battle/help.json")
        cls.battle_help_binding = load_binding(BINDING_ROOT / "battle_help.json")
        cls.command_help = load_asset("ui/command_help.json")
        cls.command_help_binding = load_binding(BINDING_ROOT / "command_help.json")
        cls.provisioning = load_asset("battle/provisioning.json")
        cls.provisioning_binding = load_binding(
            BINDING_ROOT / "battle_provisioning.json"
        )
        cls.debug = load_asset("battle/debug.json")
        cls.debug_binding = load_binding(BINDING_ROOT / "battle_debug.json")
        cls.debug_character_binding = load_binding(
            BINDING_ROOT / "battle_debug_characters.json"
        )
        cls.characters = load_asset("characters.json")
        cls.surfaces = load_surfaces()

    def test_remaining_visible_console_rows_have_one_authored_owner(self) -> None:
        rows = physical("pointer/btl_mes.json")
        bindings = [
            load_binding(BINDING_ROOT / filename)
            for filename in (
                "items.json",
                "magic.json",
                "skills.json",
                "battle_console.json",
            )
        ]
        ownership = [
            set(
                physical_id
                for physical_id in binding.records
                if physical_id.startswith("game.btl_mes.")
            )
            for binding in bindings
        ]
        self.assertEqual(sum(map(len, ownership)), 329)
        self.assertEqual(len(set().union(*ownership)), 329)
        unbound = [row for row in rows if row["id"] not in set().union(*ownership)]
        self.assertEqual(len(unbound), 29)
        self.assertTrue(all(row["reference"] == "" for row in unbound))

        self.assertEqual(len(self.console.entries), 82)
        self.assertEqual(len(self.console_binding.records), 82)
        self.assertEqual(
            set(self.console_binding.records),
            {f"game.btl_mes.p{index:04d}" for index in range(276, 358)},
        )
        self.assertEqual(
            self.console.entries["condition_paralyzed"].fields["text"].translation,
            "PARALYZE",
        )
        self.assertEqual(
            self.console.entries["result_fatal"].fields["text"].translation,
            "ーFATALー{OP:a0}",
        )
        self.assertEqual(
            self.console.entries["result_damage"].fields["text"].translation,
            "Damage_{NUM}{OP:a0}",
        )
        self.assertEqual(
            dict(self.console.entries["result_damage"].placeholders),
            {"NUM": "number"},
        )
        self.assertEqual(dict(self.console_binding.glyph_equivalence), {"4b": "殺"})

    def test_demon_chat_keeps_every_visible_physical_row_distinct(self) -> None:
        rows = physical("pointer/btl_srf.json")
        bound = set(self.demon_chat_binding.records)
        self.assertEqual(len(self.demon_chat.entries), 203)
        self.assertEqual(len(bound), 203)
        self.assertEqual(len(set(self.demon_chat_binding.records.values())), 203)
        self.assertTrue(all(row["reference"] for row in rows if row["id"] in bound))
        unbound = [row for row in rows if row["id"] not in bound]
        self.assertEqual(len(unbound), 160)
        self.assertTrue(all(row["reference"] == "" for row in unbound))

        first = self.demon_chat.entries["dialogue_0000"]
        self.assertEqual(
            first.fields["text"].translation,
            "HEY, SUMMONER...{n}YOU SAY SOMETHING?{demon_name}",
        )
        self.assertEqual(dict(first.placeholders), {"demon_name": "demon_name"})

    def test_condition_messages_partition_between_personalities_and_fallbacks(
        self,
    ) -> None:
        bindings = [
            load_binding(path)
            for path in sorted(BINDING_ROOT.glob("negotiation_*.json"))
        ] + [self.condition_binding]
        ownership = [
            set(
                physical_id
                for physical_id in binding.records
                if physical_id.startswith("game.combat_condition_messages.")
            )
            for binding in bindings
        ]
        physical_ids = {
            row["id"] for row in physical("fixed/combat_condition_messages.json")
        }
        self.assertEqual(sum(map(len, ownership)), 113)
        self.assertEqual(set().union(*ownership), physical_ids)
        self.assertEqual(len(self.conditions.entries), 8)
        self.assertTrue(
            all(
                entry.fields["text"].reviewed
                for entry in self.conditions.entries.values()
            )
        )

    def test_boss_dialogue_is_complete_and_uses_the_negotiation_window(
        self,
    ) -> None:
        rows = physical("eve/bosstalk.json")
        self.assertEqual(len(self.boss_dialogue.entries), 16)
        self.assertEqual(len(self.boss_dialogue_binding.records), 16)
        self.assertEqual(
            set(self.boss_dialogue_binding.records),
            {row["id"] for row in rows},
        )
        self.assertTrue(
            all(
                entry.fields["text"].reviewed
                for entry in self.boss_dialogue.entries.values()
            )
        )
        self.assertEqual(
            self.boss_dialogue.entries["dialogue_0000"]
            .fields["text"]
            .translation,
            "GRRRGH, GRAAAGH!{BEAT}{n}I ain't talking to you!",
        )
        self.assertEqual(
            self.boss_dialogue.entries["dialogue_0012"]
            .fields["text"]
            .translation,
            "EXECUTING ORDERS.{n}STATUS:{BEAT}{OP:8025}O{BEAT}K!!{OP:8020}",
        )
        self.assertEqual(
            dict(self.boss_dialogue_binding.field_surfaces),
            {"text": ("battle.negotiation_dialogue",)},
        )

    def test_help_and_negotiation_choices_are_editable_assets(self) -> None:
        self.assertEqual(len(self.battle_help.entries), 19)
        self.assertEqual(len(self.battle_help_binding.records), 19)
        self.assertEqual(len(self.command_help.entries), 24)
        self.assertEqual(len(self.command_help_binding.records), 24)
        self.assertEqual(
            self.battle_help.entries["fight"].fields["text"].translation,
            "Fight with a demon.",
        )
        self.assertEqual(
            self.command_help.entries["party_setup"].fields["text"].translation,
            "<Party Setup>{n}Summon/return/remove/reposition demons",
        )
        self.assertEqual(
            {
                key: entry.fields["text"].translation
                for key, entry in self.provisioning.entries.items()
            },
            {
                "cash": "Cash",
                "magnetite": "Magnetite",
                "item": "Item",
                "give_nothing": "Nothing",
            },
        )
        self.assertEqual(len(self.provisioning_binding.records), 4)

    def test_debug_text_and_character_forms_partition_the_physical_table(self) -> None:
        physical_ids = {row["id"] for row in physical("addressed/combat_debug.json")}
        debug_ids = set(self.debug_binding.records)
        character_ids = set(self.debug_character_binding.records)
        self.assertEqual(len(self.debug.entries), 12)
        self.assertEqual(len(debug_ids), 12)
        self.assertEqual(len(character_ids), 2)
        self.assertFalse(debug_ids & character_ids)
        self.assertEqual(debug_ids | character_ids, physical_ids)
        self.assertEqual(
            self.characters.entries["kyouji_kuzunoha"]
            .fields["battle_test_name"]
            .translation,
            "Kyouji",
        )
        self.assertEqual(
            self.characters.entries["rei_reiho"]
            .fields["battle_test_name"]
            .translation,
            "Rei",
        )

    def test_battle_surface_contracts_are_explicit(self) -> None:
        expected = {
            "battle.console": (
                ("fnt8x12", 3, "glyph_cells", 16),
                ("fnt8x12", 3, "glyph_cells", 16),
            ),
            "battle.demon_chat": (
                ("font16", 2, "glyph_cells", 11),
                ("font16", 2, "pixels", 176),
            ),
            "battle.help": (
                ("font16", 2, "glyph_cells", 20),
                ("font16", 2, "pixels", 300),
            ),
            "battle.negotiation_choice": (
                ("font16", 1, "glyph_cells", 10),
                ("font16", 1, "pixels", 150),
            ),
            "battle.debug_text": (
                ("font16", 1, None, None),
                ("font16", 1, None, None),
            ),
        }
        for name, (expected_ja, expected_en) in expected.items():
            with self.subTest(surface=name):
                surface = self.surfaces.surface(name)
                actual = lambda layout: (
                    layout.font,
                    layout.rows,
                    layout.width.unit,
                    layout.width.value,
                )
                self.assertEqual(actual(surface.ja), expected_ja)
                self.assertEqual(actual(surface.en), expected_en)


if __name__ == "__main__":
    unittest.main()
