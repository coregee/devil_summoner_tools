from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.event_name_inserts as inserts  # noqa: E402
from engine.core.patching import PatchError  # noqa: E402
from engine.shared.player_names import PLAYER_NAME_FIELD_BY_KEY  # noqa: E402
from engine.surfaces.event_dialogue import (  # noqa: E402
    OUTPUT_PATH as EVENT_DIALOGUE_OUTPUT_PATH,
    build_event_dialogue,
    stock_event,
)
from engine.surfaces.fusion import build_fusion_menu  # noqa: E402


class EventNameInsertsEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = inserts._stock_source()
        cls.build = inserts.build_event_name_inserts(cls.stock)
        cls.patches = {row.name: row for row in cls.build.patches}

    def test_isolated_mature_adapter_is_reproduced_exactly(self) -> None:
        self.assertEqual(len(self.build.data), 354072)
        self.assertEqual(
            hashlib.sha256(self.build.data).hexdigest(),
            "64dfdf3f6ca203f9640a9c13baa01016f1f48a043c66d17d7cdc10c6a6ab2639",
        )
        self.assertEqual(len(self.build.patches), 15)
        self.assertEqual(self.build.runtime_used_size, 86)
        self.assertEqual(self.build.runtime_capacity, 96)

    def test_adapter_composes_after_the_current_fusion_base(self) -> None:
        dialogue = build_event_dialogue()[EVENT_DIALOGUE_OUTPUT_PATH]
        fusion = build_fusion_menu(stock_event(), dialogue).data
        self.assertEqual(
            hashlib.sha256(fusion).hexdigest(),
            "a60d61a03ee768836c75601b733873009007d8bdd2fb2308fefcc1423b81d1fd",
        )
        composed = inserts.build_event_name_inserts(fusion)
        self.assertEqual(
            hashlib.sha256(composed.data).hexdigest(),
            "5ab530a29f1656ef579971faa29d6a4c6e2173aad4e0c72bd99602018ac37867",
        )

    def test_exact_fifteen_recipe_inventory_is_readable(self) -> None:
        self.assertEqual(
            set(self.patches),
            {
                "first_insert_pointer",
                "first_terminator_stamp",
                "last_insert_pointer",
                "last_terminator_stamp",
                "city_insert_pointer",
                "city_terminator_stamp",
                "ward_insert_pointer",
                "ward_terminator_stamp",
                "codename_skip_copy",
                "codename_insert_pointer",
                "raw_menu_name_renderer",
                "raw_menu_first_insert_pointer",
                "raw_menu_last_insert_pointer",
                "raw_menu_name_result_06030c66",
                "raw_menu_name_result_06030c98",
            },
        )
        self.assertEqual(
            {
                path.relative_to(inserts.ENGINE_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "asm/shared/player_name_inserts/codename_skip.s",
                "asm/shared/player_name_inserts/raw_menu_inserts.s",
                "asm/shared/player_name_inserts/raw_menu_result.s",
            },
        )

    def test_renderer_uses_all_eight_cells_and_zero_pads_only_slack(self) -> None:
        renderer = self.patches["raw_menu_name_renderer"]
        self.assertEqual(renderer.address, inserts.RUNTIME_ADDRESS)
        self.assertEqual(len(renderer.replacement), inserts.RUNTIME_CAPACITY)
        self.assertEqual(
            hashlib.sha256(renderer.replacement).hexdigest(),
            "0b81b9fe8dcddc987c57a80fb3c65fa2e5facb0758b750bea7f230e2b880c87d",
        )
        self.assertEqual(renderer.replacement[inserts.RUNTIME_USED_SIZE :], bytes(10))
        self.assertIn(bytes.fromhex("eb08"), renderer.replacement[:86])

    def test_all_pointers_come_from_the_shared_player_name_abi(self) -> None:
        expected = {
            "first_insert_pointer": "first_name",
            "last_insert_pointer": "last_name",
            "city_insert_pointer": "city",
            "ward_insert_pointer": "ward",
            "codename_insert_pointer": "codename",
            "raw_menu_first_insert_pointer": "first_name",
            "raw_menu_last_insert_pointer": "last_name",
        }
        for patch_name, field_name in expected.items():
            with self.subTest(patch=patch_name):
                self.assertEqual(
                    struct.unpack(">I", self.patches[patch_name].replacement)[0],
                    PLAYER_NAME_FIELD_BY_KEY[field_name].runtime_address,
                )

    def test_runtime_and_source_provenance_are_complete(self) -> None:
        self.assertEqual(
            dict(self.build.source_inputs),
            {f"game:{inserts.TARGET}": hashlib.sha256(self.stock).hexdigest()},
        )
        self.assertEqual(
            set(self.build.runtime_input_files),
            {inserts.DISC_CONFIG_PATH, inserts.PLAYER_NAMES_PATH},
        )

    def test_composed_site_guards_fail_closed(self) -> None:
        tampered = bytearray(self.stock)
        site = self.patches["first_insert_pointer"]
        tampered[site.address - inserts.LOAD_ADDRESS] ^= 0xFF
        with self.assertRaises(PatchError):
            inserts.build_event_name_inserts(bytes(tampered))


if __name__ == "__main__":
    unittest.main()
