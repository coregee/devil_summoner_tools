from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.core.patch_recipes import (  # noqa: E402
    ASSEMBLY_ROOT,
    resolve_recipe_expected,
)
from engine.shared.status_layout import (  # noqa: E402
    compile_status_templates,
    load_font16_metrics,
    load_stock_latin_codes,
)
from engine.surfaces.level_up_ui import (  # noqa: E402
    ASSET_FILES,
    BATTLE_UI_BUILD_PATH,
    CONFIG_PATH,
    FONT16_METRICS_PATH,
    FONT8_METRICS_PATH,
    LOAD_ADDRESS,
    MAGNAME_PATH,
    PLAYER_NAME,
    RUNTIME_CAPACITY,
    RUNTIME_CAVE,
    RUNTIME_INPUT_FILES,
    TARGET,
    _ability_names,
    _bind_patches,
    _build_components,
    _configuration,
    _fallback_assembly,
    _fixed_data,
    _level_up_terms,
    _manifest,
    _physical_records,
    _runtime_payload,
    _source_assets,
    _validate_ability_names,
    _validate_generated_magname,
    build_level_up_ui,
)
from text.util.assets import load_asset, load_bound_translations  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


EXPECTED_HASH = "466c552e95bb5c7bd808f550e8f0832077715f20fd5427dedf412793fe5d1ed1"
EXPECTED_RUNTIME_HASH = "58ae006984ff1e6cdacb7845fb3881bdb0d2b71726def22dafb20df17863ed2a"
EXPECTED_LAYOUT_HASHES = {
    "parameter_nodes": "a5b629f03d28c1cf718a71baf594c7f43e13d47041f9bfac2cc1032dfb924c01",
    "parameter_rows": "9415f594b8e07a86b13078c8892bd6bb1a6d1911161baa5a0f2a17c55c267603",
    "generic_attack_label": "bbe62789dde710c108832796fca70cf61da2ccabe5b5d34cf7df57133b4abc01",
    "generic_accuracy_label": "5867ed69657fc35465eeea9f8250200d9bc68a45b8be2fc6eaaf38c91aa24bd1",
}
EXPECTED_ASSEMBLY = {
    "level_up_ui/font16_vwf.s",
    "level_up_ui/learned_dispatcher.s",
    "level_up_ui/learned_prepare.s",
    "level_up_ui/max_level_next.s",
    "level_up_ui/name_drawer.s",
    "level_up_ui/no_magic_points.s",
}


def _status_values() -> dict[str, str]:
    status = load_asset("ui/status.json")
    names = {
        "level",
        "experience",
        "next_experience",
        "summon_cost",
        "auto_setting",
        "control",
        "personality_type",
        "loyalty",
        "party_alignment",
        "hit_points",
        "magic_points",
    }
    return {
        name: status.field(f"{name}.text").resolve()[1]
        for name in names
    }


class LevelUpUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base, cls.stock_font16 = _source_assets()
        cls.config = _configuration()
        cls.result = build_level_up_ui(cls.base)
        cls.patches = {patch.name: patch for patch in cls.result.patches}
        cls.physical = _physical_records()
        cls.terms = _level_up_terms(cls.physical)
        cls.abilities = _ability_names(cls.physical)
        cls.packed_magname = MAGNAME_PATH.read_bytes()
        cls.generated, cls.runtime, _terms = _build_components(
            cls.config,
            cls.base,
            cls.stock_font16,
            cls.packed_magname,
        )

    def test_complete_mature_level_up_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.result.data), 235_304)
        self.assertEqual(hashlib.sha256(self.result.data).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.result.patches), 21)
        self.assertEqual(
            Counter(patch.group for patch in self.result.patches),
            {
                "level_up_runtime": 6,
                "level_up_fixed_text": 11,
                "level_up_layout": 4,
            },
        )

    def test_runtime_owns_the_exact_cave_and_preserves_its_final_byte(self) -> None:
        runtime = self.patches["level_up_runtime"]
        self.assertEqual(runtime.address, RUNTIME_CAVE)
        self.assertEqual(len(runtime.expected), RUNTIME_CAPACITY)
        self.assertEqual(set(runtime.expected), {0})
        self.assertEqual(self.result.runtime_used_size, 1279)
        self.assertEqual(self.runtime.used_size, 1279)
        self.assertEqual(
            hashlib.sha256(runtime.replacement[:1279]).hexdigest(),
            EXPECTED_RUNTIME_HASH,
        )
        self.assertEqual(runtime.replacement[-1], 0)
        self.assertEqual(
            self.runtime.links,
            {
                "name_drawer": 0x060220C0,
                "learned_drawer": 0x060223B8,
                "learned_prepare": 0x060224D2,
            },
        )

    def test_recipes_keep_code_readable_and_data_generated(self) -> None:
        recipes = self.config.patches[TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {"assembly": 3, "linked_pointer": 3, "generated": 15},
        )
        sources = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        self.assertEqual(sources, EXPECTED_ASSEMBLY)
        self.assertEqual(
            {
                source.relative_to(ASSEMBLY_ROOT).as_posix()
                for source in self.result.assembly_files
            },
            EXPECTED_ASSEMBLY,
        )
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))

    def test_every_guard_resolves_against_the_untouched_stock_base(self) -> None:
        for recipe in self.config.patches[TARGET]:
            with self.subTest(recipe=recipe.name):
                expected = resolve_recipe_expected(recipe, self.base, LOAD_ADDRESS)
                self.assertEqual(len(expected), len(self.patches[recipe.name].replacement))

        guarded = next(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.expected_sha256 is not None
        )
        damaged = bytearray(self.base)
        damaged[guarded.address - LOAD_ADDRESS] ^= 1
        with self.assertRaisesRegex(ValueError, "expected SHA-256"):
            resolve_recipe_expected(guarded, bytes(damaged), LOAD_ADDRESS)

    def test_layout_bitmaps_have_exact_mature_parity(self) -> None:
        for name, expected in EXPECTED_LAYOUT_HASHES.items():
            with self.subTest(name=name):
                replacement = self.patches[name].replacement
                self.assertEqual(hashlib.sha256(replacement).hexdigest(), expected)

    def test_fixed_fields_propagate_and_confirm_no_is_centered(self) -> None:
        current = _fixed_data(self.terms)
        self.assertEqual(current["confirm_no"], b" NO\0")

        one = _fixed_data(replace(self.terms, confirm_no="X"))
        three = _fixed_data(replace(self.terms, confirm_no="XYZ"))
        title = _fixed_data(replace(self.terms, title="NEW NAME"))
        self.assertEqual(one["confirm_no"], b" X \0")
        self.assertEqual(three["confirm_no"], b"XYZ\0")
        self.assertEqual(title["title"], b"NEW NAME\0\0\0\0")

    def test_complete_status_templates_are_compiled_not_prefix_sliced(self) -> None:
        values = _status_values()
        templates = compile_status_templates(values)
        self.assertEqual(templates.prefixes["hit_points"], "HP")
        self.assertEqual(templates.hp_mp_separator, "/")

        reordered = dict(
            values,
            hit_points="HP {maximum_hp}/{current_hp}",
        )
        with self.assertRaisesRegex(ValueError, "must use"):
            compile_status_templates(reordered)
        suffixed = dict(values, level="LV {level}!")
        with self.assertRaisesRegex(ValueError, "PREFIX"):
            compile_status_templates(suffixed)
        split = dict(values, magic_points="MP {current_mp}.{maximum_mp}")
        with self.assertRaisesRegex(ValueError, "share one separator"):
            compile_status_templates(split)

    def test_both_runtime_fallbacks_are_fully_editable(self) -> None:
        recipes = {recipe.name: recipe for recipe in self.config.patches[TARGET]}
        no_mp_recipe = recipes["no_magic_points_runtime"]
        max_recipe = recipes["max_level_next_runtime"]
        no_mp_expected = resolve_recipe_expected(no_mp_recipe, self.base, LOAD_ADDRESS)
        max_expected = resolve_recipe_expected(max_recipe, self.base, LOAD_ADDRESS)

        self.assertEqual(
            _fallback_assembly(no_mp_recipe, no_mp_expected, self.terms),
            no_mp_expected,
        )
        self.assertEqual(
            _fallback_assembly(max_recipe, max_expected, self.terms),
            max_expected,
        )

        stock = load_stock_latin_codes(FONT8_METRICS_PATH)
        edited_max = replace(self.terms, max_level_next="ABC")
        max_replacement = _fallback_assembly(
            max_recipe, max_expected, edited_max
        )
        max_cells = bytes((stock["A"], stock["B"], stock["C"], 0, 0, 0, 0))
        self.assertNotEqual(max_replacement, max_expected)
        self.assertIn(max_cells, max_replacement)

        edited_no_mp = replace(self.terms, no_magic_points="ABC.XYZ")
        no_mp_replacement = _fallback_assembly(
            no_mp_recipe, no_mp_expected, edited_no_mp
        )
        no_mp_cells = bytes(
            (
                stock["A"],
                stock["B"],
                stock["C"],
                stock["."],
                stock[" "],
                stock["X"],
                stock["Y"],
                stock["Z"],
            )
        )
        self.assertNotEqual(no_mp_replacement, no_mp_expected)
        self.assertIn(no_mp_cells, no_mp_replacement)

        # The stock routine shares the normal HP/MP separator. If that field is
        # edited while the no-MP asset stays '/', install the alternate routine
        # so the two authored fields remain independent.
        dotted_templates = replace(self.terms.templates, hp_mp_separator=".")
        independent = replace(self.terms, templates=dotted_templates)
        replacement = _fallback_assembly(
            no_mp_recipe, no_mp_expected, independent
        )
        self.assertNotEqual(replacement, no_mp_expected)
        self.assertIn(
            bytes((stock["-"], stock["-"], stock["-"], stock["/"], 0)),
            replacement,
        )

    def test_magname_is_bound_by_physical_row_and_manifest_validated(self) -> None:
        self.assertEqual(len(self.abilities), 255)
        manifest = _manifest()
        self.assertEqual(_validate_generated_magname(manifest), self.packed_magname)
        self.assertEqual(
            manifest["font8_metrics_sha256"],
            hashlib.sha256(FONT8_METRICS_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            manifest["font16_metrics_sha256"],
            hashlib.sha256(FONT16_METRICS_PATH.read_bytes()).hexdigest(),
        )
        self.assertNotIn("magname_sha256", self.config.inputs)

        metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
        metrics16 = FontMetrics.load(FONT16_METRICS_PATH)
        _validate_ability_names(
            self.packed_magname, self.abilities, metrics8, metrics16
        )
        stale = bytearray(self.packed_magname)
        pointer = struct.unpack_from(">H", stale, 45 * 0x60 + 0x5E)[0]
        stale[pointer] ^= 1
        with self.assertRaisesRegex(ValueError, "row 45 .* is stale"):
            _validate_ability_names(bytes(stale), self.abilities, metrics8, metrics16)

    def test_character_table_has_five_fixed_rows_and_a_live_codename_fallback(self) -> None:
        ids = {
            f"game.charname.o{index * 8:06x}.text" for index in range(1, 6)
        }
        fixed = load_bound_translations(
            ("game.charname.",),
            required_ids=ids,
            binding_paths=(SATURN_ROOT / "text" / "bindings" / "characters.json",),
            physical_records=self.physical,
        )
        self.assertEqual(len(fixed), 5)
        runtime = self.patches["level_up_runtime"].replacement
        self.assertIn(struct.pack(">I", PLAYER_NAME), runtime)

        widths, codes = load_font16_metrics(FONT16_METRICS_PATH)
        hajime = load_bound_translations(
            ("game.charname.",),
            required_ids={"game.charname.o000000.text"},
            binding_paths=(SATURN_ROOT / "text" / "bindings" / "characters.json",),
            physical_records=self.physical,
        )["game.charname.o000000.text"]
        encoded_hajime = struct.pack(
            f">{len(hajime) + 1}H",
            *(codes[character] for character in hajime),
            0x8000,
        )
        self.assertNotIn(encoded_hajime, runtime)
        self.assertEqual(len(widths), 268)

    def test_runtime_overflow_fails_at_the_exact_cave_boundary(self) -> None:
        runtime_recipe = next(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name == "level_up_runtime"
        )
        with self.assertRaisesRegex(ValueError, "exact 0x500 cave"):
            _runtime_payload(
                runtime_recipe,
                self.terms,
                ("iiiiiiiiiiiiiiii",) * 5,
                self.abilities,
                self.packed_magname,
            )

    def test_asset_and_runtime_input_inventories_are_explicit(self) -> None:
        self.assertEqual(self.result.asset_files, ASSET_FILES)
        self.assertEqual(self.result.runtime_input_files, RUNTIME_INPUT_FILES)
        self.assertIn(MAGNAME_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(BATTLE_UI_BUILD_PATH, RUNTIME_INPUT_FILES)
        self.assertEqual(
            {path.relative_to(SATURN_ROOT.parent).as_posix() for path in ASSET_FILES},
            {
                "assets/text/characters.json",
                "assets/text/magic.json",
                "assets/text/skills.json",
                "assets/text/ui/level_up.json",
                "assets/text/ui/status.json",
            },
        )
        self.assertEqual(
            set(self.result.source_inputs),
            {"game:LEVEL_UP.BIN", "game:FONT16.FON"},
        )

    def test_generated_inventory_rejects_an_unowned_payload(self) -> None:
        recipes = tuple(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name != "accept"
        )
        incomplete = replace(self.config, patches={TARGET: recipes})
        with self.assertRaisesRegex(ValueError, "no configured owner: accept"):
            _bind_patches(
                incomplete,
                self.base,
                self.stock_font16,
                self.packed_magname,
            )


if __name__ == "__main__":
    unittest.main()
