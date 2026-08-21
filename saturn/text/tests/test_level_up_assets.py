from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402


LEVEL_UP_IDS = (
    "game.level_up_system.o0079a4",
    "game.level_up_system.o0079a8",
    "game.level_up_system.o0079ac",
    "game.level_up_system.o0079b0",
    "game.level_up_system.o0079b4",
    "game.level_up_system.o008478",
    "game.level_up_system.o008488",
    "game.level_up_system.o008e1c",
    "game.level_up_system.o008e21",
    "game.level_up_system.o008e24",
    "game.level_up_system.o008f2c",
)


class LevelUpAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("ui/level_up.json")
        cls.status = load_asset("ui/status.json")
        cls.binding = load_binding(BINDING_ROOT / "level_up.json")
        cls.status_binding = load_binding(BINDING_ROOT / "level_up_status.json")
        cls.rows = json.loads(
            (TEXT_ROOT / "corpus/game/addressed/level_up_system.json").read_text(
                encoding="utf-8"
            )
        )

    def test_human_facing_catalog_is_complete_and_typed(self) -> None:
        self.assertEqual(
            set(self.catalog.entries),
            {
                "title",
                "remaining_points",
                "max_level_next",
                "no_magic_points",
                "accept",
                "confirm_yes",
                "confirm_no",
                "learned_magic_heading",
            },
        )
        self.assertEqual(
            {
                name: (
                    entry.fields["text"].reference,
                    entry.fields["text"].translation,
                )
                for name, entry in self.catalog.entries.items()
            },
            {
                "title": ("LEVEL UP", "LEVEL UP"),
                "remaining_points": (
                    "{remaining_points} LEFT",
                    "{remaining_points} LEFT",
                ),
                "max_level_next": ("-------", "-------"),
                "no_magic_points": ("---/---", "---/---"),
                "accept": ("OK", "OK"),
                "confirm_yes": ("YES", "YES"),
                "confirm_no": ("NO", "NO"),
                "learned_magic_heading": ("魔法を習得", "Learned Magic"),
            },
        )
        remaining = self.catalog.entries["remaining_points"]
        self.assertEqual(
            dict(remaining.placeholders),
            {"remaining_points": "number"},
        )
        self.assertIn("graphical ornament", remaining.note or "")
        self.assertIn(
            "constructs this at runtime",
            self.catalog.entries["max_level_next"].note or "",
        )
        self.assertIn(
            "constructs this at runtime",
            self.catalog.entries["no_magic_points"].note or "",
        )
        self.assertIn(
            "fixed alignment cell",
            self.catalog.entries["no_magic_points"].note or "",
        )

    def test_all_visible_level_up_records_are_catalogued_without_layout_blanks(
        self,
    ) -> None:
        self.assertEqual(tuple(row["id"] for row in self.rows), LEVEL_UP_IDS)
        self.assertEqual(
            [row["reference"] for row in self.rows],
            [
                "LV",
                "HP",
                "MP",
                "EXP",
                "NEXT",
                "LEVEL UP",
                "LEFT",
                "YES",
                "NO",
                "OK",
                "魔法を習得",
            ],
        )
        self.assertTrue(
            all(
                row["source_encoding"] == "ascii"
                for row in self.rows[:-1]
            )
        )
        self.assertEqual(
            self.rows[-1]["source_encoding"], "game_font16_plain_skip"
        )
        self.assertTrue(
            all(row["reference"] == row["reference"].strip() for row in self.rows)
        )

    def test_manifest_owns_exact_physical_fields(self) -> None:
        manifest = load_manifest(manifest_path("game"))
        source = next(
            item for item in manifest.sources if item.name == "level_up_system"
        )
        fields = {}
        for record in source.container["records"]:
            self.assertEqual(len(record["locations"]), 1)
            spans = record["locations"][0]["spans"]
            self.assertEqual(len(spans), 1)
            span = spans[0]
            fields[record["name"]] = (
                int(span["offset"], 16),
                span["units"],
                record.get("source_encoding"),
                record["framing"]["type"],
            )
        self.assertEqual(
            fields,
            {
                "level": (0x79A4, 4, "ascii", "zero_terminated"),
                "hit_points": (0x79A8, 4, "ascii", "zero_terminated"),
                "magic_points": (0x79AC, 4, "ascii", "zero_terminated"),
                "experience": (0x79B0, 4, "ascii", "zero_terminated"),
                "next_experience": (0x79B4, 6, "ascii", "zero_terminated"),
                "title": (0x8478, 12, "ascii", "zero_terminated"),
                "remaining_points_label": (
                    0x8488,
                    6,
                    "ascii",
                    "zero_terminated",
                ),
                "confirm_yes": (0x8E1C, 4, "ascii", "zero_terminated"),
                "confirm_no": (0x8E21, 3, "ascii", "zero_terminated"),
                "accept": (0x8E24, 4, "ascii", "zero_terminated"),
                "learned_magic_heading": (
                    0x8F2C,
                    6,
                    "game_font16_plain_skip",
                    "terminated",
                ),
            },
        )

        validated = validate_source(load_catalog()["game"])
        data = read_source_files(validated, ("LEVEL_UP.BIN",))["LEVEL_UP.BIN"]
        self.assertEqual(data[0x8484:0x8488], b"    ")
        self.assertEqual(data[0x8488:0x848E], b"LEFT\0\0")
        self.assertEqual(data[0x8E20:0x8E24], b" NO\0")

    def test_ui_and_reused_status_bindings_have_one_exact_owner(self) -> None:
        self.assertEqual(self.binding.asset, PurePosixPath("ui/level_up.json"))
        self.assertEqual(
            dict(self.binding.records),
            {
                "game.level_up_system.o008478": "title.text",
                "game.level_up_system.o008488": "remaining_points.text",
                "game.level_up_system.o008e1c": "confirm_yes.text",
                "game.level_up_system.o008e21": "confirm_no.text",
                "game.level_up_system.o008e24": "accept.text",
                "game.level_up_system.o008f2c": "learned_magic_heading.text",
            },
        )
        remaining = self.binding.composition["game.level_up_system.o008488"]
        self.assertEqual(
            (remaining.source_role, remaining.supplies),
            ("suffix", ("remaining_points",)),
        )

        self.assertEqual(
            self.status_binding.asset,
            PurePosixPath("ui/status.json"),
        )
        self.assertEqual(
            dict(self.status_binding.records),
            {
                "game.level_up_system.o0079a4": "level.text",
                "game.level_up_system.o0079a8": "hit_points.text",
                "game.level_up_system.o0079ac": "magic_points.text",
                "game.level_up_system.o0079b0": "experience.text",
                "game.level_up_system.o0079b4": "next_experience.text",
            },
        )
        expected_supplies = {
            "game.level_up_system.o0079a4": ("level",),
            "game.level_up_system.o0079a8": ("current_hp", "maximum_hp"),
            "game.level_up_system.o0079ac": ("current_mp", "maximum_mp"),
            "game.level_up_system.o0079b0": ("experience",),
            "game.level_up_system.o0079b4": ("experience_to_next",),
        }
        self.assertEqual(
            {
                physical_id: (composition.source_role, composition.supplies)
                for physical_id, composition in self.status_binding.composition.items()
            },
            {
                physical_id: ("prefix", supplies)
                for physical_id, supplies in expected_supplies.items()
            },
        )
        self.assertEqual(
            set(self.binding.records) | set(self.status_binding.records),
            set(LEVEL_UP_IDS),
        )
        self.assertTrue(
            {
                "max_level_next.text",
                "no_magic_points.text",
            }.isdisjoint(self.binding.records.values())
        )
        self.assertTrue(
            all(
                surfaces == ("level_up.numeric_readout",)
                for surfaces in self.status_binding.record_surfaces.values()
            )
        )

    def test_existing_assets_supply_names_and_parameter_vocabulary(self) -> None:
        characters = load_binding(BINDING_ROOT / "characters.json")
        magic = load_binding(BINDING_ROOT / "magic.json")
        skills = load_binding(BINDING_ROOT / "skills.json")
        self.assertIn("level_up.character_name", characters.field_surfaces["name"])
        self.assertIn("level_up.ability_name", magic.field_surfaces["name"])
        self.assertIn("level_up.ability_name", skills.field_surfaces["name"])
        self.assertEqual(
            self.status.field("level.text").translation,
            "LV {level}",
        )

    def test_fixed_font8_fields_explicitly_select_the_stock_latin_face(self) -> None:
        for catalog, refs in (
            (self.status, (
                "level.text", "hit_points.text", "magic_points.text",
                "experience.text", "next_experience.text",
            )),
            (self.catalog, (
                "max_level_next.text", "no_magic_points.text", "title.text",
                "remaining_points.text", "accept.text", "confirm_yes.text",
                "confirm_no.text",
            )),
        ):
            for ref in refs:
                with self.subTest(ref=ref):
                    self.assertEqual(catalog.field(ref).font8_alphabet, "original")
        self.assertEqual(
            self.catalog.field("learned_magic_heading.text").font8_alphabet,
            "replaced",
        )


if __name__ == "__main__":
    unittest.main()
