from __future__ import annotations

import hashlib
import json
import struct
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
from util.glyph_sets import load_glyph_sets  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


RACE_KEYS = (
    "deity",
    "megami",
    "herald",
    "avian",
    "tree",
    "enigma",
    "genma",
    "avatar",
    "holy",
    "element",
    "mitama",
    "hero",
    "fury",
    "lady",
    "kishin",
    "dragon",
    "divine",
    "flight",
    "yoma",
    "fairy",
    "snake",
    "beast",
    "uma",
    "jirae",
    "night",
    "fallen",
    "brute",
    "femme",
    "vile",
    "raptor",
    "wood",
    "reaper",
    "wilder",
    "jaki",
    "haunt",
    "vermin",
    "tyrant",
    "drake",
    "ghost",
    "spirit",
    "foul",
    "zoma",
    "human",
)

RACE_REFERENCES = (
    "マジン",
    "メガミ",
    "ダイテンシ",
    "レイチョウ",
    "シンジュ",
    "ヒシン",
    "ゲンマ",
    "シンジュウ",
    "セイジュウ",
    "セイレイ",
    "ミタマ",
    "エイユウ",
    "ハカイシン",
    "ジボシン",
    "キシン",
    "リュウジン",
    "テンシ",
    "ヨウチョウ",
    "ヨウマ",
    "ヨウセイ",
    "リュウオウ",
    "マジュウ",
    "チンジュウ",
    "チレイ",
    "ヤマ",
    "ダテンシ",
    "ヨウキ",
    "キジョ",
    "ジャシン",
    "キョウチョウ",
    "ヨウジュ",
    "シニガミ",
    "ヨウジュウ",
    "ジャキ",
    "シキ",
    "ヨウチュウ",
    "マオウ",
    "ジャリュウ",
    "ユウキ",
    "アクリョウ",
    "ゲドウ",
    "ゾウマ",
    "ヒト",
)

ASCII_FIELDS = {
    "detail_level": (0xD284, 4, "LV"),
    "detail_hit_points": (0xD288, 4, "HP"),
    "detail_magic_points": (0xD28C, 4, "MP"),
    "detail_summon_cost": (0xD290, 4, "CP"),
    "axis_law_light": (0xD4C8, 4, "L"),
    "axis_chaos": (0xD4CC, 4, "C"),
    "axis_dark": (0xD4D0, 4, "D"),
    "axis_neutral": (0xD4D4, 2, "N"),
    "magic_cost_unit": (0xE590, 4, "M"),
    "health_cost_unit": (0xE594, 2, "H"),
    "grid_race_heading": (0xF7DC, 8, "RACE"),
    "grid_name_heading": (0xF7E4, 8, "NAME"),
    "grid_level_heading": (0xF7EC, 4, "LV"),
    "grid_hit_points_heading": (0xF7F0, 4, "HP"),
    "grid_magic_points_heading": (0xF7F4, 4, "MP"),
    "grid_attack_heading": (0xF7F8, 4, "ATK"),
    "grid_defense_heading": (0xF7FC, 4, "DEF"),
}


