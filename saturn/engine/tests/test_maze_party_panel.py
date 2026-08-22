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

from engine.build import (  # noqa: E402
    FIELD_MESSAGES_OUTPUT_PATH,
    build_field_messages_surface,
)
import engine.shared.party_panel as shared_panel  # noqa: E402
import engine.surfaces.field_messages as field_messages  # noqa: E402
import engine.surfaces.maze_party_panel as maze_panel  # noqa: E402


OUTPUT_HASH = "c45b897557852679a855b8c4e01c627fd2531d8b5be07072bb49de5a0ff2e5e1"


class MazePartyPanelEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = build_field_messages_surface()[FIELD_MESSAGES_OUTPUT_PATH]
        cls.build = maze_panel.build_maze_party_panel(cls.base)
        cls.patches = {patch.name: patch for patch in cls.build.patches}

    def test_exact_five_site_inventory_and_mature_runtime_bytes(self) -> None:
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), OUTPUT_HASH)
        self.assertEqual(
            [patch.name for patch in self.build.patches],
            [
                "renderer_cave",
                "compact_name_cave",
                "panel_pointer_0603f364",
                "panel_pointer_0603f660",
                "panel_pointer_0603f8e4",
            ],
        )
        self.assertEqual(
            hashlib.sha256(
                self.patches["renderer_cave"].replacement[:574]
            ).hexdigest(),
            "067c866fa6e4db778b663a23d23b5dfdf10a75dce4ffe61f08fb5cd76f947767",
        )
        self.assertEqual(
            hashlib.sha256(
                self.patches["compact_name_cave"].replacement[:1464]
            ).hexdigest(),
            "3bc1f4843e9ada102536a474801cacebf155778c5bdb094e21051ab9ccfbc540",
        )
        for address in maze_panel.PANEL_POINTERS:
            self.assertEqual(
                self.patches[f"panel_pointer_{address:08x}"].replacement,
                struct.pack(">I", 0x06023BE8),
            )

    def test_runtime_owns_full_disjoint_caves_and_reports_actual_use(self) -> None:
        self.assertEqual(self.build.runtime_used_size, 2038)
        self.assertEqual(self.build.runtime_capacity, 3072)
        self.assertEqual(
            [
                (arena.address, arena.used_size, arena.capacity)
                for arena in self.build.runtime_arenas
            ],
            [(0x06022800, 574, 1024), (0x06023800, 1464, 2048)],
        )
        self.assertFalse(any(self.patches["renderer_cave"].replacement[574:]))
        self.assertFalse(any(self.patches["compact_name_cave"].replacement[1464:]))
        self.assertEqual(0x06022800 + 1024, 0x06022C00)
        self.assertEqual(field_messages.CAVE_LIMIT, 0x06023800)

    def test_asset_edit_relocates_the_drawer_and_all_three_links(self) -> None:
        real_loader = shared_panel.load_bound_translations

        def edited(prefixes, **kwargs):
            values = dict(real_loader(prefixes, **kwargs))
            if "game.charname." in prefixes:
                values["game.charname.o000008.text"] = "Rei Alexandra"
            return values

        with patch.object(
            shared_panel, "load_bound_translations", side_effect=edited
        ):
            result = maze_panel.build_maze_party_panel(self.base)
        self.assertNotEqual(result.data, self.build.data)
        self.assertGreater(result.runtime_arenas[1].used_size, 1464)
        pointers = {
            patch.replacement
            for patch in result.patches
            if patch.name.startswith("panel_pointer_")
        }
        self.assertEqual(len(pointers), 1)
        self.assertGreater(struct.unpack(">I", pointers.pop())[0], 0x06023BE8)

    def test_provenance_names_shared_assets_and_readable_assembly(self) -> None:
        self.assertEqual(
            {path.name for path in self.build.asset_files},
            {"characters.json", "demons.json"},
        )
        self.assertEqual(
            {
                path.relative_to(maze_panel.ASSEMBLY_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "font8_pixel_blitter.s",
                "font8_fixed_name.s",
                "comp_menu/party_panel.s",
            },
        )
        self.assertEqual(
            set(self.build.source_inputs),
            {"game:MAZE.BIN", "composed:MAZE.BIN"},
        )


if __name__ == "__main__":
    unittest.main()
