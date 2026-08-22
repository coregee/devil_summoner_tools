from __future__ import annotations

import hashlib
import json
import struct
import unittest
from collections import Counter

from psp.engine.core.allegrex import AssemblyError, assemble
from psp.engine.core.patching import PatchError, apply_patches
from psp.engine.surfaces import title_help_ui


_WIDTHS = bytearray(range(1, title_help_ui.PACKED_WIDTH_COUNT + 1))
_WIDTHS[-1] = 4
WIDTHS = bytes(_WIDTHS)

EXPECTED_WRAPPER_WORDS = (
    0x03E0C021,
    0x04110001,
    0x00000000,
    0x27F90074,
    0x2CEF010C,
    0x11E00005,
    0x00000000,
    0x03277021,
    0x91CE0000,
    0x10000002,
    0x00000000,
    0x240E000F,
    0x022E8821,
    0x3C19FFEC,
    0x3739DD0C,
    0x033FC821,
    0x0300F821,
    0x03200008,
    0x00000000,
)


class TitleHelpUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = title_help_ui._configuration()
        cls.patches, cls.runtime = title_help_ui._build_patches(
            WIDTHS, cls.config
        )
        cls.by_name = {patch.name: patch for patch in cls.patches}

    def test_readable_runtime_is_byte_exact_to_the_proved_patch(self) -> None:
        self.assertEqual(
            struct.unpack("<19I", self.runtime.assembly.data),
            EXPECTED_WRAPPER_WORDS,
        )
        self.assertEqual(
            hashlib.sha256(self.runtime.assembly.data).hexdigest(),
            "bc49e9fa9a80ac597c8fe50d88e95ae008f8a4694b509d4fad6a8cf8fc4eb5ca",
        )
        self.assertEqual(
            self.runtime.assembly.labels,
            {
                "title_help_draw_wrapper": 0x0013EC80,
                "pc": 0x0013EC8C,
                "fallback": 0x0013ECAC,
                "advance": 0x0013ECB0,
            },
        )

    def test_two_calls_and_fixed_advance_edits_are_exact(self) -> None:
        expected_call = struct.pack("<I", 0x0C04FB20)
        self.assertEqual(self.by_name["menu_draw_call"].replacement, expected_call)
        self.assertEqual(
            self.by_name["difficulty_draw_call"].replacement,
            expected_call,
        )
        self.assertEqual(self.by_name["menu_fixed_advance"].replacement, bytes(4))
        self.assertEqual(
            self.by_name["difficulty_fixed_advance"].replacement,
            bytes(4),
        )

    def test_width_table_maps_only_title_font_owned_cells(self) -> None:
        table = self.runtime.width_table
        expected = bytearray(
            [title_help_ui.TITLE_HELP_STOCK_ADVANCE]
            * title_help_ui.TITLE_HELP_WIDTH_TABLE_SIZE
        )
        expected[0] = WIDTHS[94]
        for logical_code, storage_index in zip(
            range(1, 11), range(10), strict=True
        ):
            expected[logical_code] = WIDTHS[storage_index]
        for logical_code, storage_index in zip(
            range(11, 37), range(17, 43), strict=True
        ):
            expected[logical_code] = WIDTHS[storage_index]
        for logical_code, storage_index in zip(
            range(37, 63), range(49, 75), strict=True
        ):
            expected[logical_code] = WIDTHS[storage_index]
        expected[176] = WIDTHS[92]
        self.assertEqual(table, bytes(expected))
        self.assertEqual(table[0], 4)
        self.assertEqual(table[63], title_help_ui.TITLE_HELP_STOCK_ADVANCE)
        self.assertEqual(table[267], title_help_ui.TITLE_HELP_STOCK_ADVANCE)

    def test_version_two_recipe_uses_no_machine_code_blob(self) -> None:
        document = json.loads(
            title_help_ui.CONFIG_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(document["version"], 2)
        self.assertNotIn('"replacement"', title_help_ui.CONFIG_PATH.read_text())
        self.assertEqual(
            Counter(
                row.replacement.kind
                for row in self.config.patches[title_help_ui.TARGET]
            ),
            {
                "linked_call": 2,
                "instruction": 2,
                "assembly": 1,
                "generated": 1,
            },
        )
        self.assertEqual(
            {
                path.relative_to(title_help_ui.ASSEMBLY_ROOT).as_posix()
                for path in (
                    source
                    for row in self.config.patches[title_help_ui.TARGET]
                    for source in row.replacement.sources
                )
            },
            {"title_help_ui/draw_wrapper.s"},
        )

    def test_patch_application_is_transactional_and_uses_elf_bias(self) -> None:
        target = self.config.targets[title_help_ui.TARGET]
        size = max(
            patch.address + target.address_bias + len(patch.expected)
            for patch in self.patches
        )
        stock = bytearray(size)
        for patch in self.patches:
            start = patch.address + target.address_bias
            stock[start : start + len(patch.expected)] = patch.expected

        output = apply_patches(bytes(stock), target.address_bias, self.patches)
        for patch in self.patches:
            start = patch.address + target.address_bias
            self.assertEqual(
                output[start : start + len(patch.replacement)],
                patch.replacement,
            )

        tampered = bytearray(stock)
        first = self.patches[0]
        tampered[first.address + target.address_bias] ^= 0xFF
        with self.assertRaisesRegex(PatchError, "menu_draw_call did not match"):
            apply_patches(bytes(tampered), target.address_bias, self.patches)
        self.assertEqual(stock[first.address + target.address_bias], first.expected[0])

    def test_source_contract_includes_the_two_elf_relocations(self) -> None:
        guards = self.config.guards[title_help_ui.TARGET]
        self.assertEqual(
            [(row.name, row.file_offset, row.expected) for row in guards],
            [
                (
                    "menu_draw_relocation",
                    0x1D8960,
                    struct.pack("<II", 0x00013CC4, 4),
                ),
                (
                    "difficulty_draw_relocation",
                    0x1D8C28,
                    struct.pack("<II", 0x00013FC8, 4),
                ),
            ],
        )

    def test_runtime_bounds_and_width_validation_fail_closed(self) -> None:
        self.assertEqual(len(self.runtime.assembly.data), 76)
        self.assertEqual(len(self.runtime.width_table), 268)
        self.assertLessEqual(
            title_help_ui.TITLE_HELP_DRAW_WRAPPER_ADDRESS
            + len(self.runtime.assembly.data),
            title_help_ui.TITLE_HELP_WIDTH_TABLE_ADDRESS,
        )
        self.assertLessEqual(
            title_help_ui.TITLE_HELP_WIDTH_TABLE_ADDRESS
            + len(self.runtime.width_table),
            title_help_ui.CAVE_END_ADDRESS,
        )
        for invalid in (
            WIDTHS[:-1],
            (*WIDTHS[:-1], 0),
            (*WIDTHS[:-1], 256),
            (*WIDTHS[:-1], True),
        ):
            with self.subTest(value=invalid[-1] if invalid else None):
                with self.assertRaises(ValueError):
                    title_help_ui._build_runtime(invalid, self.config)
        with self.assertRaises(TypeError):
            title_help_ui._build_runtime(None, self.config)  # type: ignore[arg-type]

    def test_assembler_rejects_unknown_code_and_unsafe_delay_slots(self) -> None:
        with self.assertRaisesRegex(AssemblyError, "unsupported instruction"):
            assemble("mystery t0, t1", 0)
        with self.assertRaisesRegex(AssemblyError, "no delay slot"):
            assemble("jr ra", 0)
        with self.assertRaisesRegex(AssemblyError, "in a delay slot"):
            assemble("jr ra\nb somewhere\nsomewhere:\nnop", 0)

    def test_public_builder_rejects_nonstock_boot_bin(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 2404599"):
            title_help_ui.build_title_help_ui(bytes(64), WIDTHS)


if __name__ == "__main__":
    unittest.main()

