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
        self.assertEqual((self.build.runtime_used_size, self.build.runtime_capacity), (1363, 1498))
        self.assertEqual(
            hashlib.sha256(b"".join(write.data for write in runtime.writes)).hexdigest(),
            "da58fb8173633b5f2d7e7c367b62852dbde814a8e07d0cecb1944e4cd3695a93",
        )
        self.assertEqual(len(runtime.maze_name_draw_wrapper.data), 320)
        self.assertEqual(len(runtime.floor_draw_wrapper.data), 180)
        self.assertEqual(len(runtime.transition_name_bridge.data), 112)
        self.assertEqual(len(runtime.name_descriptors), 48)
        self.assertEqual(len(runtime.name_sequence), 598)

    def test_transition_bridge_stages_the_current_physical_location(self) -> None:
        for load_base in (0x08800000, 0x08904000):
            for index in range(1, 5):
                with self.subTest(load_base=hex(load_base), index=index):
                    self._run_transition_bridge(index, load_base)

    def _run_transition_bridge(self, index: int, load_base: int) -> None:
        code = self.build.runtime.transition_name_bridge
        registers = [0] * 32
        caller = load_base + DUNGEON_LOCATION_TRANSITION_NAME_DRAW_CALL_ADDRESS + 8
        registers[emitter.RA] = caller
        registers[emitter.S0] = index  # the stock JAL delay slot already incremented it
        stack = 0x09F00000
        registers[emitter.SP] = stack
        physical_id = 137
        memory = {
            load_base + DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS: physical_id,
            load_base + DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS + 1: 0,
        }
        pc = load_base + code.address
        target = load_base + DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS
        pending = None
        calls = 0
        for _step in range(128):
            if pc == caller:
                break
            if pc == target:
                calls += 1
                self.assertEqual(registers[emitter.S0], 0)
                pc = registers[emitter.RA]
                continue
            offset = pc - load_base - code.address
            word = struct.unpack_from("<I", code.data, offset)[0]
            opcode = word >> 26
            rs = (word >> 21) & 31
            rt = (word >> 16) & 31
            rd = (word >> 11) & 31
            immediate = word & 0xFFFF
            signed = immediate if immediate < 0x8000 else immediate - 0x10000
            next_pc = pc + 4
            delayed = pending
            pending = None
            if word == 0:
                pass
            elif opcode == 0 and (word & 0x3F) == 0x21:
                registers[rd] = (registers[rs] + registers[rt]) & 0xFFFFFFFF
            elif opcode == 0 and (word & 0x3F) == 0x08:
                pending = registers[rs]
            elif opcode == 0 and (word & 0x3F) == 0x09:
                pending = registers[rs]
                registers[rd] = pc + 8
            elif opcode == 0x01 and rt == 0x11:
                registers[emitter.RA] = pc + 8
                pending = pc + 4 + (signed << 2)
            elif opcode == 0x05:
                if registers[rs] != registers[rt]:
                    pending = pc + 4 + (signed << 2)
            elif opcode == 0x09:
                registers[rt] = (registers[rs] + signed) & 0xFFFFFFFF
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
            elif opcode == 0x23:
                address = (registers[rs] + signed) & 0xFFFFFFFF
                registers[rt] = sum(memory[address + i] << (i * 8) for i in range(4))
            elif opcode == 0x2B:
                address = (registers[rs] + signed) & 0xFFFFFFFF
                for i in range(4):
                    memory[address + i] = (registers[rt] >> (i * 8)) & 0xFF
            else:
                self.fail(f"unsupported transition-bridge instruction {word:#x}")
            registers[0] = 0
            pc = (delayed if delayed is not None else next_pc) & 0xFFFFFFFF
        else:
            self.fail("transition bridge did not return to its caller")
        self.assertEqual(calls, int(index == 1))
        self.assertEqual(registers[emitter.RA], caller)
        self.assertEqual(registers[emitter.SP], stack)
        self.assertEqual(registers[emitter.S0], index)
        if index == 1:
            self.assertEqual(memory[load_base + DUNGEON_LOCATION_STATE_ADDRESS], physical_id)

    def test_shared_font_drawer_accepts_every_dungeon_glyph(self) -> None:
        # Exercise the actual C998 gate, rather than only pinning emitted bytes.
        word = struct.unpack_from("<I", self.build.data, 0xC99C + 0x80)[0]
        self.assertEqual(word >> 16, (0x0A << 10) | (emitter.A3 << 5) | emitter.V0)
        limit = word & 0xFFFF
        contract = engine_build._dungeon_location_font_contract()
        self.assertEqual(limit, contract["required_draw_code_limit"])
        for code in contract["owned_codes"]:
            with self.subTest(code=hex(code)):
                self.assertLess(code, limit)

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
