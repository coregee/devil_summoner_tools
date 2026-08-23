from __future__ import annotations

import hashlib
import struct
import unittest

from psp.archive.pack import PspPack
from psp.font.util.eve_ascii import build_eve_ascii, glyph_code
from psp.rom.util.catalog import load_catalog
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.combat_dialogue import (
    BOSSTALK_BINDING,
    COMBAT_COLOR_CODES,
    COMBAT_INSERT_CODES,
    COMBAT_STRUCTURAL_CODES,
    build_bosstalk_dialogue,
    combat_row_layout,
    combat_token_code,
    encode_combat_translation,
    load_combat_dialogue_contract,
    packed_control_codes,
    scan_ordinary_combat_references,
    wrap_combat_translation,
)
from psp.text.util.event_corpus import build_event_corpus


EXPECTED_POINTERS = (
    0,
    23,
    50,
    67,
    89,
    106,
    116,
    139,
    171,
    200,
    223,
    242,
    284,
    304,
    322,
    327,
    0,
)


class CombatDialogueCodecTests(unittest.TestCase):
    def test_contract_owns_only_the_16_canonical_bosstalk_messages(self) -> None:
        contract = load_combat_dialogue_contract()
        self.assertEqual(contract.bank.name, "BOSSTALK")
        self.assertEqual(contract.bank.member_index, 22)
        self.assertEqual(contract.bank.message_count, 16)
        self.assertEqual(len(contract.bank.assets), 16)
        self.assertEqual(len(set(contract.bank.assets)), 16)
        self.assertTrue(
            all(
                identity.startswith("battle/boss_dialogue.json#dialogue_")
                for identity in contract.bank.assets
            )
        )

    def test_codec_preserves_the_separate_combat_control_dialect(self) -> None:
        encoded = encode_combat_translation("A{BEAT}\nB{OP:8025}C{OP:8020}")
        self.assertEqual(encoded, bytes.fromhex("3080048001318025328020"))
        self.assertEqual(
            packed_control_codes(encoded),
            (0x8004, 0x8001, 0x8025, 0x8020),
        )
        self.assertEqual(COMBAT_STRUCTURAL_CODES, frozenset(range(0x8000, 0x8005)))
        self.assertEqual(COMBAT_INSERT_CODES, frozenset(range(0x8010, 0x8018)))
        self.assertEqual(COMBAT_COLOR_CODES, frozenset(range(0x8020, 0x8027)))
        with self.assertRaises(ValueError):
            combat_token_code("INS:8018")
        with self.assertRaises(ValueError):
            combat_token_code("OP:8027")

    def test_layout_enforces_the_common_event_geometry(self) -> None:
        self.assertEqual(
            combat_row_layout("A{INS:8010}B", lambda text: len(text) * 5),
            (90, 10),
        )
        self.assertEqual(
            wrap_combat_translation("one two three", lambda text: len(text) * 30),
            ("one two", "three"),
        )
        with self.assertRaisesRegex(ValueError, "capacity is 3"):
            wrap_combat_translation("one\ntwo\nthree\nfour", len)


class CombatDialoguePinnedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            raise unittest.SkipTest("private PSP source ISO is unavailable")
        contract = disc.entries["eve_files"]
        _extent, stock = read_iso9660_file(disc.source_path, contract.path)
        cls.font = build_eve_ascii(stock)
        widths = cls.font.advance_table

        def measure(text: str) -> int:
            return sum(widths[glyph_code(character) - 0x1E20] for character in text)

        cls.event = build_event_corpus(cls.font.data, measure_ascii=measure)
        cls.result = build_bosstalk_dialogue(
            cls.event.eve_files,
            measure_ascii=measure,
        )

    def test_member_and_composed_archive_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.result.bank.data).hexdigest(),
            "89cbe171a4006ce00cfab902e7404f85759545f403fe0e54b97cb01b30270a15",
        )
        self.assertEqual(
            hashlib.sha256(self.result.eve_files).hexdigest(),
            "71e43ab3ce3bad0d69e9b6ad68bdd49a16510df890e6999041df8ecd803fefe5",
        )
        self.assertEqual(self.result.changed_member_indices, (22,))
        self.assertEqual(self.result.changed_byte_count, 700)

    def test_pointer_body_and_script_ownership_are_exact(self) -> None:
        bank = self.result.bank
        self.assertEqual(
            struct.unpack_from(">17H", bank.data, BOSSTALK_BINDING.table_offset),
            EXPECTED_POINTERS,
        )
        self.assertEqual(bank.used_body_bytes, 0x029A)
        self.assertEqual(bank.body_capacity_bytes, 0xD000)
        self.assertEqual(bank.message_count, 16)
        self.assertEqual(len(bank.translated_record_ids), 16)
        references = scan_ordinary_combat_references(bank.data)
        self.assertEqual(tuple(row.message_index for row in references), tuple(range(16)))
        self.assertEqual(
            tuple(row.continuation_mode for row in references),
            (0x80, 0x83) * 8,
        )

    def test_composition_preserves_every_preceding_member(self) -> None:
        before = PspPack.parse(self.event.eve_files)
        after = PspPack.parse(self.result.eve_files)
        for source, rebuilt in zip(before.members, after.members, strict=True):
            with self.subTest(member=source.index):
                if source.index == 22:
                    self.assertNotEqual(source.data, rebuilt.data)
                else:
                    self.assertEqual(source.data, rebuilt.data)


if __name__ == "__main__":
    unittest.main()
