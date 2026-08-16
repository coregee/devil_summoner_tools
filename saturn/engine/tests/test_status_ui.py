from __future__ import annotations

import hashlib
import json
import sys
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.core.patch_recipes import (  # noqa: E402
    ASSEMBLY_ROOT,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.build import (  # noqa: E402
    EQUIPMENT_NORMCOM_OUTPUT_PATH,
    STATUS_BUILD_MANIFEST_PATH,
    STATUS_NORMCOM_OUTPUT_PATH,
    build_equipment_surface,
    build_status_surface,
)
from engine.shared.font8 import font8_tables  # noqa: E402
from engine.shared.status_layout import (  # noqa: E402
    compile_status_templates,
    load_font16_metrics,
    load_status_templates,
    load_stock_latin_codes,
)
from engine.surfaces.equipment_ui import (  # noqa: E402
    CONFIG_PATH as EQUIPMENT_CONFIG_PATH,
)
from engine.surfaces.status_ui import (  # noqa: E402
    ASCII_PHYSICAL_IDS,
    ASCII_RECORDS,
    ASSET_FILES,
    ATLAS_ADDRESS,
    COMP_PANEL_CAVE,
    CONFIG_PATH,
    DVLNAME_PATH,
    EQUIPMENT_LABEL_CAVE_LIMIT,
    FONT16_METRICS_PATH,
    FONT8_METRICS_PATH,
    LIGHT_AXIS_RECORD,
    LOAD_ADDRESS,
    RUNTIME_CAVE,
    RUNTIME_DATA,
    RUNTIME_INPUT_FILES,
    RUNTIME_LIMIT,
    TARGET,
    WRAPPER_CAVE,
    _ascii_data,
    _axis_data,
    _bind_patches,
    _configuration,
    _mirror_data,
    _source_assets,
    _status_terms,
    _template_data,
    build_status_ui,
)
from text.util.event_repack import FontMetrics  # noqa: E402


BASE_HASH = "a63ec7dbe6d5fdc03f9ff9f4c15fd556c26b9883dc0eb89e7bb18a70e5b58965"
EXPECTED_HASH = "d5cbdc03719a412e9b020141e774c563b4303a2821ac5669043db2409048bf43"
EXPECTED_COMPONENT_HASHES = {
    "wrapper_cave": "5422bdeac781e6d3e5307795a766cc2eb2a1a12d67c25b09eb1a304fa269933e",
    "font12_atlas": "0ae06b004b5c0114e2f4e0d49ad42c3c1985d891096d628828080393337329e0",
    "english_status_runtime": "40cfb28a87c0ab4234e5365fc487fd1c00126476a35f1cd2d746de77b5cc14de",
}
EXPECTED_ASSEMBLY = {
    "status_ui/affinity_dispatcher.s",
    "status_ui/affinity_font8_vwf.s",
    "status_ui/atlas_wrapper.s",
    "status_ui/font16_vwf.s",
    "status_ui/light_axis_pointer.s",
    "status_ui/name_race_dispatcher.s",
    "status_ui/party_alignment_first.s",
    "status_ui/party_alignment_repeat.s",
    "status_ui/party_alignment_third.s",
    "status_ui/skill_vwf.s",
    "status_ui/stock_icon_wrapper.s",
}


def _template_values() -> dict[str, str]:
    return {
        "level": "LV {level}",
        "experience": "EXP {experience}",
        "next_experience": "NEXT {experience_to_next}",
        "summon_cost": "CP {summon_cost}",
        "auto_setting": "AUTO {command}",
        "control": "CTRL {rank}",
        "personality_type": "TYPE {personality}",
        "loyalty": "Loyalty {loyalty}",
        "party_alignment": "P.A. {alignment}",
        "hit_points": "HP {current_hp}/{maximum_hp}",
        "magic_points": "MP {current_mp}/{maximum_mp}",
    }


class StatusUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = build_equipment_surface()[EQUIPMENT_NORMCOM_OUTPUT_PATH]
        cls.config = _configuration()
        cls.result = build_status_ui(cls.base)
        cls.patches = {patch.name: patch for patch in cls.result.patches}
        (
            cls.stock_dvlname,
            cls.stock_charname,
            cls.stock_font16,
        ) = _source_assets()
        cls.english_dvlname = DVLNAME_PATH.read_bytes()

    def test_complete_mature_normcom_is_reproduced_exactly(self) -> None:
        self.assertEqual(hashlib.sha256(self.base).hexdigest(), BASE_HASH)
        self.assertEqual(len(self.result.data), 352_360)
        self.assertEqual(hashlib.sha256(self.result.data).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.result.patches), 91)
        self.assertEqual(
            Counter(patch.group for patch in self.result.patches),
            {
                "status_rendering": 11,
                "status_layout": 8,
                "status_term_mirrors": 37,
                "status_ascii": 24,
                "status_templates": 11,
            },
        )

    def test_mature_components_have_exact_parity_oracles(self) -> None:
        for name, expected_hash in EXPECTED_COMPONENT_HASHES.items():
            with self.subTest(component=name):
                self.assertEqual(
                    hashlib.sha256(self.patches[name].replacement).hexdigest(),
                    expected_hash,
                )
        mirrors = b"".join(
            patch.replacement
            for patch in self.result.patches
            if patch.group == "status_term_mirrors"
        )
        self.assertEqual(
            hashlib.sha256(mirrors).hexdigest(),
            "ab939ba949285f9a961401ecfb338474db95a6e056260091594a27114d0c872f",
        )

    def test_recipes_separate_readable_code_from_generated_data(self) -> None:
        recipes = self.config.patches[TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {
                "generated": 76,
                "assembly": 6,
                "linked_pointer": 8,
                "pointer": 1,
            },
        )
        sources = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        self.assertEqual(sources, EXPECTED_ASSEMBLY)
        self.assertEqual(
            {path.relative_to(ASSEMBLY_ROOT).as_posix() for path in self.result.assembly_files},
            EXPECTED_ASSEMBLY,
        )
        runtime = next(
            recipe for recipe in recipes if recipe.name == "english_status_runtime"
        )
        self.assertEqual(
            tuple(path.relative_to(ASSEMBLY_ROOT).as_posix() for path in runtime.replacement.sources),
            (
                "status_ui/font16_vwf.s",
                "status_ui/skill_vwf.s",
                "status_ui/affinity_font8_vwf.s",
                "status_ui/name_race_dispatcher.s",
                "status_ui/affinity_dispatcher.s",
                "status_ui/stock_icon_wrapper.s",
            ),
        )
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))

    def test_digest_guards_resolve_before_replacements_are_applied(self) -> None:
        for recipe in self.config.patches[TARGET]:
            with self.subTest(recipe=recipe.name):
                expected = resolve_recipe_expected(recipe, self.base, LOAD_ADDRESS)
                self.assertEqual(len(self.patches[recipe.name].replacement), len(expected))
                if recipe.expected_size is not None:
                    self.assertEqual(len(expected), recipe.expected_size)

        guarded = next(
            recipe for recipe in self.config.patches[TARGET]
            if recipe.expected_sha256 is not None
        )
        damaged = bytearray(self.base)
        damaged[guarded.address - LOAD_ADDRESS] ^= 1
        with self.assertRaisesRegex(ValueError, "expected SHA-256"):
            resolve_recipe_expected(guarded, bytes(damaged), LOAD_ADDRESS)

        atlas = next(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name == "font12_atlas"
        )
        self.assertEqual(len(atlas.expected), 1512)
        self.assertEqual(set(atlas.expected), {0})

    def test_equipment_cave_stops_at_mature_status_wrapper(self) -> None:
        equipment = load_patch_recipe_configuration(
            EQUIPMENT_CONFIG_PATH,
            surface="equipment.ui",
            target_names={"EVENT.BIN", "NORMCOM.BIN"},
            input_names={"font8_metrics_sha256"},
        )
        label = next(
            recipe
            for recipe in equipment.patches[TARGET]
            if recipe.name == "label_drawer"
        )
        self.assertEqual(label.address + len(label.expected), WRAPPER_CAVE)
        self.assertEqual(EQUIPMENT_LABEL_CAVE_LIMIT, WRAPPER_CAVE)
        self.assertEqual(
            self.patches["wrapper_cave"].address
            + len(self.patches["wrapper_cave"].replacement),
            0x06021518,
        )
        self.assertEqual(
            self.patches["font12_atlas"].address
            + len(self.patches["font12_atlas"].replacement),
            0x06021DE8,
        )
        self.assertEqual(ATLAS_ADDRESS, 0x06021800)
        self.assertEqual(RUNTIME_CAVE, 0x06022000)
        self.assertEqual(
            RUNTIME_CAVE + len(self.patches["english_status_runtime"].replacement),
            0x06025A01,
        )
        self.assertEqual(RUNTIME_LIMIT, COMP_PANEL_CAVE)
        self.assertLess(0x06025A01, COMP_PANEL_CAVE)

    def test_every_direct_ascii_record_is_generated_from_its_binding(self) -> None:
        recipes = {
            recipe.name: recipe
            for recipe in self.config.patches[TARGET]
            if recipe.group == "status_ascii"
        }
        self.assertEqual(set(recipes), {name for name, _address, _size in ASCII_RECORDS})
        self.assertTrue(
            all(recipe.replacement.kind == "generated" for recipe in recipes.values())
        )

        templates = load_status_templates()
        current = _ascii_data(templates)
        translations = {
            ASCII_PHYSICAL_IDS[address]: current[name].rstrip(b"\0").decode("ascii")
            for name, address, _capacity in ASCII_RECORDS
        }
        go_address = next(
            address for name, address, _capacity in ASCII_RECORDS if name == "command_go"
        )
        translations[ASCII_PHYSICAL_IDS[go_address]] = "RUN"
        with patch(
            "engine.surfaces.status_ui.load_bound_translations",
            return_value=translations,
        ):
            mutated = _ascii_data(templates)
        self.assertEqual(mutated["command_go"], b"RUN\0")

    def test_status_template_grammar_owns_all_visible_literals(self) -> None:
        templates = compile_status_templates(_template_values())
        self.assertEqual(templates.prefixes["party_alignment"], "P.A.")
        self.assertEqual(templates.hp_mp_separator, "/")

        invalid = dict(_template_values(), level="LV  {level}")
        with self.assertRaisesRegex(ValueError, "boundary space"):
            compile_status_templates(invalid)
        invalid = dict(_template_values(), magic_points="MP {current_mp}:{maximum_mp}")
        with self.assertRaisesRegex(ValueError, "share one separator"):
            compile_status_templates(invalid)
        invalid = dict(_template_values(), party_alignment="P.A! {alignment}")
        with self.assertRaisesRegex(ValueError, "repeated cells"):
            compile_status_templates(invalid)
        invalid = dict(_template_values(), level="LV {rank}")
        with self.assertRaisesRegex(ValueError, "PREFIX"):
            compile_status_templates(invalid)

        unsupported = replace(load_status_templates(), party_prefix="P_A_")
        with patch(
            "engine.surfaces.status_ui._status_templates",
            return_value=unsupported,
        ), self.assertRaisesRegex(ValueError, "preserved stock FONT8 cells"):
            _bind_patches(
                self.config,
                self.base,
                self.stock_dvlname,
                self.english_dvlname,
                self.stock_charname,
                self.stock_font16,
            )

    def test_hp_mp_separator_uses_an_editable_font8_glyph(self) -> None:
        metrics = FontMetrics.load(FONT8_METRICS_PATH)
        _widths8, codes8 = font8_tables(metrics)
        stock_codes = load_stock_latin_codes(FONT8_METRICS_PATH)
        current = _template_data(load_status_templates(), codes8, stock_codes)
        self.assertEqual(current["human_hp_mp_separator"], b"\x00\xc6")
        self.assertEqual(current["demon_hp_mp_separator"], b"\x00\xc6")

        changed = replace(load_status_templates(), hp_mp_separator=":")
        edited = _template_data(changed, codes8, stock_codes)
        self.assertEqual(edited["human_hp_mp_separator"], codes8[":"].to_bytes(2, "big"))
        self.assertEqual(edited["demon_hp_mp_separator"], edited["human_hp_mp_separator"])
        self.assertNotEqual(edited["human_hp_mp_separator"], b"\x00\xc6")

    def test_law_and_light_axes_are_independently_editable_without_default_drift(self) -> None:
        instruction = self.patches["light_axis_pointer_load"]
        literal = self.patches["light_axis_pointer_literal"]
        runtime = self.patches["english_status_runtime"]
        self.assertEqual(instruction.replacement, b"\x64\xb3")
        self.assertEqual(literal.replacement, b"\0\0\0\0")
        offset = LIGHT_AXIS_RECORD - RUNTIME_CAVE
        self.assertEqual(runtime.replacement[offset : offset + 4], b"\0\0\0\0")
        self.assertEqual(LIGHT_AXIS_RECORD, RUNTIME_DATA - 4)

        axes, law, _light = _axis_data()
        with patch(
            "engine.surfaces.status_ui._axis_data",
            return_value=(axes, law, "X"),
        ):
            changed = _bind_patches(
                self.config,
                self.base,
                self.stock_dvlname,
                self.english_dvlname,
                self.stock_charname,
                self.stock_font16,
            )
        changed = {item.name: item for item in changed}
        self.assertEqual(changed["light_axis_pointer_load"].replacement, b"\xd4\x18")
        self.assertEqual(
            changed["light_axis_pointer_literal"].replacement,
            LIGHT_AXIS_RECORD.to_bytes(4, "big"),
        )
        self.assertEqual(
            changed["english_status_runtime"].replacement[offset : offset + 4],
            b"X\0\0\0",
        )

    def test_mirror_records_are_explicit_and_fail_closed(self) -> None:
        mirror_recipes = [
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.group == "status_term_mirrors"
        ]
        self.assertEqual(len(mirror_recipes), 37)
        self.assertTrue(
            all(recipe.replacement.kind == "generated" for recipe in mirror_recipes)
        )

        races, affinities, _demons, _characters = _status_terms()
        _widths16, codes16 = load_font16_metrics(FONT16_METRICS_PATH)
        races[22] = "AAAA"
        with self.assertRaisesRegex(ValueError, "race mirror 22"):
            _mirror_data(races, affinities, codes16)

    def test_asset_inventory_is_explicit(self) -> None:
        self.assertEqual(self.result.asset_files, ASSET_FILES)
        self.assertEqual(self.result.runtime_input_files, RUNTIME_INPUT_FILES)
        self.assertEqual(
            {path.relative_to(SATURN_ROOT.parent).as_posix() for path in ASSET_FILES},
            {
                "assets/text/affinities.json",
                "assets/text/battle/commands.json",
                "assets/text/characters.json",
                "assets/text/demons.json",
                "assets/text/races.json",
                "assets/text/terminology/alignments.json",
                "assets/text/ui/status.json",
            },
        )
        runtime_inputs = {
            path.relative_to(SATURN_ROOT.parent).as_posix()
            for path in RUNTIME_INPUT_FILES
        }
        self.assertEqual(
            {path for path in runtime_inputs if "/bindings/" in path},
            {
                "saturn/text/bindings/affinities.json",
                "saturn/text/bindings/alignments.json",
                "saturn/text/bindings/battle_commands.json",
                "saturn/text/bindings/characters.json",
                "saturn/text/bindings/demons.json",
                "saturn/text/bindings/races.json",
                "saturn/text/bindings/status.json",
            },
        )
        self.assertEqual(
            {path for path in runtime_inputs if "/corpus/" in path},
            {
                "saturn/text/corpus/compendium/addressed/race_names.json",
                "saturn/text/corpus/compendium/fixed/demon_names.json",
                "saturn/text/corpus/game/addressed/battle_command_labels.json",
                "saturn/text/corpus/game/addressed/combat_analysis_affinities.json",
                "saturn/text/corpus/game/addressed/da3d_analyze.json",
                "saturn/text/corpus/game/addressed/normcom_status_ascii.json",
                "saturn/text/corpus/game/addressed/normcom_tables.json",
                "saturn/text/corpus/game/eve/shopsmp.json",
                "saturn/text/corpus/game/fixed/charname.json",
                "saturn/text/corpus/game/fixed/dvlname.json",
            },
        )

    def test_parent_build_keeps_the_equipment_base_and_terminal_output_separate(self) -> None:
        outputs = build_status_surface()
        self.assertNotEqual(EQUIPMENT_NORMCOM_OUTPUT_PATH, STATUS_NORMCOM_OUTPUT_PATH)
        self.assertEqual(
            hashlib.sha256(outputs[EQUIPMENT_NORMCOM_OUTPUT_PATH]).hexdigest(),
            BASE_HASH,
        )
        self.assertEqual(
            hashlib.sha256(outputs[STATUS_NORMCOM_OUTPUT_PATH]).hexdigest(),
            EXPECTED_HASH,
        )
        manifest = json.loads(outputs[STATUS_BUILD_MANIFEST_PATH])
        self.assertEqual(manifest["surface"], "status.ui")
        self.assertEqual(manifest["base"]["sha256"], BASE_HASH)
        self.assertEqual(manifest["output"]["sha256"], EXPECTED_HASH)
        self.assertEqual(len(manifest["asset_inputs"]), 7)
        self.assertEqual(len(manifest["assembly_inputs"]), 11)
        self.assertEqual(len(manifest["runtime_inputs"]), 24)
        self.assertEqual(
            set(manifest["source_inputs"]),
            {"game:CHARNAME.DAT", "game:DVLNAME.DAT", "game:FONT16.FON"},
        )

    def test_generated_inventory_rejects_an_unowned_payload(self) -> None:
        patches = tuple(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name != "axis_law"
        )
        incomplete = replace(self.config, patches={TARGET: patches})
        with self.assertRaisesRegex(ValueError, "no configured owner: axis_law"):
            _bind_patches(
                incomplete,
                self.base,
                self.stock_dvlname,
                self.english_dvlname,
                self.stock_charname,
                self.stock_font16,
            )


if __name__ == "__main__":
    unittest.main()
