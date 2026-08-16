from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEXT_ROOT.parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


EXPECTED_TEXT = {
    "strength": ("力", "St"),
    "intelligence": ("知", "In"),
    "magic": ("魔", "Ma"),
    "vitality": ("耐", "Vi"),
    "agility": ("速", "Ag"),
    "luck": ("運", "Lu"),
    "sword_attack": ("剣攻撃力", "Swd Atk"),
    "sword_accuracy": ("剣命中力", "Swd Acc"),
    "gun_attack": ("銃攻撃力", "Gun Atk"),
    "gun_accuracy": ("銃命中力", "Gun Acc"),
    "defense": ("防衛力", "Def"),
    "evasion": ("回避力", "Eva"),
    "magic_power": ("魔法威力", "Mag Pwr"),
    "magic_defense": ("魔法防衛", "Mag Efc"),
    "attack": ("攻撃力", "Attack"),
    "accuracy": ("命中力", "Accuracy"),
    "loyalty": ("忠誠度 {loyalty}", "Loyalty {loyalty}"),
    "personality_type": (
        "TYPE {personality}",
        "TYPE {personality}",
    ),
    "personality_sturdy": ("剛健", "Sturdy"),
    "personality_fierce": ("凶暴", "Fierce"),
    "personality_impatient": ("短気", "Impatient"),
    "personality_sly": ("狡猾", "Sly"),
    "personality_prideful": ("高慢", "Prideful"),
    "personality_gentle": ("温順", "Gentle"),
    "personality_cowardly": ("臆病", "Cowardly"),
    "personality_calm": ("冷静", "Calm"),
    "personality_cautious": ("慎重", "Cautious"),
    "personality_impartial": ("虚心", "Impartial"),
    "level": ("LV {level}", "LV {level}"),
    "hit_points": (
        "HP {current_hp}/{maximum_hp}",
        "HP {current_hp}/{maximum_hp}",
    ),
    "magic_points": (
        "MP {current_mp}/{maximum_mp}",
        "MP {current_mp}/{maximum_mp}",
    ),
    "experience": ("EXP {experience}", "EXP {experience}"),
    "next_experience": (
        "NEXT {experience_to_next}",
        "NEXT {experience_to_next}",
    ),
    "summon_cost": ("CP {summon_cost}", "CP {summon_cost}"),
    "auto_setting": ("AUTO {command}", "AUTO {command}"),
    "party_alignment": ("P.A. {alignment}", "P.A. {alignment}"),
    "control": ("CTRL {rank}", "CTRL {rank}"),
    "control_first": ("1ST", "1ST"),
    "control_second": ("2ND", "2ND"),
    "control_third": ("3RD", "3RD"),
    "control_fourth": ("4TH", "4TH"),
    "control_error": ("ERR", "ERR"),
}

