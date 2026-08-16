from __future__ import annotations

import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    OPTIONS_BUILD_MANIFEST_PATH,
    OPTIONS_OUTPUT_PATH,
    build_options_surface,
)
from engine.core.patch_recipes import ASSEMBLY_ROOT  # noqa: E402
from engine.surfaces.options_ui import (  # noqa: E402
    ACTION_RECORDS,
    ASSET_FILES,
    COMPOUND_BASE,
    CONFIG_PATH,
    CORPUS_PATH,
    DORMANT_LABEL_OFFSET,
    FOOTER_RECORDS,
    ITEM_SORT_RECORDS,
    LABEL_RECORDS,
    MAGIC_SORT_RECORDS,
    PAGE2_RECORDS,
    REQUIRED_IDS,
    RUNTIME_INPUT_FILES,
    TARGET,
    _bind_patches,
    _assembled,
    _build_runtime,
    _configuration,
    _options_terms,
    _source_cfg_set,
    _validate_inputs,
    build_options_ui,
)


EXPECTED_HASH = "6d25bab3b2137a3f5fea49d69bcf374a918f68fe5d26f170139f6a76c5fce010"
EXPECTED_COMPOUNDS = (
    "AR", " A", "ign", "Re", "co", "ve", "Sp", "ec", "At", "De",
    "Co", "ns", "um", "ab", "le", "Eq", "ui", "pm", "en",
)
EXPECTED_COMPONENT_HASHES = {
    "expanded_label_table": "ac064e109c7b29eed89a89e4f3b5a3ce92455f90a6935b124ca6cef13f636b50",
    "active_row_runtime": "7a382b17acd41bb576d78ff3905f5e92a565fb3a485526bf2a5081f9b061c188",
    "magic_sort_table": "a64360a869528c332c9223093f3899734bd1d1f1715a5b5044857d5e5a4492f5",
    "item_sort_table": "2bb9906c4da9447ebbc049a5dbaffee0987f19b0f443130a8424008fd98114a4",
    "action_vwf_runtime": "7be1ff6c7a732d6b060bcba498174631807dd2cf1d4d5b2a2534bf981857737b",
    "action_widths": "cd527d870cdce26e2c048dc54e632afc6e251dde38bbdd1dee11eb2f1c5b1bad",
    "action_atlas": "1bdd27b0b11ca57a9db848393a937c14391f046e0b0dc398dce47ca6ce3eb32c",
    "glyph_vwf_runtime": "ff18afb32613ad0060f16a02b394af79a051e3cdcfb50da5002bb63338f990f8",
    "font16_widths": "09322c0141ac2ad15bb685d1a129936fb9d710ab31b7365f0c793e29221260dd",
    "compound_widths": "1e1e672a426b556b35321b9f0103cc9c64599bf9cc12ed747651568312d5fe21",
    "compound_glyph_runtime": "f7db305dd98bdd64e26ef0acecda99afd9d67f8a4f045a8f7c9c304f4e0060f4",
    "compound_bitmaps": "bfabe81f28aae4190e76f89066b8c5f55b12ddabfbe3a4d1d6fa48b349be2ba7",
    "label_lengths": "82704fc9c2ff45361bbeeb04e415c5b3ff7b424f309c1097209d9a59e852c236",
}
EXPECTED_ASSEMBLY = {
    "options_ui/action_vwf.s",
    "options_ui/active_row_noop.s",
    "options_ui/active_row_renderer.s",
    "options_ui/compound_glyph.s",
    "options_ui/glyph_vwf.s",
}


class OptionsUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = _source_cfg_set()
        cls.config = _configuration()
        cls.result = build_options_ui(cls.base)
        cls.patches = {item.name: item for item in cls.result.patches}
        cls.terms = _options_terms()

    def test_complete_mature_cfg_set_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.result.data), 273_560)
        self.assertEqual(hashlib.sha256(self.result.data).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.result.patches), 57)
        self.assertEqual(
            Counter(item.group for item in self.result.patches),
            {
                "options_runtime": 20,
                "options_labels": 13,
                "options_ordering_popup": 13,
                "options_controller": 11,
            },
        )

    def test_readable_code_and_generated_data_are_separate(self) -> None:
        recipes = self.config.patches[TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {
                "generated": 24,
                "instruction": 17,
                "linked_pointer": 12,
                "assembly": 4,
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
        self.assertNotIn('"replacement"', CONFIG_PATH.read_text(encoding="utf-8"))

    def test_configured_assembly_sources_are_the_actual_build_inputs(self) -> None:
        with patch(
            "engine.surfaces.options_ui._assembled", wraps=_assembled
        ) as assembled:
            _bind_patches(self.config, self.base)
        actual = {
            call.args[0].relative_to(ASSEMBLY_ROOT).as_posix()
            for call in assembled.call_args_list
        }
        self.assertEqual(actual, EXPECTED_ASSEMBLY)

    def test_mature_components_have_exact_independent_hashes(self) -> None:
        for name, digest in EXPECTED_COMPONENT_HASHES.items():
            with self.subTest(component=name):
                self.assertEqual(
                    hashlib.sha256(self.patches[name].replacement).hexdigest(),
                    digest,
                )
        action_records = b"".join(
            self.patches[name].replacement for name, _offset in ACTION_RECORDS
        )
        self.assertEqual(
            hashlib.sha256(action_records).hexdigest(),
            "4a2a8641003a38c8492dced63b7bd88926c6bc703e0f1d1a08b7157733b9611b",
        )

    def test_every_visible_field_has_one_runtime_owner(self) -> None:
        self.assertEqual(len(REQUIRED_IDS), 38)
        self.assertEqual(len(self.terms), 38)
        self.assertEqual(len(LABEL_RECORDS), 18)
        self.assertEqual(len(PAGE2_RECORDS), 3)
        self.assertEqual(len(MAGIC_SORT_RECORDS) + len(ITEM_SORT_RECORDS), 7)
        self.assertEqual(len(ACTION_RECORDS), 8)
        self.assertEqual(len(FOOTER_RECORDS), 2)
        self.assertEqual(CORPUS_PATH.name, "config_static.json")

    def test_zero_length_config_row_is_preserved_but_not_asset_owned(self) -> None:
        table = self.patches["expanded_label_table"].replacement
        self.assertEqual(
            table[:16], self.base[DORMANT_LABEL_OFFSET : DORMANT_LABEL_OFFSET + 16]
        )
        self.assertEqual(table[16:32], bytes(16))
        self.assertEqual(self.base[0x9E02:0x9E04], b"\0\0")
        self.assertNotIn("title", self.terms)

    def test_compound_cells_are_derived_from_complete_authored_phrases(self) -> None:
        self.assertEqual(self.result.compounds, EXPECTED_COMPOUNDS)
        self.assertEqual(
            tuple(range(COMPOUND_BASE, COMPOUND_BASE + len(EXPECTED_COMPOUNDS))),
            tuple(range(1848, 1867)),
        )
        self.assertLess(COMPOUND_BASE + len(self.result.compounds) - 1, 1871)

        changed = dict(
            self.terms,
            assist_heal="Restore",
            footer_assign="AAAAAAAAAA",
            footer_finish="BBBBBBBBBB",
        )
        with patch(
            "engine.surfaces.options_ui._options_terms", return_value=changed
        ):
            runtime = _build_runtime()
            changed_patches, bound_runtime = _bind_patches(self.config, self.base)
        self.assertEqual(runtime.compounds, bound_runtime.compounds)
        self.assertEqual(len(changed_patches), len(self.result.patches))
        self.assertNotEqual(
            runtime.generated["magic_sort_table"],
            self.patches["magic_sort_table"].replacement,
        )
        self.assertNotEqual(
            runtime.generated["footer_assign"],
            self.patches["footer_assign"].replacement,
        )
        self.assertNotEqual(runtime.compounds, EXPECTED_COMPOUNDS)

        narrow = dict(self.terms, assist_heal="i" * 20)
        with patch(
            "engine.surfaces.options_ui._options_terms", return_value=narrow
        ):
            _changed_patches, narrow_runtime = _bind_patches(self.config, self.base)
        self.assertIn("iiii", narrow_runtime.compounds)

    def test_controller_action_edit_rebuilds_atlas_and_record(self) -> None:
        changed = dict(self.terms, action_cancel="Back")
        with patch(
            "engine.surfaces.options_ui._options_terms", return_value=changed
        ):
            runtime = _build_runtime()
        self.assertNotEqual(
            runtime.generated["action_atlas"], self.patches["action_atlas"].replacement
        )
        self.assertNotEqual(
            runtime.generated["action_cancel"], self.patches["action_cancel"].replacement
        )

    def test_capacity_and_stock_invariants_fail_closed(self) -> None:
        changed = dict(self.terms, battle_messages="X" * 17)
        with patch(
            "engine.surfaces.options_ui._options_terms", return_value=changed
        ), self.assertRaisesRegex(ValueError, "maximum is 16"):
            _build_runtime()

        damaged = bytearray(self.base)
        damaged[0x9FE6] ^= 1
        with self.assertRaisesRegex(ValueError, "preset order"):
            _validate_inputs(self.config, bytes(damaged))

    def test_generated_and_assembly_inventories_fail_closed(self) -> None:
        recipes = tuple(
            recipe
            for recipe in self.config.patches[TARGET]
            if recipe.name != "controls"
        )
        incomplete = type(self.config)(
            self.config.surface,
            self.config.targets,
            self.config.inputs,
            {TARGET: recipes},
        )
        with self.assertRaisesRegex(ValueError, "no configured owner: controls"):
            _bind_patches(incomplete, self.base)

    def test_parent_build_records_complete_provenance(self) -> None:
        outputs = build_options_surface()
        self.assertEqual(
            hashlib.sha256(outputs[OPTIONS_OUTPUT_PATH]).hexdigest(), EXPECTED_HASH
        )
        manifest = json.loads(outputs[OPTIONS_BUILD_MANIFEST_PATH])
        self.assertEqual(manifest["surface"], "options.ui")
        self.assertEqual(manifest["output"]["sha256"], EXPECTED_HASH)
        self.assertEqual(manifest["patches"], 57)
        self.assertEqual(manifest["derived_local_compound_glyphs"], 19)
        self.assertEqual(len(manifest["asset_inputs"]), len(ASSET_FILES))
        self.assertEqual(len(manifest["runtime_inputs"]), len(RUNTIME_INPUT_FILES))
        self.assertEqual(set(manifest["source_inputs"]), {"game:CFG_SET.BIN"})
        self.assertEqual(set(manifest["assembly_inputs"]), {
            f"saturn/engine/asm/{name}" for name in EXPECTED_ASSEMBLY
        })


if __name__ == "__main__":
    unittest.main()
