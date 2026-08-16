from __future__ import annotations

import hashlib
import sys
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.core.patch_recipes import (  # noqa: E402
    ASSEMBLY_ROOT,
    resolve_recipe_expected,
)
from engine.shared.demon_sort import dense_rank_table  # noqa: E402
from engine.shared.font8 import font8_tables  # noqa: E402
from engine.shared.status_layout import (  # noqa: E402
    load_font16_metrics,
    load_stock_latin_codes,
)
from engine.surfaces.analyze_ui import (  # noqa: E402
    ASSET_FILES,
    BATTLE_UI_BUILD_PATH,
    COMP_MENU_BUILD_PATH,
    CONFIG_PATH,
    DVLNAME_PATH,
    FONT8_METRICS_PATH,
    LOAD_ADDRESS,
    MAGNAME_PATH,
    RUNTIME_CAPACITY,
    RUNTIME_INPUT_FILES,
    TABLE_CAPACITY,
    TARGET,
    _ability_names,
    _analyze_terms,
    _bind_patches,
    _build_components,
    _compact_data,
    _configuration,
    _direct_data,
    _physical_records,
    _runtime_payload,
    _runtime_terms,
    _small_assembly,
    _source_assets,
    _validate_inputs,
    _validate_magname,
    build_analyze_ui,
)
from text.util.event_repack import FontMetrics  # noqa: E402


EXPECTED_HASH = "3d84b647018108d6a2f1f74a068336d6166766b1a3d25d826f7eb05c66f2efe7"
EXPECTED_RUNTIME_HASH = "f32d246645d3156f65fc6a2da34b4268f69b613c6c00eb4ee8215dabbdf51ccc"
EXPECTED_TABLE_HASH = "4844e426709dd876e38bd9491b85fa2767c4bebd96d8454e73c50340d7dec246"
EXPECTED_LAYOUT_HASHES = {
    "parameter_nodes": "a5b629f03d28c1cf718a71baf594c7f43e13d47041f9bfac2cc1032dfb924c01",
    "parameter_rows": "9415f594b8e07a86b13078c8892bd6bb1a6d1911161baa5a0f2a17c55c267603",
    "generic_attack_label": "bbe62789dde710c108832796fca70cf61da2ccabe5b5d34cf7df57133b4abc01",
    "generic_accuracy_label": "5867ed69657fc35465eeea9f8250200d9bc68a45b8be2fc6eaaf38c91aa24bd1",
    "loyalty_label": "8c61244312171095b245c9c10eb27a78f2762e3e012a25de6aec92a2e7e3f029",
}
EXPECTED_ASSEMBLY = {
    "analyze_ui/affinity_dispatcher.s",
    "analyze_ui/axis_cell_argument.s",
    "analyze_ui/axis_law_adjust.s",
    "analyze_ui/axis_pointer_load.s",
    "analyze_ui/font16_from_font8.s",
    "analyze_ui/font8_vwf.s",
    "analyze_ui/name_decoder.s",
    "analyze_ui/name_race_dispatcher.s",
    "analyze_ui/name_rank_compare.s",
    "analyze_ui/skill_dispatcher.s",
    "analyze_ui/table_font8_vwf.s",
}


class AnalyzeUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base, cls.stock_font16 = _source_assets()
        cls.config = _configuration()
        cls.dvlname, cls.magname = _validate_inputs(
            cls.config, cls.base, cls.stock_font16
        )
        cls.physical = _physical_records()
        cls.terms = _analyze_terms(cls.physical)
        cls.races, cls.affinities, cls.demons = _runtime_terms(cls.physical)
        cls.abilities = _ability_names(cls.physical)
        cls.result = build_analyze_ui(cls.base)
        cls.patches = {patch.name: patch for patch in cls.result.patches}
        cls.generated, cls.runtime, cls.axes_diverge, cls.compact = _build_components(
            cls.config,
            cls.base,
            cls.stock_font16,
            cls.dvlname,
            cls.magname,
        )
        cls.metrics8 = FontMetrics.load(FONT8_METRICS_PATH)
        cls.widths8, cls.codes8 = font8_tables(cls.metrics8)
        cls.widths16, cls.codes16 = load_font16_metrics(
            SATURN_ROOT / "font" / "generated" / "game" / "FONT16_metrics.json"
        )

    def test_complete_mature_analyze_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.result.data), 283_536)
        self.assertEqual(hashlib.sha256(self.result.data).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.result.patches), 37)
        self.assertEqual(
            Counter(patch.group for patch in self.result.patches),
            {
                "analyze_runtime": 9,
                "analyze_layout": 5,
                "analyze_visible_text": 23,
            },
        )

    def test_runtime_owns_two_separate_exact_caves(self) -> None:
        self.assertEqual(self.runtime.used_size, 3510)
        self.assertEqual(self.runtime.capacity, RUNTIME_CAPACITY)
        self.assertEqual(self.runtime.table_used_size, 256)
        self.assertEqual(self.runtime.table_capacity, TABLE_CAPACITY)
        self.assertEqual(
            hashlib.sha256(self.runtime.data).hexdigest(), EXPECTED_RUNTIME_HASH
        )
        self.assertEqual(
            hashlib.sha256(self.runtime.table_data).hexdigest(), EXPECTED_TABLE_HASH
        )
        self.assertEqual(self.runtime.data[3510:], bytes(12))
        self.assertEqual(self.runtime.table_data[256:], bytes(2))
        self.assertEqual(
            self.runtime.links,
            {
                "detailed_dispatcher": 0x060650C0,
                "skill_dispatcher": 0x060651CC,
                "affinity_dispatcher": 0x06064F78,
                "table_dispatcher": 0x06065094,
            },
        )

    def test_recipes_and_directory_have_exact_readable_assembly_inventory(self) -> None:
        recipes = self.config.patches[TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {"assembly": 8, "linked_pointer": 5, "generated": 24},
        )
        configured = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        on_disk = {
            path.relative_to(ASSEMBLY_ROOT).as_posix()
            for path in (ASSEMBLY_ROOT / "analyze_ui").glob("*.s")
        }
        self.assertEqual(configured, EXPECTED_ASSEMBLY)
        self.assertEqual(on_disk, EXPECTED_ASSEMBLY)
        self.assertEqual(
            {
                path.relative_to(ASSEMBLY_ROOT).as_posix()
                for path in self.result.assembly_files
            },
            EXPECTED_ASSEMBLY,
        )
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))

    def test_every_guard_resolves_against_untouched_stock(self) -> None:
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
                self.assertEqual(
                    hashlib.sha256(self.patches[name].replacement).hexdigest(),
                    expected,
                )

    def test_every_fixed_visible_field_is_generated_from_authored_terms(self) -> None:
        self.assertEqual(self.generated["detail_level_prefix"], b"LV\0\0")
        self.assertEqual(self.generated["magic_cost_suffix"], b"M\0\0\0")
        self.assertEqual(self.generated["race_heading"], b"RACE\0\0\0\0")
        prefixes = dict(self.terms.templates.prefixes)
        prefixes.update(
            level="XL", hit_points="QP", magic_points="RP", summon_cost="SP"
        )
        templates = replace(
            self.terms.templates, prefixes=MappingProxyType(prefixes)
        )
        axes = MappingProxyType(
            {"law": "A", "light": "B", "chaos": "Q", "dark": "R", "neutral": "S"}
        )
        edited = replace(
            self.terms,
            templates=templates,
            race_heading="TYPE",
            name_heading="UNIT",
            attack_heading="POW",
            defense_heading="ARM",
            magic_cost_suffix="X",
            health_cost_suffix="Y",
            axes=axes,
        )
        data, _diverges = _direct_data(
            edited, self.widths8, load_stock_latin_codes(FONT8_METRICS_PATH)
        )
        self.assertEqual(data["detail_level_prefix"], b"XL\0\0")
        self.assertEqual(data["detail_hit_points_prefix"], b"QP\0\0")
        self.assertEqual(data["detail_magic_points_prefix"], b"RP\0\0")
        self.assertEqual(data["detail_summon_cost_prefix"], b"SP\0\0")
        self.assertEqual(data["race_heading"], b"TYPE\0\0\0\0")
        self.assertEqual(data["name_heading"], b"UNIT\0\0\0\0")
        self.assertEqual(data["level_heading"], b"XL\0\0")
        self.assertEqual(data["hit_points_heading"], b"QP\0\0")
        self.assertEqual(data["magic_points_heading"], b"RP\0\0")
        self.assertEqual(data["attack_heading"], b"POW\0")
        self.assertEqual(data["defense_heading"], b"ARM\0")
        self.assertEqual(data["magic_cost_suffix"], b"X\0\0\0")
        self.assertEqual(data["health_cost_suffix"], b"Y\0")
        self.assertEqual(data["axis_law"], b"A\0B\0")
        self.assertEqual(data["axis_chaos"], b"Q\0\0\0")
        self.assertEqual(data["axis_dark"], b"R\0\0\0")
        self.assertEqual(data["axis_neutral"], b"S\0")

    def test_law_and_light_alias_splits_only_when_authored_values_diverge(self) -> None:
        self.assertFalse(self.axes_diverge)
        self.assertEqual(self.generated["axis_law"], b"L\0\0\0")
        self.assertEqual(self.generated["axis_law_light_pointer"], bytes.fromhex("0602d4c8"))
        recipes = {recipe.name: recipe for recipe in self.config.patches[TARGET]}
        for name in (
            "axis_law_first_load",
            "axis_law_adjust",
            "axis_law_cell_argument",
            "axis_light_load",
            "axis_light_cell_argument",
        ):
            expected = resolve_recipe_expected(recipes[name], self.base, LOAD_ADDRESS)
            self.assertEqual(
                _small_assembly(recipes[name], expected, axes_diverge=False), expected
            )

        axes = dict(self.terms.axes)
        axes["light"] = "X"
        edited = replace(self.terms, axes=MappingProxyType(axes))
        data, diverges = _direct_data(
            edited, self.widths8, load_stock_latin_codes(FONT8_METRICS_PATH)
        )
        self.assertTrue(diverges)
        self.assertEqual(data["axis_law"], b"L\0X\0")
        self.assertEqual(data["axis_law_light_pointer"], bytes.fromhex("0602d4ca"))
        expected_opcodes = {
            "axis_law_first_load": "d41c",
            "axis_law_adjust": "74fe",
            "axis_law_cell_argument": "e507",
            "axis_light_load": "d413",
            "axis_light_cell_argument": "e507",
        }
        for name, opcode in expected_opcodes.items():
            recipe = recipes[name]
            expected = resolve_recipe_expected(recipe, self.base, LOAD_ADDRESS)
            self.assertEqual(
                _small_assembly(recipe, expected, axes_diverge=True).hex(), opcode
            )

    def test_affinity_dictionary_is_derived_and_exact_not_literal_owned(self) -> None:
        self.assertEqual(len(self.compact.affinity_phrases), 4)
        source = (
            SATURN_ROOT / "engine" / "surfaces" / "analyze_ui.py"
        ).read_text(encoding="utf-8")
        for phrase in self.compact.affinity_phrases:
            self.assertNotIn(phrase, source)
        self.assertEqual(
            self.compact.addresses,
            {
                "font16_widths": 0x06064386,
                "race_pool": 0x060643D6,
                "race_offsets": 0x060644DE,
                "long_name_bits": 0x06064534,
                "name_pool": 0x0606455C,
                "affinity_word_offsets": 0x060648C0,
                "affinity_word_pool": 0x060648DC,
                "affinity_tokens": 0x06064995,
            },
        )

    def test_demon_name_edits_propagate_to_runtime_and_sort_ranks(self) -> None:
        edited = list(self.demons)
        edited[123] = "Aamata-no-Orochi"
        changed = _compact_data(
            0x06064386,
            (SATURN_ROOT / "font" / "generated" / "game" / "FONT8.FON").read_bytes(),
            self.widths8,
            self.codes8,
            self.widths16,
            self.codes16,
            self.races,
            self.affinities,
            edited,
            self.dvlname,
        )
        self.assertNotEqual(changed.data, self.compact.data)
        self.assertNotEqual(
            dense_rank_table(edited, count=255),
            self.generated["english_name_ranks"],
        )

    def test_race_and_affinity_edits_rebuild_compact_runtime_data(self) -> None:
        races = list(self.races)
        races[0] = races[0][:-1] + ("X" if races[0][-1] != "X" else "Y")
        affinities = list(self.affinities)
        affinities[1] = affinities[1].replace("Fire", "Fyre")
        changed = _compact_data(
            0x06064386,
            (SATURN_ROOT / "font" / "generated" / "game" / "FONT8.FON").read_bytes(),
            self.widths8,
            self.codes8,
            self.widths16,
            self.codes16,
            races,
            affinities,
            self.demons,
            self.dvlname,
        )
        self.assertNotEqual(changed.data, self.compact.data)

    def test_magname_manifest_and_all_255_bound_names_are_validated(self) -> None:
        self.assertEqual(len(self.abilities), 255)
        _validate_magname(
            self.magname, self.abilities, self.widths8, self.codes8
        )
        edited = list(self.abilities)
        edited[0] = "Agu"
        with self.assertRaisesRegex(ValueError, "row 0 .* stale"):
            _validate_magname(self.magname, edited, self.widths8, self.codes8)
        self.assertIn(DVLNAME_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(MAGNAME_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(COMP_MENU_BUILD_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(BATTLE_UI_BUILD_PATH, RUNTIME_INPUT_FILES)
        self.assertNotIn("dvlname_sha256", self.config.inputs)
        self.assertNotIn("magname_sha256", self.config.inputs)

    def test_runtime_overflow_fails_closed_at_exact_main_boundary(self) -> None:
        recipes = {recipe.name: recipe for recipe in self.config.patches[TARGET]}
        oversized = replace(self.compact, data=self.compact.data + bytes(32))
        with self.assertRaisesRegex(ValueError, "exact cave"):
            _runtime_payload(
                recipes["analyze_runtime"],
                recipes["analyze_table_runtime"],
                oversized,
            )

    def test_asset_runtime_and_source_inventories_are_explicit(self) -> None:
        self.assertEqual(self.result.asset_files, ASSET_FILES)
        self.assertEqual(self.result.runtime_input_files, RUNTIME_INPUT_FILES)
        self.assertEqual(
            set(self.result.source_inputs), {"game:DA_3D.BIN", "game:FONT16.FON"}
        )
        self.assertEqual(self.result.runtime_used_size, 3510)
        self.assertEqual(self.result.runtime_capacity, 3522)
        self.assertEqual(self.result.table_runtime_used_size, 256)
        self.assertEqual(self.result.table_runtime_capacity, 258)

    def test_generated_inventory_rejects_an_unowned_field(self) -> None:
        recipes = tuple(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name != "defense_heading"
        )
        incomplete = replace(self.config, patches={TARGET: recipes})
        with self.assertRaisesRegex(ValueError, "no configured owner: defense_heading"):
            _bind_patches(
                incomplete,
                self.base,
                self.stock_font16,
                self.dvlname,
                self.magname,
            )


if __name__ == "__main__":
    unittest.main()