EXPECTED_COMMANDS = {
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


class StatusAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("ui/status.json")
        cls.commands = load_asset("battle/commands.json")
        cls.alignments = load_asset("terminology/alignments.json")
        cls.binding = load_binding(BINDING_ROOT / "status.json")
        cls.command_binding = load_binding(BINDING_ROOT / "battle_commands.json")
        cls.alignment_binding = load_binding(BINDING_ROOT / "alignments.json")
        cls.surfaces = load_surfaces()

    def test_complete_saturn_status_vocabulary_uses_mature_output(self) -> None:
        self.assertEqual(tuple(self.catalog.entries), tuple(EXPECTED_TEXT))
        self.assertEqual(
            {
                key: (entry.fields["text"].reference, entry.fields["text"].translation)
                for key, entry in self.catalog.entries.items()
            },
            EXPECTED_TEXT,
        )
        for entry in self.catalog.entries.values():
            self.assertEqual(set(entry.fields), {"text"})
            self.assertFalse(entry.fields["text"].reviewed)
            self.assertEqual(dict(entry.fields["text"].variants), {})

        self.assertEqual(
            {
                key: entry.fields["name"].translation
                for key, entry in self.commands.entries.items()
            },
            EXPECTED_COMMANDS,
        )
        self.assertEqual(
            {
                key: frozenset(entry.fields)
                for key, entry in self.alignments.entries.items()
            },
            {
                "law": frozenset({"party_label", "axis_label"}),
                "neutral": frozenset({"party_label", "axis_label"}),
                "chaos": frozenset({"party_label", "axis_label"}),
                "light": frozenset({"axis_label"}),
                "dark": frozenset({"axis_label"}),
            },
        )

    def test_dynamic_rows_and_value_domains_are_typed_and_editable(self) -> None:
        expected_placeholders = {
            "loyalty": {"loyalty": "number"},
            "personality_type": {"personality": "personality_label"},
            "level": {"level": "number"},
            "hit_points": {
                "current_hp": "number",
                "maximum_hp": "number",
            },
            "magic_points": {
                "current_mp": "number",
                "maximum_mp": "number",
            },
            "experience": {"experience": "number"},
            "next_experience": {"experience_to_next": "number"},
            "summon_cost": {"summon_cost": "number"},
            "auto_setting": {"command": "battle_command"},
            "party_alignment": {"alignment": "alignment_label"},
            "control": {"rank": "control_rank"},
        }
        self.assertEqual(
            {
                key: dict(self.catalog.entries[key].placeholders)
                for key in expected_placeholders
            },
            expected_placeholders,
        )

    def test_all_retail_ascii_status_strings_have_semantic_bindings(self) -> None:
        corpus_ids = {
            row["id"]
            for row in json.loads(
                (
                    TEXT_ROOT
                    / "corpus"
                    / "game"
                    / "addressed"
                    / "normcom_status_ascii.json"
                ).read_text(encoding="utf-8")
            )
        }
        status_command_ids = {
            physical_id
            for physical_id in self.command_binding.records
            if physical_id.startswith("game.normcom_status_ascii.")
        }
        status_alignment_ids = {
            physical_id
            for physical_id in self.alignment_binding.records
            if physical_id.startswith("game.normcom_status_ascii.")
        }
        bound_ids = set(self.binding.records) | status_command_ids | status_alignment_ids
        self.assertEqual(len(corpus_ids), 24)
        self.assertEqual(bound_ids, corpus_ids)
        self.assertEqual(len(self.binding.records), 14)
        self.assertEqual(len(status_command_ids), 7)
        self.assertEqual(len(status_alignment_ids), 3)
        self.assertEqual(
            {
                physical_id: composition.source_role
                for physical_id, composition in self.binding.composition.items()
            },
            {
                physical_id: "prefix"
                for physical_id in self.binding.composition
            },
        )
        self.assertEqual(len(self.binding.composition), 9)

    def test_stock_bitmap_sources_are_pinned_without_becoming_corpus_rows(self) -> None:
        validated = validate_source(load_catalog()["game"])
        source = read_source_files(validated, ("NORMCOM.BIN",))["NORMCOM.BIN"]
        self.assertEqual(
            hashlib.sha256(source).hexdigest(),
            "983d84ad48c0a497715633c0d2e380743c52e4b1644422ed027ac27e52a2aa9a",
        )
        expected_regions = {
            (0x2376C, 0x23BEC): (
                "86c69aedbccf3b6417f9d544b86d2718ffc6ad705b00b019769dedcb735c79aa"
            ),
            (0x23BEC, 0x2406C): (
                "d7c9a5237611fd0953a7838b24ddb754e9d2354c104d2a8c8283f956e5ce37d9"
            ),
            (0x2406C, 0x269AC): (
                "9ce5065a769443c3b6075eae19ff42ec207b16b135e61b29e65b91b64bd48bc9"
            ),
        }
        self.assertEqual(
            {
                region: hashlib.sha256(source[slice(*region)]).hexdigest()
                for region in expected_regions
            },
            expected_regions,
        )

    def test_status_surface_limits_match_the_mature_renderer(self) -> None:
        expected = {
            "status.base_stat_label": (
                (None, 1, "glyph_cells", 1),
                ("font8", 1, "pixels", 12),
            ),
            "status.derived_stat_label": (
                ("font12", 1, "glyph_cells", 4),
                ("font8", 1, "pixels", 46),
            ),
            "status.generic_combat_stat_label": (
                ("font12", 1, "glyph_cells", 3),
                ("font8", 1, "pixels", 46),
            ),
            "status.loyalty_label": (
                ("font12", 1, "glyph_cells", 3),
                ("font8", 1, "pixels", 38),
            ),
            "status.personality_type_label": (
                ("font8", 1, "glyph_cells", 4),
                ("font8", 1, "glyph_cells", 4),
            ),
            "status.personality_value": (
                ("font12", 1, "glyph_cells", 2),
                ("font8", 1, "pixels", 38),
            ),
            "status.numeric_readout": (
                ("font8", 1, None, None),
                ("font8", 1, None, None),
            ),
            "status.auto_setting": (
                ("font8", 1, "glyph_cells", 12),
                ("font8", 1, "glyph_cells", 12),
            ),
            "status.party_alignment": (
                ("font8", 1, "glyph_cells", 12),
                ("font8", 1, "glyph_cells", 12),
            ),
            "status.control": (
                ("font8", 1, "glyph_cells", 10),
                ("font8", 1, "glyph_cells", 10),
            ),
            "status.loyalty_row": (
                (None, 1, None, None),
                ("font8", 1, None, None),
            ),
            "status.personality_row": (
                (None, 1, None, None),
                ("font8", 1, None, None),
            ),
            "status.control_rank": (
                ("font8", 1, "glyph_cells", 3),
                ("font8", 1, "glyph_cells", 3),
            ),
            "status.auto_command": (
                ("font8", 1, "glyph_cells", 7),
                ("font8", 1, "glyph_cells", 7),
            ),
            "status.party_alignment_value": (
                ("font8", 1, "glyph_cells", 7),
                ("font8", 1, "glyph_cells", 7),
            ),
            "status.alignment_axis_label": (
                ("font8", 1, "glyph_cells", 1),
                ("font8", 1, "glyph_cells", 1),
            ),
        }
        for name, (expected_ja, expected_en) in expected.items():
            with self.subTest(surface=name):
                surface = self.surfaces.surface(name)
                self.assertEqual(
                    (
                        surface.ja.font,
                        surface.ja.rows,
                        surface.ja.width.unit,
                        surface.ja.width.value,
                    ),
                    expected_ja,
                )
                self.assertEqual(
                    (
                        surface.en.font,
                        surface.en.rows,
                        surface.en.width.unit,
                        surface.en.width.value,
                    ),
                    expected_en,
                )

    def test_composite_status_spans_do_not_hide_component_slots(self) -> None:
        expected = {
            "status.auto_setting": (12, "status.auto_command", 7, 5),
            "status.party_alignment": (
                12,
                "status.party_alignment_value",
                7,
                5,
            ),
            "status.control": (10, "status.control_rank", 3, 7),
        }
        for row_name, (
            row_cells,
            value_name,
            value_cells,
            value_start,
        ) in expected.items():
            with self.subTest(surface=row_name):
                row = self.surfaces.surface(row_name).en
                value = self.surfaces.surface(value_name).en
                self.assertEqual(
                    (row.width.unit, row.width.value),
                    ("glyph_cells", row_cells),
                )
                self.assertEqual(
                    (value.width.unit, value.width.value),
                    ("glyph_cells", value_cells),
                )
                self.assertEqual(row_cells - value_cells, value_start)

        for row_name in (
            "status.numeric_readout",
            "status.loyalty_row",
            "status.personality_row",
        ):
            with self.subTest(unbounded_surface=row_name):
                self.assertFalse(self.surfaces.surface(row_name).en.width.known)

    def test_compression_hints_are_not_translator_vocabulary(self) -> None:
        authored = {
            field.translation
            for entry in self.catalog.entries.values()
            for field in entry.fields.values()
        }
        self.assertTrue(
            {
                "Nulls: Expel",
                "Demon attacks",
                "Demon Atk",
                "Other magic",
            }.isdisjoint(authored)
        )


if __name__ == "__main__":
    unittest.main()
