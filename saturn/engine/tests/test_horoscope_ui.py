from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.horoscope_ui as horoscope  # noqa: E402


MATURE_HASH = "b51a5611e1095387c92baec2a5f8a8965eb47794cab0b774add3eb310f04b041"


class HoroscopeUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = horoscope.build_horoscope_ui()
        cls.config = horoscope._configuration()
        cls.runtime = horoscope._build_runtime()
        cls.patches = {row.name: row for row in cls.build.patches}

    def test_mature_output_and_typed_inventory_are_exact(self) -> None:
        self.assertEqual(len(self.build.data), horoscope.TARGET_SIZE)
        self.assertEqual(hashlib.sha256(self.build.data).hexdigest(), MATURE_HASH)
        self.assertEqual(len(self.build.patches), 10)
        self.assertEqual(
            [row.name for row in self.build.patches],
            [
                "message_pool",
                *(f"message_{index:02d}_pointer" for index in range(1, 9)),
                "reveal_scale",
            ],
        )
        self.assertEqual(
            [row.replacement.kind for row in self.config.patches[horoscope.TARGET]],
            ["generated", *("linked_pointer" for _ in range(8)), "instruction"],
        )
        self.assertEqual(self.patches["reveal_scale"].replacement.hex(), "4508")

    def test_default_pool_reproduces_every_mature_layout(self) -> None:
        self.assertEqual(self.build.runtime_used_size, 668)
        self.assertEqual(self.build.runtime_capacity, 1024)
        self.assertEqual(
            [len(self.runtime.layouts[f"message_{index:02d}"]) for index in range(1, 9)],
            [51, 35, 51, 49, 31, 31, 32, 54],
        )
        self.assertEqual(
            list(self.runtime.links.values()),
            [
                0x06020400,
                0x06020466,
                0x060204AC,
                0x06020512,
                0x06020574,
                0x060205B2,
                0x060205F0,
                0x06020630,
            ],
        )
        pool = self.patches["message_pool"].replacement
        self.assertEqual(len(pool), 1024)
        self.assertFalse(any(pool[668:]))
        for index, expected_lines in enumerate(
            ((18, 17, 13), (19, 14), (18, 18, 12), (19, 18, 9),
             (19, 10), (19, 10), (18, 12), (15, 20, 16)),
            start=1,
        ):
            layout = self.runtime.layouts[f"message_{index:02d}"]
            line_lengths: list[int] = []
            current = 0
            for code in layout:
                if code in (horoscope.NEWLINE, horoscope.TERMINATOR):
                    line_lengths.append(current)
                    current = 0
                else:
                    current += 1
            self.assertEqual(tuple(line_lengths), expected_lines)

    def test_authored_edit_relocates_following_links_inside_fixed_capacity(self) -> None:
        values = dict(horoscope._bound_messages())
        first_id = horoscope.MESSAGE_ROWS[0][1]
        values[first_id] = "A short first point."
        with patch.object(horoscope, "_bound_messages", return_value=values):
            edited = horoscope.build_horoscope_ui()
            runtime = horoscope._build_runtime()
        self.assertNotEqual(edited.data, self.build.data)
        self.assertLess(runtime.used_size, self.runtime.used_size)
        self.assertEqual(runtime.links["message_01"], horoscope.POOL_ADDRESS)
        self.assertLess(runtime.links["message_02"], self.runtime.links["message_02"])
        pointer = next(
            row for row in edited.patches if row.name == "message_02_pointer"
        )
        self.assertEqual(
            struct.unpack(">I", pointer.replacement)[0],
            runtime.links["message_02"],
        )

    def test_invalid_word_and_row_overflow_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "word wider than 20"):
            horoscope._layout_words(tuple(range(21)), 0x010B)
        values = dict(horoscope._bound_messages())
        values[horoscope.MESSAGE_ROWS[0][1]] = " ".join("a" for _ in range(40))
        with patch.object(horoscope, "_bound_messages", return_value=values), self.assertRaisesRegex(
            ValueError, "three 20-cell rows|reveal limit"
        ):
            horoscope._build_runtime()

    def test_config_drift_and_composed_base_are_rejected(self) -> None:
        config = self.config
        recipes = list(config.patches[horoscope.TARGET])
        recipes[1] = replace(recipes[1], address=recipes[1].address + 4)
        drifted = replace(config, patches={horoscope.TARGET: tuple(recipes)})
        with patch.object(horoscope, "load_patch_recipe_configuration", return_value=drifted), self.assertRaisesRegex(
            ValueError, "inventory drifted"
        ):
            horoscope._configuration()

        stock = bytearray(horoscope._stock_source())
        stock[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "stock target"):
            horoscope._validate_sources(config, bytes(stock))

    def test_manifest_inputs_are_complete_and_immutable(self) -> None:
        self.assertEqual(self.build.asset_files, horoscope.ASSET_FILES)
        self.assertEqual(self.build.assembly_files, ())
        self.assertEqual(
            set(self.build.runtime_input_files), set(horoscope.RUNTIME_INPUT_FILES)
        )
        self.assertEqual(
            dict(self.build.source_inputs),
            {f"game:{horoscope.TARGET}": horoscope._sha256(horoscope._stock_source())},
        )
        self.assertFalse(
            any("rom/extracted" in path.as_posix() for path in self.build.runtime_input_files)
        )


if __name__ == "__main__":
    unittest.main()
