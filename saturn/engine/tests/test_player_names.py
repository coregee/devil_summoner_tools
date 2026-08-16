from __future__ import annotations

import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.shared.player_names import (  # noqa: E402
    CODENAME_BYTES,
    FONT16_ROW_STRIDE,
    NAME_FW,
    NAME_FW_FULL,
    PLAYER_NAME_FIELDS,
    byte_to_advance_table,
    byte_to_font16_table,
    byte_to_font8_table,
)


class PlayerNameContractTests(unittest.TestCase):
    def test_wram_contract_matches_the_save_and_name_consumers(self) -> None:
        self.assertEqual(NAME_FW, 0x0023FDF0)
        self.assertEqual(NAME_FW_FULL, 0x0023FE50)
        self.assertEqual(CODENAME_BYTES, 0x0023FFD0)
        self.assertEqual(
            tuple((row.key, row.stage_address) for row in PLAYER_NAME_FIELDS),
            (
                ("first_name", 0x002029E0),
                ("last_name", 0x002029E8),
                ("codename", 0x002029D8),
                ("city", 0x002029F0),
                ("ward", 0x002029F8),
            ),
        )
        self.assertEqual(
            tuple(row.runtime_address for row in PLAYER_NAME_FIELDS),
            tuple(NAME_FW + index * FONT16_ROW_STRIDE for index in range(5)),
        )

    def test_complete_byte_tables_have_safe_fallbacks(self) -> None:
        font16 = {" ": 4, "?": 7, "A": 9}
        advances = {" ": 3, "?": 6, "A": 8}
        font8 = {"?": 11, "A": 13}
        wide = byte_to_font16_table(font16)
        widths = byte_to_advance_table(advances)
        narrow = byte_to_font8_table(font8)

        self.assertEqual((len(wide), len(widths), len(narrow)), (256, 256, 256))
        self.assertEqual((wide[0], widths[0], narrow[0]), (4, 0, 0))
        self.assertEqual((wide[ord("A")], widths[ord("A")], narrow[ord("A")]), (9, 8, 13))
        self.assertEqual((wide[0x80], widths[0x80], narrow[0x80]), (7, 6, 11))


if __name__ == "__main__":
    unittest.main()
