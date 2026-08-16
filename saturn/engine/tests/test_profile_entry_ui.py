from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.profile_entry_ui as profile  # noqa: E402
from engine.core.patching import PatchError  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


CORRECTED_HASH = "bde4ea3bd7edd9bd9427aeaed68637bb597163a6c1db73e3d720222d5ebf8397"
MATURE_BUGGY_HASH = "11b5824ffb71f54137ff9a644e0d55ef0dee3ee6f9e176a72310574ddecf22d3"


class ProfileEntryUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = profile.build_profile_entry_ui()
        cls.patches = {row.name: row for row in cls.build.patches}

    def test_corrected_mature_output_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.build.data), 155208)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), CORRECTED_HASH)
        self.assertEqual(len(self.build.patches), 22)
        self.assertEqual(
            tuple(dict.fromkeys(row.group for row in self.build.patches)),
            (
                "profile_entry.runtime",
                "profile_entry.templates",
                "profile_entry.occupation",
            ),
        )

    def test_confirmation_sentinel_is_the_only_mature_binary_delta(self) -> None:
        sentinel = 0x20C3E
        self.assertEqual(self.build.data[sentinel : sentinel + 2], b"\x80\x00")
        buggy = bytearray(self.build.data)
        buggy[sentinel : sentinel + 2] = b"\0\0"
        self.assertEqual(hashlib.sha256(buggy).hexdigest(), MATURE_BUGGY_HASH)

    def test_runtime_arena_preserves_the_proven_default_layout(self) -> None:
        arena = self.patches["runtime_arena"]
        self.assertEqual(arena.address, profile.DATA_ADDRESS)
        self.assertEqual(len(arena.replacement), profile.RUNTIME_CAPACITY)
        self.assertEqual(self.build.runtime_used_size, 5112)
        self.assertEqual(self.build.runtime_capacity, 6840)
        self.assertEqual(
            hashlib.sha256(arena.replacement).hexdigest(),
            "2eaef6daec94c6dee438ca76b1b96ebe53201618244c09ded5864fea9cb35a11",
        )
        self.assertEqual(
            hashlib.sha256(arena.replacement[:2504]).hexdigest(),
            "59bf35d50b3f80d480f94efeadf9079486c219e11e8627194e6fe2715896aae8",
        )
        self.assertEqual(
            hashlib.sha256(arena.replacement[2504:5112]).hexdigest(),
            "135dadfde95bb69a5d602bf1fac4c0c296b6b1d643d78fac7231dc8014a8b9df",
        )
        self.assertFalse(any(arena.replacement[5112:]))

    def test_typed_recipe_and_provenance_inventories_are_complete(self) -> None:
        expected_names = {
            "runtime_arena",
            "entry_template",
            "confirm_template",
            "occupation_template",
            "router_hook",
            "router_pointer",
            "init_pointer",
            "initial_row_flush_pointer",
            "commit_pointer",
            "end_pointer_060312b4",
            "end_pointer_060328fc",
            "tab_draw_pointer",
            "skip_stock_text",
            "occupation_cursor_pointer",
            "occupation_count_value",
            "occupation_count_compare",
            "occupation_stride_flag",
            "occupation_row_stride",
            "occupation_left_offset",
            "occupation_count_0603297e",
            "occupation_right_offset",
            "occupation_count_06032a44",
        }
        self.assertEqual(set(self.patches), expected_names)
        self.assertEqual(
            {
                path.relative_to(profile.ENGINE_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "asm/profile_entry_ui/entry.s",
                "asm/profile_entry_ui/router_hook.s",
                "asm/profile_entry_ui/skip_stock_text.s",
            },
        )
        self.assertEqual(
            {path.name for path in self.build.asset_files},
            {"profile_entry.json", "player_profile.json"},
        )
        self.assertIn(profile.PLAYER_NAMES_PATH, self.build.runtime_input_files)
        self.assertEqual(
            dict(self.build.source_inputs),
            {f"game:{profile.TARGET}": profile._sha256(profile._stock_source())},
        )

    def test_grids_use_the_named_stock_kanji_reference_set(self) -> None:
        arena = self.patches["runtime_arena"].replacement
        codes = profile._kanji_codes()

        def word(offset: int) -> int:
            return struct.unpack_from(">H", arena, offset)[0]

        upper_a = (profile.GRID_COLUMNS + profile.GRID_CONTENT_COLUMN) * 2
        self.assertEqual(word(upper_a), codes["A"])
        self.assertEqual(
            word((profile.END_ROW * profile.GRID_COLUMNS + profile.END_COLUMN) * 2),
            profile.END_DISPLAY_CELL,
        )
        symbol_display = 4 * 304
        explicit_space = (
            symbol_display
            + ((profile.GRID_CONTENT_ROW + 1) * profile.GRID_COLUMNS + 9) * 2
        )
        self.assertEqual(word(explicit_space), codes[" "])
        symbol_commit = symbol_display + 304
        self.assertEqual(word(symbol_commit + explicit_space - symbol_display), 0x20)

    def test_three_glyph_no_edit_uses_the_free_confirmation_cell(self) -> None:
        original = profile._translation

        def edited(catalog, key: str) -> str:
            return "NO!" if key == "label_no" else original(catalog, key)

        with patch.object(profile, "_translation", side_effect=edited):
            changed = profile.build_profile_entry_ui()
        confirm = next(row for row in changed.patches if row.name == "confirm_template")
        words = struct.unpack(">20H", confirm.replacement)
        metrics = FontMetrics.load(profile.FONT16_METRICS_PATH).by_text
        self.assertEqual(
            words[16:20],
            (metrics["N"].code, metrics["O"].code, metrics["!"].code, 0x8000),
        )

    def test_authored_reverse_order_and_separator_change_storage_code(self) -> None:
        with patch.object(
            profile,
            "_full_name_storage",
            return_value="{last_name}/{first_name}",
        ):
            changed = profile.build_profile_entry_ui()
        self.assertNotEqual(changed.data, self.build.data)
        self.assertEqual(changed.runtime_used_size, self.build.runtime_used_size + 4)
        self.assertLess(changed.runtime_used_size, changed.runtime_capacity)

    def test_data_growth_relocates_controller_and_every_link(self) -> None:
        original = profile._translation

        def edited(catalog, key: str) -> str:
            return "UPPER!!!!" if key == "tab_upper" else original(catalog, key)

        with patch.object(profile, "_translation", side_effect=edited):
            changed = profile.build_profile_entry_ui()
        changed_patches = {row.name: row for row in changed.patches}
        self.assertEqual(changed.runtime_used_size, self.build.runtime_used_size + 4)
        for name in (
            "router_pointer",
            "init_pointer",
            "initial_row_flush_pointer",
            "commit_pointer",
            "end_pointer_060312b4",
            "end_pointer_060328fc",
            "tab_draw_pointer",
            "occupation_cursor_pointer",
        ):
            before = struct.unpack(">I", self.patches[name].replacement)[0]
            after = struct.unpack(">I", changed_patches[name].replacement)[0]
            with self.subTest(pointer=name):
                self.assertEqual(after, before + 4)

    def test_unsupported_full_name_separator_fails_clearly(self) -> None:
        with patch.object(
            profile,
            "_full_name_storage",
            return_value="{first_name}☃{last_name}",
        ), self.assertRaisesRegex(ValueError, "unsupported FONT16.*translation"):
            profile.build_profile_entry_ui()

    def test_composed_base_guards_still_fail_closed(self) -> None:
        tampered = bytearray(profile._stock_source())
        offset = self.patches["occupation_count_value"].address - profile.LOAD_ADDRESS
        tampered[offset] ^= 0xFF
        with self.assertRaises(PatchError):
            profile.build_profile_entry_ui(bytes(tampered))


if __name__ == "__main__":
    unittest.main()
