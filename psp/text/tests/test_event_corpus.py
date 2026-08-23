from __future__ import annotations

import hashlib
import json
import unittest

from psp.archive.pack import PspPack
from psp.font.util.eve_ascii import build_eve_ascii, glyph_code
from psp.rom.util.catalog import load_catalog
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import load_asset_field
from psp.text.util.event_corpus import (
    EVENT_BINDINGS,
    EVENT_BINDINGS_ROOT,
    build_event_corpus,
)
from psp.text.util.event_dvlname import build_psp_dvlname_runtime_table
from psp.text.util.event_packed import decode_ascii, encode_ascii


EXPECTED_BANKS = {
    "SHOPSMP": (816, 460, 572, 32320, "762eb5569435834585b94083108c856602a95521f5aa910a9737ef6690a8e1cc"),
    "EVFILE_0": (472, 472, 774, 50024, "b596a4a01e7da68b478d16da453a1f258ef234b96cb39f88b97937e7c137a876"),
    "EVFILE_1": (329, 327, 602, 43580, "64bdb9dc58ea8a64e0c8cdc6b5f4b878cb99464c831060ed264b738cd6892c21"),
    "MESFILE": (240, 240, 514, 45794, "c8b37e260848217d38dcb9a4f0e73bbf947cc58c15a9ec0a0151f34665a1d493"),
    "EVFILE_2": (90, 82, 170, 10222, "343b71fb0efe2ad7256070e7917e5e5abac8e8656816954cc890aad7c0099d39"),
}


class EventCorpusContractsTests(unittest.TestCase):
    def test_packed_ascii_round_trips_the_complete_authored_alphabet(self) -> None:
        text = "".join(chr(code) for code in range(0x20, 0x7F))
        self.assertEqual(decode_ascii(encode_ascii(text)), text)

    def test_compact_bindings_resolve_every_canonical_page(self) -> None:
        page_count = 0
        native_count = 0
        identities = set()
        for binding in EVENT_BINDINGS:
            path = EVENT_BINDINGS_ROOT / f"{binding.name}.EVE.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["bank"], binding.name)
            self.assertEqual(document["member_index"], binding.member_index)
            self.assertEqual(document["message_count"], binding.expected_messages)
            self.assertEqual(len(document["assets"]), binding.expected_messages)
            for row in document["assets"]:
                for identity in row:
                    page_count += 1
                    if identity is None:
                        native_count += 1
                    else:
                        identities.add(identity)
        for identity in identities:
            reference, translation = load_asset_field(identity)
            self.assertTrue(reference, identity)
            self.assertTrue(translation, identity)
        self.assertEqual(page_count, 2838)
        self.assertEqual(native_count, 8)
        self.assertEqual(len(identities), 2559)

    def test_dvlname_runtime_table_matches_the_mature_port(self) -> None:
        table = build_psp_dvlname_runtime_table()
        self.assertEqual(len(table), 3205)
        self.assertEqual(
            hashlib.sha256(table).hexdigest(),
            "73d099b8f2b182630c97405e8e22d8b9959415b1448b97b5ceeea1db7dcbe497",
        )


class EventCorpusPinnedSourceTests(unittest.TestCase):
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

        cls.result = build_event_corpus(cls.font.data, measure_ascii=measure)

    def test_all_five_members_rebuild_transactionally(self) -> None:
        self.assertEqual(self.result.changed_member_indices, (0, 1, 2, 3, 4))
        self.assertEqual(
            hashlib.sha256(self.result.eve_files).hexdigest(),
            "dcecdf12a20bff77277b22dbc46f9f6f0466b06c56d8acf7d0bb92408e4d5458",
        )
        source_archive = PspPack.parse(self.font.data)
        output_archive = PspPack.parse(self.result.eve_files)
        self.assertEqual(source_archive.members[5].data, output_archive.members[5].data)

    def test_bank_scope_and_hashes_are_exact(self) -> None:
        self.assertEqual(len(self.result.translated_record_ids), 2369)
        self.assertEqual(len(self.result.preserved_record_ids), 190)
        for bank in self.result.banks:
            with self.subTest(bank=bank.name):
                expected = EXPECTED_BANKS[bank.name]
                self.assertEqual(
                    (
                        bank.message_count,
                        bank.translated_message_count,
                        len(bank.translated_record_ids),
                        bank.used_body_bytes,
                        hashlib.sha256(bank.data).hexdigest(),
                    ),
                    expected,
                )
                self.assertEqual(bank.body_capacity_bytes, 0xD000)
                self.assertEqual(bank.dvlname_table_size, 3205)


if __name__ == "__main__":
    unittest.main()
