"""Behavior checks for terrain ownership and the native 3D field prompt.

The executable tests additionally use Unicorn when installed. They load the
actual PRX relocations and execute the retail queue/C998 path, rather than
replacing the renderer with a stub that would hide its glyph rejection gate.
"""

import struct
import unittest

from psp.engine import build
from psp.engine.core import layout
from psp.engine.core.storage import (
    validate_map_collision_data, validate_retired_name_owner, validate_retired_name_source,
)
from psp.engine.tests.support import map_ready_boot, name_ready_boot

try:
    import unicorn as uc
    from unicorn import mips_const as m
except ImportError:
    uc = None


class MapStorageTests(unittest.TestCase):
    def test_every_collision_cell_and_native_movement_instruction_is_preserved(self):
        stock, _, _ = build._source_entries()
        output = map_ready_boot()
        validate_map_collision_data(stock, output)
        self.assertEqual(output[0xA3100 + 128 : 0xA3330 + 128], stock[0xA3100 + 128 : 0xA3330 + 128])
        self.assertEqual((layout.MAP2D_COLLISION_TABLE_END_ADDRESS - layout.MAP2D_COLLISION_TABLE_ADDRESS) // 2, 9 * 35 * 35)
        # Inject an instruction into a formerly misidentified zero-filled cave.
        changed = bytearray(output)
        struct.pack_into('<I', changed, 0x17374C + 128, 0x27BDFFE0)
        with self.assertRaisesRegex(ValueError, 'collision tiles'):
            validate_map_collision_data(stock, bytes(changed))

    def test_reclaimed_storage_requires_retired_grid_and_labels(self):
        stock, _, _ = build._source_entries()
        validate_retired_name_source(stock)
        output = map_ready_boot()
        validate_retired_name_owner(output)
        with self.assertRaisesRegex(ValueError, 'single-page grid'):
            validate_retired_name_owner(stock)
        changed = bytearray(output)
        struct.pack_into('<II', changed, 0x1C6BDC + 128,
                         layout.NAME_RETIRED_STORAGE_ADDRESS - layout.DATA_LOAD_SEGMENT_ADDRESS, 4)
        with self.assertRaisesRegex(ValueError, 'label descriptors'):
            validate_retired_name_owner(bytes(changed))

    def test_map_builder_rejects_a_renderer_that_would_blank_the_field_prompt(self):
        stock, _, _ = build._source_entries()
        changed = bytearray(name_ready_boot())
        struct.pack_into('<I', changed, 0xC99C + 128, 0x28E2069D)
        with self.assertRaisesRegex(ValueError, 'FONT16 draw gate'):
            build.build_map2d(stock, bytes(changed), build._map2d_font_contract())


@unittest.skipIf(uc is None, 'install unicorn to run the native PSP execution checks')
class NativeMapTests(unittest.TestCase):
    def machine(self, base):
        data = map_ready_boot()
        machine = uc.Uc(uc.UC_ARCH_MIPS, uc.UC_MODE_MIPS32 | uc.UC_MODE_LITTLE_ENDIAN)
        machine.ctl_set_cpu_model(m.UC_CPU_MIPS32_74KF)
        machine.mem_map(base, 0x800000)
        # Both PT_LOAD segments are contiguous in this pinned executable.
        headers = [struct.unpack_from('<8I', data, 52 + i * 32) for i in range(2)]
        image = bytearray(max(h[2] + h[4] for h in headers))
        for _, offset, address, _, size, _, _, _ in headers:
            image[address:address + size] = data[offset:offset + size]
        for offset, size in ((0x1CD9E8, 0x68ED8), (0x236B28, 0x6180), (0x23CCA8, 0xC510)):
            pending = []
            for cursor in range(offset, offset + size, 8):
                address, info = struct.unpack_from('<II', data, cursor)
                kind = info & 255
                address += headers[(info >> 8) & 255][2]
                target = base + headers[(info >> 16) & 255][2]
                word = struct.unpack_from('<I', image, address)[0]
                if kind == 0:
                    continue
                if kind == 2:
                    word = (word + target) & 0xFFFFFFFF
                elif kind == 4:
                    word = (word & 0xFC000000) | (((((word & 0x3FFFFFF) << 2) + target) >> 2) & 0x3FFFFFF)
                elif kind == 5:
                    pending.append((address, word, target))
                    continue
                elif kind == 6:
                    low = word & 0xFFFF
                    low = low if low < 0x8000 else low - 0x10000
                    for high_address, high_word, high_target in pending:
                        high = (((high_word & 0xFFFF) << 16) + low + high_target + 0x8000) >> 16
                        struct.pack_into('<I', image, high_address, (high_word & 0xFFFF0000) | (high & 0xFFFF))
                    pending.clear()
                    word = (word & 0xFFFF0000) | ((low + target) & 0xFFFF)
                else:
                    self.fail(f'unsupported PRX relocation {kind}')
                struct.pack_into('<I', image, address, word)
            self.assertFalse(pending)
        machine.mem_write(base, bytes(image))
        machine.reg_write(m.UC_MIPS_REG_SP, base + 0x700000)
        return machine

    def call(self, machine, base, address, arguments):
        for index, value in enumerate(arguments):
            machine.reg_write(m.UC_MIPS_REG_A0 + index, value)
        end = base + 0x7F0000
        stack = machine.reg_read(m.UC_MIPS_REG_SP)
        machine.reg_write(m.UC_MIPS_REG_RA, end)
        machine.emu_start(base + address, end, count=100000)
        self.assertEqual(machine.reg_read(m.UC_MIPS_REG_PC), end)
        self.assertEqual(machine.reg_read(m.UC_MIPS_REG_SP), stack)

    def test_field_prompt_and_both_choice_highlights_reach_the_native_drawer(self):
        for base in (0x08800000, 0x08904000):
            for selection in (0, 1):
                with self.subTest(base=hex(base), selection=selection):
                    machine = self.machine(base)
                    self.call(machine, base, 0x2A39C, (base + 0x190824, 0))
                    self.call(machine, base, 0x15BCC, (base + 0x190808, base + 0x19080C, base + 0x190810, selection))
                    draws = []
                    def submit(machine, address, size, context):
                        if address == base + 0x6208:
                            pointer = machine.reg_read(m.UC_MIPS_REG_A0)
                            draws.append(struct.unpack('<6I', machine.mem_read(pointer, 24)))
                            machine.reg_write(m.UC_MIPS_REG_PC, machine.reg_read(m.UC_MIPS_REG_RA))
                    machine.hook_add(uc.UC_HOOK_CODE, submit)
                    machine.emu_start(base + 0x15698, base + 0x15724, count=100000)
                    self.assertEqual(machine.reg_read(m.UC_MIPS_REG_PC), base + 0x15724)
                    self.assertEqual(len(draws), 19)  # 14 prompt + 3 Yes + 2 No
                    self.assertTrue(all(draw[0] == 15 for draw in draws))  # FONT16 page 6

    def test_relocated_compendium_bridge_and_item_caller_preserve_the_stack(self):
        for base in (0x08800000, 0x08904000):
            machine = self.machine(base)
            glyphs = []
            def glyph(machine, address, size, context):
                if address == base + 0x9EEA8:
                    glyphs.append(machine.reg_read(m.UC_MIPS_REG_A2))
                    machine.reg_write(m.UC_MIPS_REG_PC, machine.reg_read(m.UC_MIPS_REG_RA))
            machine.hook_add(uc.UC_HOOK_CODE, glyph)
            self.call(machine, base, layout.ITEM_NAME_DRAW_WRAPPER_ADDRESS, (280, 32, 48))
            self.assertEqual(len(glyphs), len('Death Tally'))

    def test_relocated_dungeon_drawers_cover_every_location_and_transition_index(self):
        from psp.engine.surfaces.dungeon_locations import _font_plan
        records, _, _, _ = _font_plan(build._dungeon_location_font_contract())
        for base in (0x08800000, 0x08904000):
            machine = self.machine(base)
            draws = []
            def submit(machine, address, size, context):
                if address == base + 0x6208:
                    draws.append(machine.reg_read(m.UC_MIPS_REG_A0))
                    machine.reg_write(m.UC_MIPS_REG_PC, machine.reg_read(m.UC_MIPS_REG_RA))
            machine.hook_add(uc.UC_HOOK_CODE, submit)
            ids = machine.mem_read(base + layout.SAVEDATA_LOCATION_ID_TABLE_ADDRESS, 144)
            for physical, semantic in enumerate(ids):
                for index in range(5):
                    draws.clear()
                    machine.mem_write(base + layout.DUNGEON_LOCATION_STATE_ADDRESS, bytes([physical]))
                    machine.mem_write(base + layout.DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS, struct.pack('<H', physical))
                    machine.reg_write(m.UC_MIPS_REG_S0, index)
                    target = (layout.DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS if index == 0
                              else layout.DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS)
                    self.call(machine, base, target, (32, 200, 4, 1))
                    self.assertEqual(machine.reg_read(m.UC_MIPS_REG_S0), index)
                    self.assertEqual(len(draws), len(records[semantic]) if index < 2 else 0)


if __name__ == '__main__':
    unittest.main()
