from __future__ import annotations

import unittest

from psp.archive.pack import PspPack
from psp.engine import build as engine_build
from psp.text.util.item_runtime import ITEM_RUNTIME_GAME_IDS, load_item_runtime_text


class ItemRuntimeTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.member = PspPack.parse(engine_build._source_regdata()).members[4].data
        cls.source = load_item_runtime_text(cls.member)

    def test_three_psp_authored_rows_are_source_pinned(self) -> None:
        self.assertEqual(tuple(record.game_id for record in self.source.records), ITEM_RUNTIME_GAME_IDS)
        self.assertEqual(
            tuple((record.name, record.description) for record in self.source.records),
            (
                ("Back-Upper R", "Special item: Field\nSave anywhere; reusable."),
                ("Death Tally", "Reduces Demon Compendium summoning costs."),
                ("Demon Compendium Extra Volume", "A supplement listing demons absent from the main Compendium."),
            ),
        )
        self.assertEqual(self.source.records[2].post_terminator_tail, "Its demons cannot be summoned.")
        self.assertEqual(self.source.source_member_sha256, "d8f599b6a739eb5367ea4ad1107bc325641dc1d0164bad89034cef948bb75f96")

    def test_changed_native_row_fails_closed(self) -> None:
        changed = bytearray(self.member)
        changed[(255 - 1) * 104 + 4] ^= 1
        with self.assertRaisesRegex(ValueError, "ITEMNAME member changed"):
            load_item_runtime_text(bytes(changed))


if __name__ == "__main__":
    unittest.main()
