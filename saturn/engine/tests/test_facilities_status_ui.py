from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    EQUIPMENT_EVENT_OUTPUT_PATH,
    build_equipment_surface,
)
from engine.core.patch_recipes import ASSEMBLY_ROOT, resolve_recipe_expected  # noqa: E402
import engine.surfaces.facilities_status_ui as status  # noqa: E402


BASE_SHA256 = "c292f62b306f1f98a52590adbf8ae8da1884bab3e9ae0a94d8ef091ae11e9d36"
OUTPUT_SHA256 = "7f765a31d200d641e1bc2b254a4575e965c6228aae611b7e7bf4360c70ff20d9"
RUNTIME_USED_SHA256 = (
    "95cbe0e4eaeb2b4564a4af7a0dbae1e9537ace6606e69d299829b8b671c1e7d9"
)
RUNTIME_FULL_SHA256 = (
    "4f0fa00cfc1ca5669fea9e25d5bf0c50b430c591a678b9476343d9cad208ecb1"
)
AUTO_USED_SHA256 = "7e5a0d31dc8e72faaeb538e71835cf43ec300394a8e5e55add9565dda9014df7"
AUTO_FULL_SHA256 = "9554b27d9138c82cf5410a7112b3fb885e8f1ffa828498b4921e5864a325fa55"
MIRROR_SHA256 = "ab939ba949285f9a961401ecfb338474db95a6e056260091594a27114d0c872f"

