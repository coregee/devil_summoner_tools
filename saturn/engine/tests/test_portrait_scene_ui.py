from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.portrait_scene_ui as portrait  # noqa: E402
from engine.core.patch_recipes import ASSEMBLY_ROOT  # noqa: E402
from engine.shared.event_window import font16_layout  # noqa: E402
from engine.shared.player_name_adapters import pointer_contract  # noqa: E402
from text.util.event_codec import load_event_dictionary  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


MATURE_HASH = "3cbbf6ec70887cdb49a46c006767550438da684a30b5a754d6ce7c811d337814"
EXPECTED_ASSEMBLY = {
    "font16_subpixel_blitter.s",
    "shared/event_window/absolute_jump.s",
    "shared/event_window/advance.s",
    "shared/event_window/character_term_insert.s",
    "shared/event_window/full_term_inserts.s",
    "shared/event_window/menu_glyph.s",
    "shared/event_window/packed_fetch.s",
    "shared/event_window/two_glyph_pacing.s",
    "shared/player_name_inserts/codename_skip.s",
    "shared/player_name_inserts/raw_menu_inserts.s",
    "shared/player_name_inserts/raw_menu_result.s",
}


class PortraitSceneUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = portrait._stock_source()
        cls.config = portrait._configuration()
        cls.dictionary = load_event_dictionary(portrait.CODEC_PATH).runtime_table()
        cls.build = portrait.build_portrait_scene_ui()
        cls.runtime = portrait._build_runtime(cls.config, cls.dictionary)
        cls.patches = {row.name: row for row in cls.build.patches}
        cls.demons, cls.characters, cls.races, cls.debug = portrait._bound_terms()
        cls.metrics16 = FontMetrics.load(portrait.FONT16_METRICS_PATH)

    def test_complete_mature_portrait_scene_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.build.data), 103_792)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), MATURE_HASH)
        self.assertEqual(len(self.build.patches), 37)
        self.assertEqual(
            tuple(dict.fromkeys(row.group for row in self.build.patches)),
            (
                "msgr.dialogue_vwf",
                "msgr.term_inserts",
                "msgr.player_name_adapters",
                "msgr.fixed_text_compatibility",
                "msgr.debug_messages",
            ),
        )

    def test_three_runtime_arenas_have_exact_geometry_and_padding(self) -> None:
        self.assertEqual(self.build.runtime_used_size, 6_679)
        self.assertEqual(self.build.runtime_capacity, 24_928)
        self.assertEqual(
            self.build.runtime_arenas,
            (
                portrait.RuntimeArena("dialogue_window", 0x06060400, 2_113, 19_456),
                portrait.RuntimeArena("full_term_inserts", 0x06065000, 4_480, 5_376),
                portrait.RuntimeArena("player_name_raw_menu", 0x0606C63C, 86, 96),
            ),
        )
        dialogue_names = (
            "dialogue_two_glyph_pacing_cave",
            "advance_cave",
            "packed_fetch_cave",
            "subpixel_blitter_cave",
            "menu_glyph_cave",
        )
        self.assertEqual(
            sum(len(self.patches[name].replacement) for name in dialogue_names),
            2_113,
        )
        term = self.patches["dialogue_full_term_runtime"].replacement
        raw_menu = self.patches["raw_menu_name_renderer"].replacement
        self.assertFalse(any(term[4_480:]))
        self.assertFalse(any(raw_menu[86:]))

    def test_typed_recipe_and_readable_source_inventory_is_exact(self) -> None:
        recipes = self.config.patches[portrait.TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {
                "assembly": 13,
                "pointer": 9,
                "linked_pointer": 6,
                "instruction": 5,
                "generated": 4,
            },
        )
        self.assertEqual(
            Counter(recipe.group for recipe in recipes),
            {
                "msgr.dialogue_vwf": 14,
                "msgr.term_inserts": 4,
                "msgr.player_name_adapters": 15,
                "msgr.fixed_text_compatibility": 1,
                "msgr.debug_messages": 3,
            },
        )
        sources = {
            path.relative_to(ASSEMBLY_ROOT).as_posix()
            for path in self.build.assembly_files
        }
        self.assertEqual(sources, EXPECTED_ASSEMBLY)
        document = portrait.CONFIG_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"replacement"', document)
        self.assertNotIn('"replacement_zero_bytes"', document)

    def test_generated_fields_come_from_bound_terms(self) -> None:
        generated = self.runtime.generated
        self.assertEqual(
            generated["race_uma_mirror"], bytes.fromhex("001f0017000b8000")
        )
        self.assertEqual(
            generated["debug_name_id_error"], b"NAME TO ID ERR\0\0"
        )
        self.assertEqual(generated["debug_load_error"], b"LOAD ERR\0\0")
        self.assertEqual(
            generated["debug_menu_count_over"], b"ERROR: MENU COUNT OVER\0\0"
        )

        changed = dict(self.debug)
        changed["game.msgr_debug_ascii.o00ae14"] = "IO ERR"
        rebuilt = portrait._generated_data(
            self.races,
            changed,
            self.metrics16,
            self.patches["race_uma_mirror"].expected,
        )
        self.assertEqual(rebuilt["debug_load_error"], b"IO ERR\0\0\0\0")

    def test_uma_mirror_encodes_one_to_four_glyph_rows(self) -> None:
        fallback = self.patches["race_uma_mirror"].expected
        codes = portrait._font_codes(self.metrics16)
        for value in ("U", "Um", "Uma", "Uma!"):
            races = (*self.races[:22], value, *self.races[23:])
            generated = portrait._generated_data(
                races, self.debug, self.metrics16, fallback
            )
            glyphs = tuple(codes[character] for character in value)
            if len(glyphs) == 4:
                expected = struct.pack(">4H", *glyphs)
            else:
                expected = struct.pack(f">{len(glyphs) + 1}H", *glyphs, 0x8000)
                expected = expected.ljust(8, b"\0")
            with self.subTest(value=value):
                self.assertEqual(generated["race_uma_mirror"], expected)
        self.assertEqual(expected, bytes.fromhex("001f0031002500b3"))

    def test_long_uma_uses_live_table_and_leaves_compatibility_row_stock(self) -> None:
        races = (*self.races[:22], "Unicorn", *self.races[23:])
        with patch.object(
            portrait,
            "_bound_terms",
            return_value=(self.demons, self.characters, races, self.debug),
        ):
            build = portrait.build_portrait_scene_ui()
        patches = {row.name: row for row in build.patches}
        mirror = patches["race_uma_mirror"]
        self.assertEqual(mirror.replacement, mirror.expected)
        self.assertGreater(
            build.runtime_arenas[1].used_size,
            self.build.runtime_arenas[1].used_size,
        )
        self.assertNotEqual(
            patches["dialogue_full_term_runtime"].replacement,
            self.patches["dialogue_full_term_runtime"].replacement,
        )
        self.assertNotEqual(
            patches["dialogue_race_insert"].replacement,
            self.patches["dialogue_race_insert"].replacement,
        )
        self.assertNotEqual(build.data, self.build.data)

    def test_debug_fields_reject_every_nonprintable_ascii_form(self) -> None:
        self.assertEqual(portrait._ascii_field("OK", 4, "test"), b"OK\0\0")
        invalid = (
            "",
            "line\nfeed",
            "tab\tstop",
            "\x1f",
            "\x7f",
            "caf\N{LATIN SMALL LETTER E WITH ACUTE}",
        )
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaisesRegex(
                ValueError, "printable ASCII"
            ):
                portrait._ascii_field(value, 16, "test")

    def test_font16_layout_rejects_a_different_font_identity(self) -> None:
        document = json.loads(
            portrait.FONT16_METRICS_PATH.read_text(encoding="utf-8")
        )
        document["font"] = "FONT12.FON"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid runtime width layout"):
                font16_layout(path)

    def test_player_name_pointers_use_the_shared_runtime_contract(self) -> None:
        for name, address in pointer_contract().items():
            with self.subTest(name=name):
                self.assertEqual(
                    struct.unpack(">I", self.patches[name].replacement)[0], address
                )
        for name, address in portrait.FIXED_POINTER_CONTRACT.items():
            with self.subTest(name=name):
                self.assertEqual(
                    struct.unpack(">I", self.patches[name].replacement)[0], address
                )

    def test_full_recipe_semantics_reject_config_drift(self) -> None:
        recipes = list(self.config.patches[portrait.TARGET])
        by_name = {recipe.name: index for index, recipe in enumerate(recipes)}
        changes = {
            "address": replace(
                recipes[by_name["menu_advance"]],
                address=recipes[by_name["menu_advance"]].address + 2,
            ),
            "linked_pointer": replace(
                recipes[by_name["dialogue_race_insert"]],
                replacement=replace(
                    recipes[by_name["dialogue_race_insert"]].replacement,
                    link="dialogue_demon_name_insert",
                ),
            ),
            "instruction": replace(
                recipes[by_name["menu_advance"]],
                replacement=replace(
                    recipes[by_name["menu_advance"]].replacement,
                    instruction="nop",
                ),
            ),
            "assembly_source": replace(
                recipes[by_name["fetch_site_1"]],
                replacement=replace(
                    recipes[by_name["fetch_site_1"]].replacement,
                    sources=recipes[
                        by_name["codename_skip_copy"]
                    ].replacement.sources,
                ),
            ),
            "pointer": replace(
                recipes[by_name["advance_pointer"]],
                replacement=replace(
                    recipes[by_name["advance_pointer"]].replacement,
                    pointer=portrait.DIALOGUE_ARENA + 4,
                ),
            ),
        }
        for name, changed_recipe in changes.items():
            changed = list(recipes)
            changed[by_name[changed_recipe.name]] = changed_recipe
            config = replace(
                self.config,
                patches={portrait.TARGET: tuple(changed)},
            )
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "patch inventory|replacement contract"
            ):
                portrait._recipe_map(config)

        changed = list(recipes)
        changed[by_name["advance_pointer"]] = changes["pointer"]
        pointer_config = replace(
            self.config,
            patches={portrait.TARGET: tuple(changed)},
        )
        with self.assertRaisesRegex(ValueError, "pointer contract"):
            portrait._bind_patches(pointer_config, self.stock, self.runtime)

    def test_asset_text_and_source_provenance_is_complete(self) -> None:
        self.assertEqual(set(self.build.asset_files), set(portrait.ASSET_FILES))
        self.assertEqual(
            set(self.build.runtime_input_files), set(portrait.RUNTIME_INPUT_FILES)
        )
        runtime_inputs = set(self.build.runtime_input_files)
        self.assertTrue(set(portrait.BINDING_FILES) <= runtime_inputs)
        self.assertTrue(set(portrait.CORPUS_FILES) <= runtime_inputs)
        self.assertTrue(set(portrait.EVENT_BANK_PATHS) <= runtime_inputs)
        self.assertEqual(
            dict(self.build.source_inputs),
            {
                f"game:{portrait.TARGET}": hashlib.sha256(self.stock).hexdigest()
            },
        )

    def test_term_storage_limit_fails_closed(self) -> None:
        demons = ("W" * 21, *self.demons[1:])
        with patch.object(
            portrait,
            "_bound_terms",
            return_value=(demons, self.characters, self.races, self.debug),
        ), self.assertRaisesRegex(ValueError, "exceeds 20 glyphs"):
            portrait._build_runtime(self.config, self.dictionary)

    def test_in_capacity_term_edits_relocate_and_account_dynamically(self) -> None:
        variants = {
            "shorter": ("Vi", *self.demons[1:]),
            "longer": ("Vishnu Vishnu", *self.demons[1:]),
        }
        builds = {}
        for name, demons in variants.items():
            with self.subTest(name=name), patch.object(
                portrait,
                "_bound_terms",
                return_value=(demons, self.characters, self.races, self.debug),
            ):
                builds[name] = portrait.build_portrait_scene_ui()

        default_term_used = self.build.runtime_arenas[1].used_size
        short_term_used = builds["shorter"].runtime_arenas[1].used_size
        long_term_used = builds["longer"].runtime_arenas[1].used_size
        self.assertLess(short_term_used, default_term_used)
        self.assertGreater(long_term_used, default_term_used)
        self.assertLessEqual(long_term_used, portrait.TERM_CAPACITY)

        link_names = (
            "dialogue_demon_name_insert",
            "dialogue_race_insert",
            "dialogue_character_name_insert",
        )
        default_patches = self.patches
        for name, build in builds.items():
            with self.subTest(output=name):
                patches = {row.name: row for row in build.patches}
                self.assertEqual(len(build.data), len(self.build.data))
                self.assertNotEqual(build.data, self.build.data)
                self.assertEqual(
                    build.runtime_used_size,
                    2_113 + build.runtime_arenas[1].used_size + 86,
                )
                self.assertTrue(
                    all(
                        patches[link].replacement
                        != default_patches[link].replacement
                        for link in link_names
                    )
                )

    def test_runtime_ownership_rejects_unconfigured_payloads(self) -> None:
        changed = portrait.RuntimeBuild(
            {**self.runtime.assembly, "unowned_runtime": b""},
            self.runtime.generated,
            self.runtime.links,
            self.runtime.arenas,
        )
        with self.assertRaisesRegex(ValueError, "assembly ownership"):
            portrait._bind_patches(self.config, self.stock, changed)

    def test_default_debug_recipes_are_byte_neutral(self) -> None:
        for name in (
            "debug_name_id_error",
            "debug_load_error",
            "debug_menu_count_over",
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    self.patches[name].replacement, self.patches[name].expected
                )
        self.assertNotEqual(
            self.patches["race_uma_mirror"].replacement,
            self.patches["race_uma_mirror"].expected,
        )

    def test_runtime_contains_no_player_visible_prose_literals(self) -> None:
        module = Path(portrait.__file__).read_text(encoding="utf-8")
        assembly = "\n".join(
            path.read_text(encoding="utf-8") for path in self.build.assembly_files
        )
        for literal in ("NAME TO ID ERR", "LOAD ERR", "ERROR: MENU COUNT OVER"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, module)
                self.assertNotIn(literal, assembly)
        self.assertNotIn(".ascii", assembly)
        self.assertNotIn(".string", assembly)

    def test_nonstock_target_input_fails_closed(self) -> None:
        damaged = bytearray(self.stock)
        damaged[0xAE04] ^= 1
        with patch.object(
            portrait, "_stock_source", return_value=bytes(damaged)
        ), self.assertRaisesRegex(ValueError, "does not match the patch target"):
            portrait.build_portrait_scene_ui()


if __name__ == "__main__":
    unittest.main()
