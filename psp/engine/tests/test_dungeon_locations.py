from __future__ import annotations

import hashlib
import struct
import unittest

from psp.engine import build as engine_build
from psp.engine.core import emitter
from psp.engine.core.layout import (
    DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS,
    DUNGEON_LOCATION_STATE_ADDRESS,
    DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS,
)
from psp.engine.surfaces.dungeon_locations import (
    DUNGEON_LOCATION_DRAW_CALL_CONTRACTS,
    DUNGEON_LOCATION_STAGE_CALL_CONTRACTS,
    build_dungeon_locations,
)
from psp.engine.surfaces.dungeon_locations_runtime import (
    DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS,
)


class DungeonLocationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stock, _eboot, _source = engine_build._source_entries()
        title = engine_build.build_title_help_ui(stock, engine_build._metric_widths())
        config = engine_build.build_config_menu(stock, title.data, engine_build._config_font_contract())
        command = engine_build.build_command_menu_help(stock, config.data)
        event = engine_build.build_event_window(stock, command.data, engine_build.load_eve_widths())
        name = engine_build.build_name_entry(stock, event.data)
        savedata = engine_build.build_savedata(stock, name.data)
        cls.stock = stock
        cls.savedata = savedata
        cls.build = build_dungeon_locations(
            stock, savedata.data, engine_build._dungeon_location_font_contract()
        )

    def test_runtime_extends_the_mature_patch_with_the_transition_surface(self) -> None:
        runtime = self.build.runtime
        self.assertEqual(len(runtime.writes), 21)
        self.assertEqual((self.build.runtime_used_size, self.build.runtime_capacity), (1323, 1498))
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest(),
            "bd7b360d9532bfeba5724d8c174a3b81c7e6e6999eee96f0df09bd656f0b884b",
        )
        self.assertEqual(len(runtime.maze_name_draw_wrapper.data), 320)
        self.assertEqual(len(runtime.floor_draw_wrapper.data), 180)
        self.assertEqual(len(runtime.transition_name_bridge.data), 72)
        self.assertEqual(len(runtime.name_descriptors), 48)
        self.assertEqual(len(runtime.name_sequence), 598)

    def test_transition_bridge_stages_the_current_physical_location(self) -> None:
        code = self.build.runtime.transition_name_bridge
        load_base = 0x08800000
        registers = [0] * 32
        caller = load_base + DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS + 8
        registers[emitter.RA] = caller
        physical_id = 137
        memory = {
            load_base + DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS: physical_id,
            load_base + DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS + 1: 0,
        }
        pc = load_base + code.address
        target = load_base + DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS
        for _step in range(64):
            if pc == target:
                break
            offset = pc - load_base - code.address
            word = struct.unpack_from("<I", code.data, offset)[0]
            opcode = word >> 26
            rs = (word >> 21) & 31
            rt = (word >> 16) & 31
            rd = (word >> 11) & 31
            immediate = word & 0xFFFF
            signed = immediate if immediate < 0x8000 else immediate - 0x10000
            next_pc = pc + 4
            if word == 0:
                pass
            elif opcode == 0 and (word & 0x3F) == 0x21:
                registers[rd] = (registers[rs] + registers[rt]) & 0xFFFFFFFF
            elif opcode == 0 and (word & 0x3F) == 0x08:
                next_pc = registers[rs]
            elif opcode == 0x01 and rt == 0x11:
                registers[emitter.RA] = pc + 8
                next_pc = pc + 4 + (signed << 2)
            elif opcode == 0x0D:
                registers[rt] = registers[rs] | immediate
            elif opcode == 0x0F:
                registers[rt] = immediate << 16
            elif opcode == 0x25:
                address = (registers[rs] + signed) & 0xFFFFFFFF
                registers[rt] = memory.get(address, 0) | memory.get(address + 1, 0) << 8
            elif opcode == 0x28:
                address = (registers[rs] + signed) & 0xFFFFFFFF
                memory[address] = registers[rt] & 0xFF
            else:
                self.fail(f"unsupported transition-bridge instruction {word:#x}")
            registers[0] = 0
            pc = next_pc & 0xFFFFFFFF
        else:
            self.fail("transition bridge did not reach the shared name wrapper")
        self.assertEqual(pc, target)
        self.assertEqual(registers[emitter.RA], caller)
        self.assertEqual(memory[load_base + DUNGEON_LOCATION_STATE_ADDRESS], physical_id)

    def test_calls_preserve_stock_delay_slots_and_relocations(self) -> None:
        for name, address, relocation_offset, sequence in (
            DUNGEON_LOCATION_DRAW_CALL_CONTRACTS + DUNGEON_LOCATION_STAGE_CALL_CONTRACTS
        ):
            write = self.build.runtime.write(name)
            self.assertEqual((write.address, len(write.data)), (address, 4))
            self.assertEqual(
                self.build.data[write.file_offset + 4 : write.file_offset + 8],
                sequence[4:8],
            )
            self.assertEqual(
                self.build.data[relocation_offset : relocation_offset + 8],
                address.to_bytes(4, "little") + (4).to_bytes(4, "little"),
            )

    def test_savedata_selector_dependency_is_explicit(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires the savedata selector"):
            build_dungeon_locations(
                self.stock,
                self.stock,
                engine_build._dungeon_location_font_contract(),
            )


if __name__ == "__main__":
    unittest.main()
