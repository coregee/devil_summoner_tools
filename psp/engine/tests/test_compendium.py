from __future__ import annotations

import hashlib
import struct
import unittest
from dataclasses import replace

from psp.engine import build as engine_build
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

    def test_prose_emitter_matches_the_mature_patch(self) -> None:
        patch = self._prose()
        self.assertEqual(
            (patch.draw_wrapper.address, patch.draw_wrapper.end_address),
            (0x00176794, 0x001768A0),
        )
        self.assertEqual(
            hashlib.sha256(patch.draw_wrapper.data).hexdigest(),
            "8cac1f564f1aff6eb5f6dac15aba0d0d95c940730a830d213c4566452a49cb86",
        )
        self.assertEqual(
            tuple((write.name, write.address, len(write.data)) for write in patch.writes),
            (
                ("compendium_draw_wrapper", 0x00176794, 268),
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
            "995cb938f91e11e96fa9edcae5e17bd6a63f6ad60265423356f5ec5c1432b66d",
        )
        self.assertEqual(
            hashlib.sha256(patch.compare_wrapper.data).hexdigest(),
            "af2c5678fa838f32294a28bb3403ac09c95d007d5e9084a78a37db42702a44af",
        )
        self.assertEqual(
            patch.write("compendium_name_sort_block").data.hex(),
            "0800b396080092962120600221284002b0de050c0000000019004010000000000a00001000000000",
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
        result = build_compendium(stock, stock, load_eve_widths())
        self.assertEqual(len(result.patches), 12)
        self.assertEqual(result.text.used_size, 116_577)
        self.assertEqual(result.runtime_used_size, 125_830)
        self.assertEqual(result.runtime_capacity, 128_205)
        self.assertEqual(
            hashlib.sha256(result.data).hexdigest(),
            "dc2e9a1e801df2cd6440b174c9850bd6e383429695c65870947b4cb8cc9ee679",
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

