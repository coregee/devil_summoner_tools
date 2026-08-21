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


EXPECTED_HASH = "9143d8961f1193aa23a8033f70c829214fa7a40e149e6467b335f23e7ad61f41"


class ProfileEntryUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = profile.build_profile_entry_ui()
        cls.patches = {row.name: row for row in cls.build.patches}

    def test_polished_profile_entry_output_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.build.data), 155208)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.build.patches), 22)
        self.assertEqual(
            tuple(dict.fromkeys(row.group for row in self.build.patches)),
            (
                "profile_entry.runtime",
                "profile_entry.templates",
                "profile_entry.occupation",
            ),
        )

    def test_confirmation_template_is_blank_for_the_proportional_runtime(self) -> None:
        confirm = self.patches["confirm_template"]
        words = struct.unpack(">20H", confirm.replacement)
        self.assertEqual(words, (0,) * 19 + (profile.ROW_TERMINATOR,))

    def test_runtime_arena_preserves_the_proven_default_layout(self) -> None:
        arena = self.patches["runtime_arena"]
        self.assertEqual(arena.address, profile.DATA_ADDRESS)
        self.assertEqual(len(arena.replacement), profile.RUNTIME_CAPACITY)
        self.assertEqual(self.build.runtime_used_size, 5376)
        self.assertEqual(self.build.runtime_capacity, 6840)
        self.assertEqual(
            hashlib.sha256(arena.replacement).hexdigest(),
            "419fc4026acf7d81560dd3d0dae8d22687ef5f9dd349203e428ec1348c6c4290",
        )
        self.assertEqual(
            hashlib.sha256(arena.replacement[:2636]).hexdigest(),
            "e1b54d820ae2b000d9465d81e0cd84da67041d20a09e702574e91ffe91cdb95f",
        )
        self.assertEqual(
            hashlib.sha256(arena.replacement[2636:5376]).hexdigest(),
            "10d962de9b5474205b39cbc883feb30b7b0ebd07431c074cefb139374cb964dd",
        )
        self.assertFalse(any(arena.replacement[5376:]))

    def test_centered_echo_clears_both_stock_row_state_and_pixel_canvas(self) -> None:
        controller = self.patches["runtime_arena"].replacement[2636:5376]
        self.assertIn(struct.pack(">I", 0x0602EE1C), controller)
        self.assertIn(struct.pack(">I", 0x0602F0E4), controller)

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

    def test_grids_use_the_named_ark_kanji_set_and_runtime_blitter(self) -> None:
        arena = self.patches["runtime_arena"].replacement
        codes, offsets = profile._kanji_maps()

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
        self.assertGreater(offsets["i"], offsets["W"])
        self.assertEqual(arena.count(struct.pack(">I", 0x0602F3F4)), 1)
        self.assertNotIn(struct.pack(">I", 0x0602F05C), arena)

    def test_three_glyph_no_edit_is_owned_by_the_proportional_confirm_data(self) -> None:
        original = profile._translation

        def edited(catalog, key: str) -> str:
            return "NO!" if key == "label_no" else original(catalog, key)

        with patch.object(profile, "_translation", side_effect=edited):
            changed = profile.build_profile_entry_ui()
        confirm = next(row for row in changed.patches if row.name == "confirm_template")
        words = struct.unpack(">20H", confirm.replacement)
        self.assertEqual(words, (0,) * 19 + (profile.ROW_TERMINATOR,))
        arena = next(row for row in changed.patches if row.name == "runtime_arena")
        self.assertIn(b"NO!\0", arena.replacement)

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