EXPECTED_ASSEMBLY = {
    "facilities_status_ui/affinity_dispatcher.s",
    "facilities_status_ui/affinity_font8_vwf.s",
    "facilities_status_ui/event_character_insert.s",
    "facilities_status_ui/event_term_inserts.s",
    "facilities_status_ui/facility_name_drawers.s",
    "facilities_status_ui/font16_from_font8.s",
    "facilities_status_ui/font16_vwf.s",
    "facilities_status_ui/font8_surface_blitter.s",
    "facilities_status_ui/name_race_dispatcher.s",
    "facilities_status_ui/skill_vwf.s",
    "status_ui/auto_action_vwf.s",
    "status_ui/auto_block_ascii.s",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FacilitiesStatusUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = build_equipment_surface()[EQUIPMENT_EVENT_OUTPUT_PATH]
        cls.config = status._configuration()
        cls.result = status.build_facilities_status_ui(cls.base)
        cls.patches = {patch.name: patch for patch in cls.result.patches}
        (
            cls.stock_event,
            cls.stock_dvlname,
            cls.stock_charname,
            cls.stock_font16,
        ) = status._source_assets()

    def test_complete_facilities_event_is_reproduced_exactly(self) -> None:
        self.assertEqual(_sha256(self.base), BASE_SHA256)
        self.assertEqual(len(self.result.data), 354_072)
        self.assertEqual(_sha256(self.result.data), OUTPUT_SHA256)
        self.assertEqual(len(self.result.patches), 74)
        self.assertEqual(
            Counter(patch.group for patch in self.result.patches),
            {
                "fusion.status_ui": 22,
                "event.term_inserts": 3,
                "facilities.command_ui": 1,
                "bar.status_ui": 4,
                "healer.status_ui": 7,
                "event.fixed_text_compatibility": 37,
            },
        )

    def test_runtime_matches_mature_oracle_and_owns_the_whole_cave(self) -> None:
        runtime = self.patches["fusion_status_runtime"]
        auto_runtime = self.patches["fusion_auto_runtime"]
        self.assertEqual(runtime.address, 0x06023294)
        self.assertEqual(auto_runtime.address, 0x06065BB4)
        self.assertEqual(self.result.runtime_used_size, 12_306)
        self.assertEqual(self.result.runtime_capacity, 12_640)
        self.assertEqual(len(runtime.replacement), 11_796)
        self.assertEqual(len(auto_runtime.replacement), 844)
        self.assertEqual(
            _sha256(runtime.replacement[:11_718]),
            RUNTIME_USED_SHA256,
        )
        self.assertEqual(_sha256(runtime.replacement), RUNTIME_FULL_SHA256)
        self.assertEqual(
            _sha256(auto_runtime.replacement[:588]), AUTO_USED_SHA256
        )
        self.assertEqual(_sha256(auto_runtime.replacement), AUTO_FULL_SHA256)
        self.assertEqual(
            runtime.replacement[11_718:], bytes(11_796 - 11_718)
        )
        self.assertEqual(
            auto_runtime.replacement[588:], bytes(844 - 588)
        )
        self.assertEqual(
            self.result.runtime_arenas,
            (
                status.RuntimeArena(
                    "event_facilities_status",
                    0x06023294,
                    11_718,
                    11_796,
                ),
                status.RuntimeArena(
                    "event_status_auto",
                    0x06065BB4,
                    588,
                    844,
                ),
            ),
        )

    def test_exact_recipe_and_assembly_ownership_is_readable(self) -> None:
        recipes = self.config.patches[status.TARGET]
        self.assertEqual(
            tuple(status._recipe_contract(recipe) for recipe in recipes),
            status.RECIPE_CONTRACT,
        )
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {"generated": 53, "assembly": 3, "linked_pointer": 18},
        )
        assembly = {
            path.relative_to(ASSEMBLY_ROOT).as_posix()
            for path in self.result.assembly_files
        }
        self.assertEqual(assembly, EXPECTED_ASSEMBLY)
        self.assertNotIn('"replacement"', status.CONFIG_PATH.read_text("utf-8"))

    def test_mirrors_cover_only_the_grounded_event_records(self) -> None:
        mirrors = [
            patch
            for patch in self.result.patches
            if patch.group == "event.fixed_text_compatibility"
        ]
        self.assertEqual(
            [patch.name for patch in mirrors],
            [
                "races_022",
                "affinities_001",
                "affinities_029",
                "affinities_051",
                "affinities_052",
                "affinities_060",
                "affinities_064",
                *(f"affinities_{index:03d}" for index in range(66, 96)),
            ],
        )
        self.assertEqual(_sha256(b"".join(row.replacement for row in mirrors)), MIRROR_SHA256)

    def test_every_event_status_entry_uses_the_shared_auto_block_runtime(self) -> None:
        action_patch = self.patches["fusion_auto_action_name_drawer"]
        block_patch = self.patches["fusion_auto_block_ascii_drawer"]
        self.assertEqual(action_patch.address, 0x06055744)
        self.assertEqual(action_patch.expected, bytes.fromhex("06051830"))
        self.assertEqual(block_patch.address, 0x0605573C)
        self.assertEqual(block_patch.expected, bytes.fromhex("060516e8"))

        runtime = self.patches["fusion_status_runtime"].replacement
        auto_runtime = self.patches["fusion_auto_runtime"].replacement
        action = int.from_bytes(action_patch.replacement, "big")
        block = int.from_bytes(block_patch.replacement, "big")
        action_offset = action - status.AUTO_RUNTIME_ADDRESS
        block_offset = block - status.AUTO_RUNTIME_ADDRESS
        action_blob = auto_runtime[action_offset:block_offset]
        block_blob = auto_runtime[block_offset:]
        for address in (
            status.CURRENT_PARTY_TYPE,
            status.HUMAN_AUTO_STATE,
            status.DEMON_AUTO_STATE,
            status.ITEMNAME_BASE,
            status.MAGNAME_BASE,
            status.FONT8_GLYPH_DRAWER,
            status.FONT12_DRAWER,
        ):
            self.assertIn(address.to_bytes(4, "big"), action_blob)
        for address in (*status.PARTY_ALIGNMENT_SOURCES.values(), 0x060516E8):
            self.assertIn(address.to_bytes(4, "big"), block_blob)
        self.assertIn(b"LAW\0NEUTRAL\0CHAOS\0", runtime)

        action_source = (
            ASSEMBLY_ROOT / "status_ui" / "auto_action_vwf.s"
        ).read_text("ascii")
        block_source = (
            ASSEMBLY_ROOT / "status_ui" / "auto_block_ascii.s"
        ).read_text("ascii")
        self.assertIn("add     #4, r11", action_source)
        self.assertIn("add     #4, r0", action_source)
        self.assertIn("add     #4, r7", block_source)
        self.assertEqual(status._party_alignment_terms(), ("LAW", "NEUTRAL", "CHAOS"))
        for text in status._party_alignment_terms():
            self.assertTrue(status._encode_party_alignment_ascii(text).endswith(b"\0"))
        with self.assertRaisesRegex(ValueError, "exceeds 8 original FONT8 cells"):
            status._encode_party_alignment_ascii("NEUTRALITY")

    def test_facility_compounds_use_authored_stock_latin_not_legacy_review_typo(self) -> None:
        aliases = self.patches["facility_revive_status_aliases"].replacement
        self.assertEqual(aliases, bytes.fromhex("1c0f2013200f1d1e0b1e1f1d"))
        self.assertNotEqual(aliases, bytes.fromhex("1c0f20130f211d1e0b1e1f1d"))

        values = {
            "game.facility_command_labels.o0425f8": "REVIVE",
            "game.facility_command_labels.o0425fe": "STATUS",
        }
        stock_codes = status.load_stock_latin_codes(status.FONT8_METRICS_PATH)
        with patch.object(status, "_bound_translations", return_value=values):
            self.assertEqual(status._facility_alias_data(stock_codes), aliases)
        edited = dict(values)
        edited["game.facility_command_labels.o0425f8"] = "RESCUE"
        with patch.object(status, "_bound_translations", return_value=edited):
            changed = status._facility_alias_data(stock_codes)
        self.assertNotEqual(changed, aliases)

    def test_fusion_confirmation_sites_remain_exclusively_owned_upstream(self) -> None:
        self.assertFalse(
            status.FUSION_CONFIRMATION_PATCH_NAMES & set(self.patches)
        )
        for patch_row in self.result.patches:
            patch_end = patch_row.address + len(patch_row.replacement)
            for owner, address, size in status.FUSION_CONFIRMATION_SPANS:
                with self.subTest(patch=patch_row.name, confirmation=owner):
                    self.assertFalse(
                        patch_row.address < address + size and address < patch_end
                    )

    def test_generated_name_tables_use_fresh_manifests_not_config_pins(self) -> None:
        inputs = json.loads(status.CONFIG_PATH.read_text("utf-8"))["inputs"]
        self.assertNotIn("dvlname_sha256", inputs)
        self.assertNotIn("magname_sha256", inputs)
        self.assertIn(status.COMP_MENU_TEXT_BUILD_PATH, self.result.runtime_input_files)
        self.assertIn(status.BATTLE_UI_TEXT_BUILD_PATH, self.result.runtime_input_files)

        document = json.loads(status.COMP_MENU_TEXT_BUILD_PATH.read_text("utf-8"))
        document["outputs"]["DVLNAME.DAT"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            stale = Path(temporary) / "comp_menu_build.json"
            stale.write_text(json.dumps(document), encoding="utf-8")
            with patch.object(status, "COMP_MENU_TEXT_BUILD_PATH", stale):
                with self.assertRaisesRegex(ValueError, "manifest SHA-256 is stale"):
                    status._validate_inputs(
                        self.config,
                        self.base,
                        self.stock_event,
                        self.stock_dvlname,
                        self.stock_charname,
                        self.stock_font16,
                    )

    def test_race_and_facility_name_edits_obey_their_real_pixel_limits(self) -> None:
        races, affinities, demons, characters = status._status_terms()
        too_wide = list(races)
        too_wide[0] = "WWWWWW"
        with patch.object(
            status,
            "_status_terms",
            return_value=(too_wide, affinities, demons, characters),
        ):
            with self.assertRaisesRegex(ValueError, "status race exceeds 46px"):
                status.build_facilities_status_ui(self.base)

        too_wide_names = list(demons)
        too_wide_names[0] = "W" * 15
        with patch.object(
            status,
            "_status_terms",
            return_value=(races, affinities, too_wide_names, characters),
        ):
            with self.assertRaisesRegex(ValueError, "status name 0 exceeds 126px"):
                status.build_facilities_status_ui(self.base)

        unsupported_status_names = list(characters)
        unsupported_status_names[5] = "A.B"
        with patch.object(
            status,
            "_status_terms",
            return_value=(races, affinities, demons, unsupported_status_names),
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"status name mapper cannot convert '\.'",
            ):
                status.build_facilities_status_ui(self.base)

        drinks, talk_labels, healing_all = status._facility_terms()
        too_wide_talk = list(talk_labels)
        too_wide_talk[0] = "W" * 20
        with patch.object(
            status,
            "_facility_terms",
            return_value=(drinks, too_wide_talk, healing_all),
        ):
            with self.assertRaisesRegex(ValueError, r"bar patron \d+ exceeds 64px"):
                status.build_facilities_status_ui(self.base)

        with patch.object(
            status,
            "_facility_terms",
            return_value=(drinks, talk_labels, "I" * 40),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "healer all-members exceeds 32 glyphs",
            ):
                status.build_facilities_status_ui(self.base)

    def test_runtime_relocates_safely_when_authored_terms_change_size(self) -> None:
        drinks, talk_labels, _healing_all = status._facility_terms()
        for term, expected_size in (("All", 12_298), ("All Party Members", 12_310)):
            with self.subTest(term=term), patch.object(
                status,
                "_facility_terms",
                return_value=(drinks, talk_labels, term),
            ):
                changed = status.build_facilities_status_ui(self.base)
            changed_patches = {patch.name: patch for patch in changed.patches}
            self.assertEqual(changed.runtime_used_size, expected_size)
            if term == "All":
                self.assertLess(
                    changed.runtime_used_size,
                    self.result.runtime_used_size,
                )
            else:
                self.assertGreater(
                    changed.runtime_used_size,
                    self.result.runtime_used_size,
                )
            self.assertLessEqual(changed.runtime_used_size, changed.runtime_capacity)
            self.assertEqual(
                len(changed_patches["fusion_status_runtime"].replacement),
                status.RUNTIME_CAPACITY,
            )
            self.assertEqual(
                len(changed_patches["fusion_auto_runtime"].replacement),
                status.AUTO_RUNTIME_CAPACITY,
            )
            self.assertNotEqual(_sha256(changed.data), OUTPUT_SHA256)
            for name in (
                "bar_drink_name_drawer",
                "healing_all_drawer_0",
                "event_dialogue_demon_name_insert",
            ):
                with self.subTest(term=term, patch=name):
                    self.assertNotEqual(
                        changed_patches[name].replacement,
                        self.patches[name].replacement,
                    )

        with patch.object(
            status,
            "_facility_terms",
            return_value=(drinks, talk_labels, "All Party Members"),
        ):
            grown = status.build_facilities_status_ui(self.base)
        grown_patches = {patch.name: patch for patch in grown.patches}
        self.assertGreater(
            grown.runtime_used_size, self.result.runtime_used_size
        )
        self.assertLessEqual(grown.runtime_used_size, grown.runtime_capacity)
        self.assertNotEqual(_sha256(grown.data), OUTPUT_SHA256)
        for name in (
            "bar_drink_name_drawer",
            "healing_all_drawer_0",
            "event_dialogue_demon_name_insert",
        ):
            with self.subTest(grown_patch=name):
                self.assertNotEqual(
                    grown_patches[name].replacement,
                    self.patches[name].replacement,
                )

    def test_identity_target_and_replacement_drift_fail_closed(self) -> None:
        def mutate(document: dict[str, object], variant: str) -> None:
            groups = document["groups"]
            assert isinstance(groups, list)
            rows = {
                row["name"]: row
                for group in groups
                for row in group["patches"]
            }
            if variant == "rename":
                rows["fusion_parameter_nodes"]["name"] = "renamed_parameter_nodes"
            elif variant == "retarget":
                rows["fusion_name_race_drawer"]["address"] = "0x06054bd0"
            elif variant == "source":
                sources = rows["fusion_status_runtime"]["assembly"]
                sources[0], sources[1] = sources[1], sources[0]
            elif variant == "link":
                rows["fusion_name_race_drawer"]["linked_pointer"] = "drifted_link"
            elif variant == "generator":
                rows["fusion_parameter_nodes"]["generated"] = "drifted_generator"
            else:
                raise AssertionError(variant)

        original = json.loads(status.CONFIG_PATH.read_text("utf-8"))
        for variant in ("rename", "retarget", "source", "link", "generator"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                document = json.loads(json.dumps(original))
                mutate(document, variant)
                path = Path(temporary) / "facilities_status_ui.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                with patch.object(status, "CONFIG_PATH", path):
                    with self.assertRaisesRegex(ValueError, "recipe contract changed"):
                        status._configuration()

    def test_every_composed_site_guard_matches_the_equipment_base(self) -> None:
        for recipe in self.config.patches[status.TARGET]:
            with self.subTest(recipe=recipe.name):
                expected = resolve_recipe_expected(
                    recipe,
                    self.base,
                    status.LOAD_ADDRESS,
                )
                self.assertEqual(
                    len(expected),
                    len(self.patches[recipe.name].replacement),
                )


if __name__ == "__main__":
    unittest.main()
