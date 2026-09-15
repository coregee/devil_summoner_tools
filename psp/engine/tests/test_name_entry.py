from __future__ import annotations

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psp.engine import build as engine_build
from psp.engine.surfaces import name_entry
from psp.engine.surfaces.name_entry import build_name_entry
from psp.engine.surfaces.name_entry_runtime import (
    NAME_BUFFER_DRAW_WRAPPER_ADDRESS,
    NAME_FIELD_LIMITS,
    NAME_GRID_DONE,
    NAME_GRID_OFFSET_TABLE_ADDRESS,
    NAME_GRID_SENTINEL,
    NAME_LABEL_BLOB_ADDRESS,
    NAME_LABEL_DRAW_CALL_ADDRESS,
    NAME_PROFILE_FIELD_OFFSETS,
)
from psp.font.util.name_entry import name_grid_glyph
from psp.text.util.name_entry import load_name_entry_text


class NameGridMetricContractTests(unittest.TestCase):
    def test_corrupt_font_metrics_are_rejected_before_runtime_compilation(self) -> None:
        text = load_name_entry_text()
        document = json.loads(name_entry.FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
        mutations = {
            "missing character": lambda rows: rows.pop(),
            "duplicate character": lambda rows: rows.append(copy.deepcopy(rows[0])),
            "wrong glyph": lambda rows: rows[0].update(code=0),
            "invalid bounds": lambda rows: rows[0].update(bounds=[0, 0, 17, 16]),
            "inconsistent offset": lambda rows: rows[0].update(
                x_offset=(rows[0]["x_offset"] + 1) % 16
            ),
            "boolean offset": lambda rows: rows[0].update(x_offset=True),
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "psp.fonts.json"
            with patch.object(name_entry, "FONT_MANIFEST_PATH", manifest):
                for description, mutate in mutations.items():
                    with self.subTest(description=description):
                        changed = copy.deepcopy(document)
                        mutate(changed["name_entry"]["grid_metrics"])
                        manifest.write_text(json.dumps(changed), encoding="utf-8")
                        with self.assertRaises(ValueError):
                            name_entry._name_grid_offsets(text)


class NameEntryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(stock, title.data, engine_build._config_font_contract())
        command = engine_build.build_command_menu_help(stock, config.data)
        event = engine_build.build_event_window(stock, command.data, engine_build.load_eve_widths())
        cls.stock = stock
        cls.event = event
        cls.build = build_name_entry(stock, event.data)

    def test_runtime_matches_the_polished_patch(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.writes), 142)
        self.assertEqual(self.build.runtime_used_size, 3697)
        self.assertEqual(self.build.runtime_capacity, 3936)
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest(),
            "139ad604b349771e03e3fc4478bbdcf6462cc0f78315f601c2fa7cdff55bd9c2",
        )
        self.assertEqual(
            hashlib.sha256(runtime.label_draw_wrapper.data).hexdigest(),
            "7c00aabdef6065bf3f3fe40809e3d201aad476b0b3d55541af0042a992380a29",
        )

    def test_cursor_and_character_grid_drawers_are_centered(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(
            runtime.write("name_buffer_draw_wrapper").address,
            NAME_BUFFER_DRAW_WRAPPER_ADDRESS,
        )
        self.assertEqual(len(runtime.write("name_buffer_draw_wrapper").data), 200)
        self.assertEqual(len(runtime.write("name_grid_draw_wrapper").data), 72)
        blob = runtime.write("name_label_blob").data
        offset = NAME_GRID_OFFSET_TABLE_ADDRESS - NAME_LABEL_BLOB_ADDRESS
        table = blob[offset : offset + 0x116]
        self.assertEqual(table[name_grid_glyph("A")], 1)
        self.assertEqual(table[name_grid_glyph("i")], 0)
        self.assertEqual(table[name_grid_glyph("W")], 1)
        self.assertEqual(table[name_grid_glyph("'")], 5)
        self.assertEqual(table[name_grid_glyph(".")], 6)

    def test_five_fields_and_native_grid_geometry_are_exact(self) -> None:
        self.assertEqual(NAME_FIELD_LIMITS, (8, 8, 8, 8, 8))
        self.assertEqual(
            NAME_PROFILE_FIELD_OFFSETS,
            {"first": 0, "last": 8, "codename": 16, "city": 24, "ward": 32},
        )
        cells = struct.unpack("<152H", self.build.runtime.write("name_grid_upper_primary").data)
        self.assertEqual(cells[:19], (NAME_GRID_SENTINEL,) * 19)
        self.assertEqual(cells[4 * 19 + 15], NAME_GRID_DONE)
        self.assertEqual(
            self.build.runtime.write("name_grid_upper_primary").data,
            self.build.runtime.write("name_grid_upper_secondary").data,
        )

    def test_event_dependency_and_stock_source_are_guarded(self) -> None:
        with self.assertRaisesRegex(ValueError, "EVENT runtime foundation"):
            build_name_entry(self.stock, self.stock)
        changed = bytearray(self.stock)
        changed[NAME_LABEL_DRAW_CALL_ADDRESS + 0x80] ^= 1
        with self.assertRaisesRegex(ValueError, "BOOT source contract changed"):
            build_name_entry(bytes(changed), self.event.data)

    def test_new_draw_hooks_preserve_delay_slots_and_guard_relocations(self) -> None:
        for address in (0x0009E478, 0x0009E948):
            with self.subTest(address=hex(address)):
                delay = name_entry.file_offset(address + 4)
                self.assertEqual(self.build.data[delay : delay + 4], self.stock[delay : delay + 4])
                _, offset, expected = next(
                    row for row in name_entry.NAME_ENTRY_RELOCATION_CONTRACTS
                    if row[0] == address
                )
                self.assertEqual(self.build.data[offset : offset + len(expected)], expected)
                changed = bytearray(self.stock)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, "JAL relocation changed"):
                    name_entry.validate_source_elf(bytes(changed))


if __name__ == "__main__":
    unittest.main()
