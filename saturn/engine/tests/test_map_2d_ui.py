from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path, PurePosixPath
from unittest.mock import patch

SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from text.util.event_repack import FontMetrics

import engine.surfaces.map_2d_ui as map_2d
from engine.shared.player_names import PLAYER_NAME_FIELD_BY_KEY

MATURE_HASH = "dce250711d7a596bb6c675c76c8cc30542181f00570c5bd4a92d3b7eca6b1123"


class Map2dUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = map_2d._stock_source()
        cls.build = map_2d.build_map_2d_ui()
        cls.patches = {row.name: row for row in cls.build.patches}
        cls.config = map_2d._configuration()
        cls.runtime = map_2d._build_runtime(cls.config)
        cls.metrics = FontMetrics.load(map_2d.FONT16_METRICS_PATH)
        cls.terms = dict(map_2d._bound_terms())
        cls.templates = dict(map_2d._map_templates())

    def test_mature_output_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.build.data), 126_600)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), MATURE_HASH)
        self.assertEqual(len(self.build.patches), 24)
        self.assertEqual(
            tuple(dict.fromkeys(row.group for row in self.build.patches)),
            (
                "map_2d.runtime",
                "map_2d.prompt",
                "map_2d.labels",
                "map_2d.layout",
            ),
        )

    def test_three_runtime_arenas_reproduce_the_mature_layout(self) -> None:
        name = self.patches["name_runtime_arena"].replacement
        prompt = self.patches["prompt_runtime"].replacement
        data = self.patches["bitmap_data_arena"].replacement
        self.assertEqual(len(name), map_2d.NAME_RUNTIME_CAPACITY)
        self.assertEqual(len(prompt), map_2d.PROMPT_RUNTIME_CAPACITY)
        self.assertEqual(len(data), map_2d.BITMAP_ARENA_CAPACITY)
        self.assertEqual(
            hashlib.sha256(name).hexdigest(),
            "2e6b53c63cf04d1dea132fc3e6440cd4bddd348d3637a986c2796f62e33b5ac5",
        )
        self.assertEqual(
            hashlib.sha256(prompt).hexdigest(),
            "e1e77094c1b47ff3e113f602274ac42e23299597434ca0e6917d1a0e283a6a6a",
        )
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "bf7a50cde8e1864a4fd33532d23429d393c14624e42250da5236f18c0476b964",
        )
        self.assertFalse(any(name[772:]))
        self.assertEqual(self.build.runtime_used_size, 2166)
        self.assertEqual(self.build.runtime_capacity, 2756)
        self.assertEqual(
            dict(self.runtime.choice_cells),
            {"talk_choice_yes": 3, "talk_choice_no": 2},
        )

    def test_choice_rows_and_reserved_gaps_are_explicit(self) -> None:
        arena = self.patches["bitmap_data_arena"].replacement
        yes_row = map_2d.CHOICE_YES_ROW - map_2d.BITMAP_ARENA
        no_row = map_2d.CHOICE_NO_ROW - map_2d.BITMAP_ARENA
        self.assertEqual(
            arena[yes_row : yes_row + 8], bytes.fromhex("0000000100028000")
        )
        self.assertEqual(arena[no_row : no_row + 6], bytes.fromhex("000000018000"))
        self.assertFalse(
            any(arena[no_row + 6 : map_2d.PROMPT_BITMAP - map_2d.BITMAP_ARENA])
        )
        self.assertFalse(any(arena[-8:]))

    def test_typed_recipe_and_readable_source_inventory_is_exact(self) -> None:
        recipes = self.config.patches[map_2d.TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {
                "assembly": 2,
                "generated": 11,
                "linked_pointer": 2,
                "pointer": 2,
                "instruction": 7,
            },
        )
        self.assertEqual(
            Counter(recipe.group for recipe in recipes),
            {
                "map_2d.runtime": 10,
                "map_2d.prompt": 6,
                "map_2d.labels": 6,
                "map_2d.layout": 2,
            },
        )
        self.assertEqual(
            {
                path.relative_to(map_2d.ASSEMBLY_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "map_2d_ui/name_compositor.s",
                "map_2d_ui/prompt_wrapper.s",
            },
        )
        document = json.loads(map_2d.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(document["version"], 2)
        self.assertNotIn(
            '"replacement"', map_2d.CONFIG_PATH.read_text(encoding="utf-8")
        )

    def test_shared_player_name_pointers_are_the_only_dynamic_sources(self) -> None:
        self.assertEqual(
            struct.unpack(">I", self.patches["city_name_pointer"].replacement)[0],
            PLAYER_NAME_FIELD_BY_KEY["city"].runtime_address,
        )
        self.assertEqual(
            struct.unpack(">I", self.patches["ward_name_pointer"].replacement)[0],
            PLAYER_NAME_FIELD_BY_KEY["ward"].runtime_address,
        )
        self.assertEqual(
            struct.unpack(">I", self.patches["name_copy_pointer"].replacement)[0],
            map_2d.NAME_RUNTIME,
        )

    def test_text_and_build_provenance_is_complete(self) -> None:
        self.assertEqual(set(self.build.asset_files), set(map_2d.ASSET_FILES))
        self.assertEqual(
            set(self.build.runtime_input_files), set(map_2d.RUNTIME_INPUT_FILES)
        )
        self.assertEqual(
            dict(self.build.source_inputs),
            {f"game:{map_2d.TARGET}": hashlib.sha256(self.stock).hexdigest()},
        )
        owners = map_2d._binding_inventory()
        self.assertEqual(sum(len(owner) for owner in owners), 14)
        self.assertEqual(
            set().union(*(set(owner) for owner in owners)),
            {
                row["id"]
                for row in json.loads(
                    map_2d.MAP_CORPUS_PATH.read_text(encoding="utf-8")
                )
            },
        )

    def test_binding_assets_cannot_escape_manifest_provenance(self) -> None:
        original = map_2d.load_binding

        def redirect_asset(path: Path, **kwargs: object):
            binding = original(path, **kwargs)
            if path == map_2d.MAP_BINDING_PATH:
                return replace(binding, asset=PurePosixPath("ui/options.json"))
            return binding

        with patch.object(
            map_2d, "load_binding", side_effect=redirect_asset
        ), self.assertRaisesRegex(ValueError, "selects ui/options.json"):
            map_2d._binding_inventory()

    def test_default_text_widths_match_the_renderer_contract(self) -> None:
        expected = {
            "rinkai_park_row": 60,
            "mount_kasagi_row": 55,
            "yarai_ward_row": 59,
            "chuo_ward_row": 55,
            "hibarigaoka_row": 62,
        }
        for name, physical_id in map_2d.FIXED_RECORDS:
            with self.subTest(label=name):
                codes = map_2d._encode(self.terms[physical_id], self.metrics, name)
                self.assertEqual(map_2d._measure(codes, self.metrics), expected[name])
        for key, width in (
            ("talk_prompt", 171),
            ("talk_choice_yes", 20),
            ("talk_choice_no", 13),
        ):
            with self.subTest(label=key):
                value = self.terms[map_2d.MESSAGE_RECORDS[key]]
                codes = map_2d._encode(value, self.metrics, key)
                self.assertEqual(map_2d._measure(codes, self.metrics), width)

    def test_three_glyph_no_uses_the_reserved_third_cell(self) -> None:
        terms = dict(self.terms)
        terms[map_2d.MESSAGE_RECORDS["talk_choice_no"]] = "........."
        codes = map_2d._encode(".........", self.metrics, "test")
        self.assertEqual(len(codes), 3)
        self.assertGreater(map_2d._measure(codes, self.metrics), 32)
        with patch.object(map_2d, "_bound_terms", return_value=terms):
            runtime = map_2d._build_runtime(self.config)
        arena = runtime.generated["bitmap_data_arena"]
        row = map_2d.CHOICE_NO_ROW - map_2d.BITMAP_ARENA
        self.assertEqual(runtime.choice_cells["talk_choice_no"], 3)
        self.assertEqual(arena[row : row + 8], bytes.fromhex("0000000100028000"))
        self.assertEqual(
            runtime.generated["talk_choice_no_row"],
            self.patches["talk_choice_no_row"].expected,
        )
        self.assertEqual(runtime.used_size, self.build.runtime_used_size + 34)

    def test_world_city_literal_suffix_uses_the_authored_overview_row(self) -> None:
        templates = dict(self.templates)
        templates["world_city_label"] = "{city} M"
        with patch.object(map_2d, "_map_templates", return_value=templates):
            runtime = map_2d._build_runtime(self.config)
        codes = map_2d._encode(" M", self.metrics, "test suffix")
        self.assertEqual(
            runtime.generated["overview_suffix_row"],
            struct.pack(">5H", *codes, 0x8000, 0, 0),
        )
        self.assertNotEqual(
            runtime.generated["overview_suffix_row"],
            self.runtime.generated["overview_suffix_row"],
        )

    def test_unsupported_template_edits_fail_instead_of_being_ignored(self) -> None:
        edits = {
            "city_label": "{city} City",
            "world_ward_label": "Ward {ward}",
            "area_label": "{city}{area}",
            "world_city_label": "Map {city}",
        }
        for key, value in edits.items():
            templates = dict(self.templates)
            templates[key] = value
            with (
                self.subTest(template=key),
                patch.object(map_2d, "_map_templates", return_value=templates),
                self.assertRaisesRegex(ValueError, "MAP2D"),
            ):
                map_2d._build_runtime(self.config)

        templates = dict(self.templates)
        templates["world_city_label"] = "{city}Map"
        with (
            patch.object(map_2d, "_map_templates", return_value=templates),
            self.assertRaisesRegex(ValueError, "two-glyph/32px"),
        ):
            map_2d._build_runtime(self.config)

    def test_visible_width_and_storage_limits_fail_closed(self) -> None:
        too_wide = dict(self.terms)
        too_wide[map_2d.FIXED_RECORDS[0][1]] = "W" * 7
        with (
            patch.object(map_2d, "_bound_terms", return_value=too_wide),
            self.assertRaisesRegex(ValueError, "limit is 64px"),
        ):
            map_2d._build_runtime(self.config)

        prompt = dict(self.terms)
        prompt[map_2d.MESSAGE_RECORDS["talk_prompt"]] = "W" * 23
        with (
            patch.object(map_2d, "_bound_terms", return_value=prompt),
            self.assertRaisesRegex(ValueError, "limit is 224px"),
        ):
            map_2d._build_runtime(self.config)

        choice = dict(self.terms)
        choice[map_2d.MESSAGE_RECORDS["talk_choice_yes"]] = "Wide"
        with (
            patch.object(map_2d, "_bound_terms", return_value=choice),
            self.assertRaisesRegex(ValueError, "three-glyph/48px"),
        ):
            map_2d._build_runtime(self.config)

        profile = dict(self.terms)
        profile[map_2d.PROFILE_RECORDS["default_city"]] = "NineChars"
        with (
            patch.object(map_2d, "_bound_terms", return_value=profile),
            self.assertRaisesRegex(ValueError, "eight-byte player-name"),
        ):
            map_2d._build_runtime(self.config)

    def test_guard_only_stock_records_remain_unchanged(self) -> None:
        for address, size in (
            (0x0603E684, 10),
            (0x0603E6C0, 10),
            (0x0603E6D4, 10),
            (0x0603E6DE, 8),
            (0x0603ADBC, 4),
            (map_2d.FONT16_POINTER, 4),
        ):
            offset = address - map_2d.LOAD_ADDRESS
            with self.subTest(address=f"{address:#x}"):
                self.assertEqual(
                    self.build.data[offset : offset + size],
                    self.stock[offset : offset + size],
                )

    def test_runtime_contains_no_player_visible_prose_literals(self) -> None:
        module = Path(map_2d.__file__).read_text(encoding="utf-8")
        assembly = "\n".join(
            path.read_text(encoding="utf-8") for path in self.build.assembly_files
        )
        for literal in (
            "Rinkai Park",
            "Mt. Kasagi",
            "Yarai Ward",
            "Chuo Ward",
            "Hibarigaoka",
            "Someone is here",
        ):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, module)
                self.assertNotIn(literal, assembly)
        self.assertNotIn(".ascii", assembly)
        self.assertNotIn(".string", assembly)

    def test_nonstock_target_input_fails_closed(self) -> None:
        tampered = bytearray(self.stock)
        patch_site = self.patches["area_city_draw"]
        tampered[patch_site.address - map_2d.LOAD_ADDRESS] ^= 0xFF
        with patch.object(
            map_2d, "_stock_source", return_value=bytes(tampered)
        ), self.assertRaisesRegex(ValueError, "configured stock target"):
            map_2d.build_map_2d_ui()


if __name__ == "__main__":
    unittest.main()