class Map3dAnalyzeAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asset = load_asset("ui/map_3d_analyze.json")
        cls.status = load_asset("ui/status.json")
        cls.races = load_asset("races.json")
        cls.alignments = load_asset("terminology/alignments.json")
        cls.binding = load_binding(BINDING_ROOT / "map_3d_analyze.json")
        cls.status_binding = load_binding(
            BINDING_ROOT / "map_3d_analyze_status.json"
        )
        cls.race_binding = load_binding(BINDING_ROOT / "races.json")
        cls.alignment_binding = load_binding(BINDING_ROOT / "alignments.json")
        cls.rows = json.loads(
            (
                TEXT_ROOT
                / "corpus/game/addressed/da3d_analyze.json"
            ).read_text(encoding="utf-8")
        )

        validated = validate_source(load_catalog()["game"])
        cls.da3d = read_source_files(validated, ("DA_3D.BIN",))["DA_3D.BIN"]

    def test_analyze_asset_owns_only_surface_specific_complete_text(self) -> None:
        self.assertEqual(
            tuple(self.asset.entries),
            (
                "race_heading",
                "name_heading",
                "attack_heading",
                "defense_heading",
                "magic_cost",
                "health_cost",
            ),
        )
        self.assertEqual(
            {
                key: (
                    entry.fields["text"].reference,
                    entry.fields["text"].translation,
                )
                for key, entry in self.asset.entries.items()
            },
            {
                "race_heading": ("RACE", "RACE"),
                "name_heading": ("NAME", "NAME"),
                "attack_heading": ("ATK", "ATK"),
                "defense_heading": ("DEF", "DEF"),
                "magic_cost": ("{cost}M", "{cost}M"),
                "health_cost": ("{cost}H", "{cost}H"),
            },
        )
        for key in ("magic_cost", "health_cost"):
            self.assertEqual(
                dict(self.asset.entries[key].placeholders),
                {"cost": "number"},
            )
        self.assertIn("IDs through 159", self.asset.entries["magic_cost"].note or "")
        self.assertIn("IDs above 159", self.asset.entries["health_cost"].note or "")

    def test_generated_corpus_has_all_43_races_and_17_ascii_records(self) -> None:
        self.assertEqual(len(self.rows), 60)
        self.assertEqual(
            [row["reference"] for row in self.rows[:43]],
            list(RACE_REFERENCES),
        )
        self.assertTrue(
            all(
                row["source_encoding"] == "game_font8_plain_glyph"
                for row in self.rows[:43]
            )
        )
        addressed = self.rows[43:]
        self.assertEqual(
            [row["reference"] for row in addressed],
            [value[2] for value in ASCII_FIELDS.values()],
        )
        self.assertTrue(
            all(row["source_encoding"] == "ascii" for row in addressed)
        )
        self.assertEqual(
            {row["id"] for row in self.rows[:43]},
            {
                f"game.da3d_analyze.grid_races.r{index:04d}"
                for index in range(43)
            },
        )

    def test_manifest_and_stock_disc_pin_every_physical_record(self) -> None:
        manifest = load_manifest(manifest_path("game"))
        source = next(item for item in manifest.sources if item.name == "da3d_analyze")
        self.assertEqual(
            source.corpus_path,
            PurePosixPath("addressed/da3d_analyze.json"),
        )
        self.assertEqual(
            source.container["tables"],
            [
                {
                    "name": "grid_races",
                    "count": 43,
                    "source_encoding": "game_font8_plain_glyph",
                    "framing": {"type": "zero_padded"},
                    "require_identical_bytes": False,
                    "locations": [
                        {"base": "0x4517c", "stride": "0x6", "units": 6}
                    ],
                }
            ],
        )
        fields = {}
        for record in source.container["records"]:
            span = record["locations"][0]["spans"][0]
            fields[record["name"]] = (
                int(span["offset"], 16),
                span["units"],
            )
        self.assertEqual(
            fields,
            {
                name: (offset, units)
                for name, (offset, units, _reference) in ASCII_FIELDS.items()
            },
        )

        race_bytes = self.da3d[0x4517C:0x4527E]
        self.assertEqual(len(race_bytes), 43 * 6)
        self.assertEqual(
            hashlib.sha256(race_bytes).hexdigest(),
            "fb2d01194650e10ce6fadb42fbab07e5bd63678818c1bdc61acc74e81ed2c881",
        )
        for offset, units, reference in ASCII_FIELDS.values():
            raw = self.da3d[offset : offset + units]
            visible = raw.split(b"\0", 1)[0]
            self.assertEqual(visible.decode("ascii"), reference)
            self.assertEqual(raw[len(visible) : len(visible) + 1], b"\0")

    def test_every_physical_record_has_one_semantic_owner(self) -> None:
        corpus_ids = {row["id"] for row in self.rows}
        bindings = (
            self.binding,
            self.status_binding,
            self.race_binding,
            self.alignment_binding,
        )
        owned = {
            physical_id
            for binding in bindings
            for physical_id in binding.records
            if physical_id.startswith("game.da3d_analyze.")
        }
        self.assertEqual(owned, corpus_ids)
        self.assertEqual(
            {
                physical_id: variant
                for physical_id, variant in self.race_binding.variants.items()
                if physical_id.startswith("game.da3d_analyze.grid_races.")
            },
            {
                f"game.da3d_analyze.grid_races.r{index:04d}": "analyze_grid"
                for index in range(43)
            },
        )
        for index, key in enumerate(RACE_KEYS):
            physical_id = f"game.da3d_analyze.grid_races.r{index:04d}"
            self.assertEqual(self.race_binding.records[physical_id], f"{key}.name")
            reference, translation, _reviewed = self.races.entries[key].fields[
                "name"
            ].resolve("analyze_grid")
            self.assertEqual(reference, RACE_REFERENCES[index])
            self.assertEqual(
                translation,
                self.races.entries[key].fields["name"].translation,
            )

    def test_shared_status_templates_and_cost_composition_are_explicit(self) -> None:
        self.assertEqual(
            dict(self.status_binding.records),
            {
                "game.da3d_analyze.o00d284": "level.text",
                "game.da3d_analyze.o00d288": "hit_points.text",
                "game.da3d_analyze.o00d28c": "magic_points.text",
                "game.da3d_analyze.o00d290": "summon_cost.text",
                "game.da3d_analyze.o00f7ec": "level.text",
                "game.da3d_analyze.o00f7f0": "hit_points.text",
                "game.da3d_analyze.o00f7f4": "magic_points.text",
            },
        )
        self.assertEqual(self.status.field("level.text").translation, "LV {level}")
        self.assertEqual(
            self.status.field("hit_points.text").translation,
            "HP {current_hp}/{maximum_hp}",
        )
        self.assertEqual(
            self.status.field("magic_points.text").translation,
            "MP {current_mp}/{maximum_mp}",
        )
        self.assertEqual(
            self.status.field("summon_cost.text").translation,
            "CP {summon_cost}",
        )
        self.assertTrue(
            all(
                composition.source_role == "prefix"
                for composition in self.status_binding.composition.values()
            )
        )
        self.assertEqual(
            {
                physical_id: (
                    composition.source_role,
                    composition.supplies,
                )
                for physical_id, composition in self.binding.composition.items()
            },
            {
                "game.da3d_analyze.o00e590": ("suffix", ("cost",)),
                "game.da3d_analyze.o00e594": ("suffix", ("cost",)),
            },
        )

        # The stock branch compares against ability id 159, then selects the
        # M pointer for the lower domain and H for the upper domain.
        self.assertEqual(self.da3d[0xE6E6:0xE6E8], b"\x00\x9f")
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xE700)[0], 0x0602E590)
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xE720)[0], 0x0602E594)

    def test_dynamic_entity_relations_reuse_existing_authored_catalogues(self) -> None:
        demons = load_asset("demons.json")
        magic = load_asset("magic.json")
        skills = load_asset("skills.json")
        items = load_asset("items.json")
        demon_binding = load_binding(BINDING_ROOT / "demons.json")
        magic_binding = load_binding(BINDING_ROOT / "magic.json")
        skill_binding = load_binding(BINDING_ROOT / "skills.json")
        affinity_binding = load_binding(BINDING_ROOT / "affinities.json")
        item_binding = load_binding(BINDING_ROOT / "items.json")

        self.assertEqual(len(demons.entries), 312)
        self.assertEqual(
            sum(
                physical_id.startswith("game.dvlname.")
                for physical_id in demon_binding.records
            ),
            319,
        )
        self.assertEqual(len(magic.entries), 79)
        self.assertEqual(len(skills.entries), 178)
        self.assertEqual(len(items.entries), 73)
        self.assertIn(
            "map_3d.analyze_demon_name",
            demon_binding.field_surfaces["name"],
        )
        self.assertIn("status.demon_name", demon_binding.field_surfaces["name"])
        self.assertIn("map_3d.analyze_race", self.race_binding.field_surfaces["name"])
        self.assertIn("status.demon_race", self.race_binding.field_surfaces["name"])
        self.assertIn("status.skill_name", magic_binding.field_surfaces["name"])
        self.assertIn("status.skill_name", skill_binding.field_surfaces["name"])
        self.assertIn("status.affinity", affinity_binding.field_surfaces["description"])
        self.assertFalse(
            any(
                surface.startswith("map_3d.analyze")
                for surfaces in item_binding.field_surfaces.values()
                for surface in surfaces
            )
        )

    def test_law_and_light_are_independent_despite_the_stock_alias(self) -> None:
        shared_id = "game.da3d_analyze.o00d4c8"
        self.assertEqual(self.alignment_binding.records[shared_id], "law.axis_label")
        self.assertEqual(
            tuple(
                (use.asset_ref, use.variant, use.composition)
                for use in self.alignment_binding.additional_uses[shared_id]
            ),
            (("light.axis_label", None, None),),
        )
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xD554)[0], 0x0602D4C8)
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xD560)[0], 0x0602D4CC)
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xD564)[0], 0x0602D4D0)
        self.assertEqual(struct.unpack_from(">I", self.da3d, 0xD568)[0], 0x0602D4D4)
        self.assertIn(
            "remain independent",
            self.alignments.entries["law"].fields["axis_label"].note or "",
        )
        self.assertIn(
            "independently editable",
            self.alignments.entries["light"].fields["axis_label"].note or "",
        )

    def test_surface_geometry_and_stock_latin_handlers_are_grounded(self) -> None:
        surfaces = load_surfaces()
        expected = {
            "map_3d.analyze_grid.race_heading": (1, "pixels", 52),
            "map_3d.analyze_grid.name_heading": (1, "pixels", 76),
            "map_3d.analyze_grid.level_heading": (1, "pixels", 46),
            "map_3d.analyze_grid.hit_points_heading": (1, "pixels", 34),
            "map_3d.analyze_grid.magic_points_heading": (1, "pixels", 28),
            "map_3d.analyze_grid.attack_heading": (1, "pixels", 36),
            "map_3d.analyze_grid.defense_heading": (1, "pixels", 52),
            "map_3d.analyze_race": (1, "pixels", 52),
            "map_3d.analyze_demon_name": (1, "pixels", 84),
            "map_3d.analyze_detail.numeric_readout": (1, "pixels", 96),
            "map_3d.analyze_detail.skill_cost": (1, "pixels", 16),
            "map_3d.analyze_detail.skill_list": (6, "pixels", 96),
            "status.demon_name": (1, "pixels", 126),
            "status.demon_race": (1, "pixels", 46),
            "status.skill_name": (1, "pixels", 80),
            "status.affinity": (2, "pixels", 128),
            "status.alignment_axis_label": (1, "glyph_cells", 1),
        }
        for name, (rows, unit, width) in expected.items():
            with self.subTest(surface=name):
                surface = surfaces.surface(name)
                self.assertEqual(
                    (surface.en.rows, surface.en.width.unit, surface.en.width.value),
                    (rows, unit, width),
                )

        signed_header_x = struct.unpack_from(">7h", self.da3d, 0xF7CC)
        self.assertEqual(signed_header_x, (-148, -96, -20, 26, 60, 88, 124))
        header_x = tuple(value + 176 for value in signed_header_x)
        self.assertEqual(header_x, (28, 80, 156, 202, 236, 264, 300))
        self.assertEqual(
            tuple(right - left for left, right in zip(header_x, (*header_x[1:], 352))),
            (52, 76, 46, 34, 28, 36, 52),
        )

        def descriptor_size(index: int) -> tuple[int, int]:
            return struct.unpack_from(">HH", self.da3d, 0x43E30 + index * 16)

        self.assertEqual(descriptor_size(20), (96, 60))
        self.assertEqual(descriptor_size(21), (128, 16))
        self.assertEqual(descriptor_size(22), (48, 16))
        self.assertEqual(descriptor_size(34), (96, 80))
        self.assertEqual(
            tuple(descriptor_size(index) for index in range(35, 40)),
            ((8, 8),) * 5,
        )
        self.assertEqual(descriptor_size(40), (128, 32))

        glyph_sets = load_glyph_sets()
        stock_latin = {
            "map_3d.analyze_grid.race_heading",
            "map_3d.analyze_grid.name_heading",
            "map_3d.analyze_grid.level_heading",
            "map_3d.analyze_grid.hit_points_heading",
            "map_3d.analyze_grid.magic_points_heading",
            "map_3d.analyze_grid.attack_heading",
            "map_3d.analyze_grid.defense_heading",
            "map_3d.analyze_detail.numeric_readout",
            "map_3d.analyze_detail.skill_cost",
            "status.alignment_axis_label",
        }
        for surface in stock_latin:
            with self.subTest(glyph_handler=surface):
                handler = glyph_sets.for_surface(surface)
                self.assertIsNotNone(handler)
                self.assertEqual(
                    (handler.font, handler.reference_set),
                    ("font8", "stock_latin"),
                )
        self.assertIsNone(glyph_sets.for_surface("map_3d.analyze_race"))
        self.assertIsNone(glyph_sets.for_surface("map_3d.analyze_demon_name"))


if __name__ == "__main__":
    unittest.main()
