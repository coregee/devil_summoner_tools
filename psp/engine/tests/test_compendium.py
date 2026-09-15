from __future__ import annotations

import hashlib
import struct
import unittest
from dataclasses import replace

from psp.engine import build as engine_build
from psp.engine.tests.support import name_ready_boot
from psp.engine.surfaces.command_menu_help import load_eve_widths
from psp.engine.surfaces.compendium import build_compendium
from psp.engine.surfaces.compendium_name_runtime import (
    COMPENDIUM_NAME_OFFSET_TABLE_SIZE,
    CompendiumNamePatchSource,
    build_compendium_name_patch,
)
from psp.engine.surfaces.compendium_prose_runtime import (
    COMPENDIUM_LIVE_PROFILE_COUNT,
    COMPENDIUM_POINTER_RECORD_SIZE,
    COMPENDIUM_POINTER_TABLE_SIZE,
    COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
    COMPENDIUM_TEXT_ARENA_SIZE,
    CompendiumPatchSource,
    build_compendium_patch,
)
from psp.text.util.event_dvlname import build_psp_dvlname_runtime_table
from psp.text.util.event_packed import encode_ascii


class CompendiumRuntimeTests(unittest.TestCase):
    def _prose(self):
        arena = bytearray(COMPENDIUM_TEXT_ARENA_SIZE)
        arena[:2] = encode_ascii("A") + b"\0"
        table = bytearray(COMPENDIUM_POINTER_TABLE_SIZE)
        for row_index in range(COMPENDIUM_LIVE_PROFILE_COUNT):
            struct.pack_into(
                "<IIII",
                table,
                row_index * COMPENDIUM_POINTER_RECORD_SIZE,
                COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
                COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
                COMPENDIUM_TEXT_ARENA_RAW_ADDRESS,
                row_index,
            )
        return build_compendium_patch(
            CompendiumPatchSource(bytes(arena), bytes(table))
        )

    def test_prose_emitter_uses_the_retired_name_storage(self) -> None:
        patch = self._prose()
        self.assertEqual(
            (patch.draw_wrapper.address, patch.draw_wrapper.end_address),
            (0x001C7700, 0x001C780C),
        )
        self.assertEqual(
            hashlib.sha256(patch.draw_wrapper.data).hexdigest(),
            "16213cb14fd48ae809cbab6631836d2ebde05e5e10c8d0a89c1b43f58001da29",
        )
        self.assertEqual(
            tuple((write.name, write.address, len(write.data)) for write in patch.writes),
            (
                ("compendium_draw_bridge", 0x001726C0, 36),
                ("compendium_draw_wrapper", 0x001C7700, 268),
                ("compendium_origin_draw_call", 0x0008A88C, 4),
                ("compendium_summary_draw_call", 0x0008A8A4, 4),
                ("compendium_detail_draw_call", 0x0008A974, 4),
                ("compendium_text_arena", 0x001A0AD8, 0x1D028),
                ("compendium_pointer_table", 0x001BEB4C, 319 * 0x10),
            ),
        )

    def test_name_emitters_and_table_match_the_mature_patch(self) -> None:
        patch = build_compendium_name_patch(
            CompendiumNamePatchSource(
                build_psp_dvlname_runtime_table(),
                bytes([5] * 95),
            )
        )
        self.assertEqual(
            hashlib.sha256(patch.dvlname_table).hexdigest(),
            "73d099b8f2b182630c97405e8e22d8b9959415b1448b97b5ceeea1db7dcbe497",
        )
        self.assertEqual(
            hashlib.sha256(patch.draw_wrapper.data).hexdigest(),
            "07a1f1345bf76705fd5cc1695361389d4c587238e3ed5f1f9d22012b580ace41",
        )
        self.assertEqual(
            hashlib.sha256(patch.compare_wrapper.data).hexdigest(),
            "d43b7f4be0af900b2230c13017dd7c444bf4d5a7299259433822678c20f332cd",
        )
        self.assertEqual(
            patch.write("compendium_name_sort_block").data.hex(),
            "0800b396080092962120600221284002801e070c0000000019004010000000000a00001000000000",
        )
        changed = bytearray(patch.dvlname_table)
        changed[COMPENDIUM_NAME_OFFSET_TABLE_SIZE] = 2
        with self.assertRaisesRegex(ValueError, "unsupported byte"):
            build_compendium_name_patch(
                replace(
                    CompendiumNamePatchSource(patch.dvlname_table, bytes([5] * 95)),
                    dvlname_table=bytes(changed),
                )
            )

    def test_private_stock_build_is_exact_and_disjoint(self) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        result = build_compendium(stock, name_ready_boot(), load_eve_widths())
        self.assertEqual(len(result.patches), 13)
        self.assertEqual(result.text.used_size, 116_577)
        self.assertEqual(result.runtime_used_size, 125_866)
        self.assertEqual(result.runtime_capacity, 128_269)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "a824ce8f682afa87a44049e1a2a7b3bf80ca6eb9672c0743df289edee387145d",
        )
        ordered = sorted(result.patches, key=lambda patch: patch.address)
        self.assertTrue(
            all(
                left.address + len(left.replacement) <= right.address
                for left, right in zip(ordered, ordered[1:])
            )
        )
        self.assertEqual(
            result.prose.write("compendium_text_arena").end_address,
            result.names.write("compendium_name_table").address,
        )


if __name__ == "__main__":
    unittest.main()

