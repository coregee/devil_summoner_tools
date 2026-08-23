from __future__ import annotations

import unittest

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.btl_mes import (
    build_btl_mes,
    encode_message,
    load_config,
    load_records,
)


PRESERVED_INDICES = (
    0,
    15,
    16,
    19,
    20,
    *range(33, 41),
    *range(45, 49),
    *range(122, 128),
    173,
    175,
    177,
    189,
    *range(192, 208),
    270,
    273,
)


class BtlMesTextTests(unittest.TestCase):
    def test_psp_binding_owns_every_translated_or_preserved_slot(self) -> None:
        config = load_config()
        records = load_records(config)
        self.assertEqual(len(records), 358)
        self.assertEqual(sum(record.translated for record in records), 313)
        self.assertEqual(
            tuple(record.index for record in records if not record.translated),
            PRESERVED_INDICES,
        )
        self.assertEqual(records[190].translation, "7_Shooting_Stars")
        self.assertEqual(
            sum(record.asset_identity is not None for record in records),
            329,
        )

    def test_codec_retains_the_native_fnt8x12_order_and_controls(self) -> None:
        self.assertEqual(
            encode_message("Dragon_ATM"),
            bytes.fromhex("0f 37 26 2c 34 32 41 0c 1f 18 80"),
        )
        self.assertEqual(
            encode_message("【{NUM}】{OP:a0}"),
            bytes.fromhex("45 a5 46 a0 80"),
        )
        self.assertEqual(encode_message("m"), bytes.fromhex("33 80"))
        self.assertEqual(encode_message("n"), bytes.fromhex("32 80"))

    def test_codec_rejects_unproved_glyphs_controls_and_overflow(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            encode_message("")
        with self.assertRaisesRegex(ValueError, "no verified FNT8X12 glyph"):
            encode_message("!")
        with self.assertRaisesRegex(ValueError, "operation.*glyph range"):
            encode_message("{OP:7f}")
        with self.assertRaisesRegex(ValueError, "operation.*not verified"):
            encode_message("{OP:a6}")
        with self.assertRaisesRegex(ValueError, "outside FNT8X12"):
            encode_message("{GLYPH:48}")
        with self.assertRaisesRegex(ValueError, "17/16 encoded cells"):
            encode_message("A" * 17)

    def test_private_source_reproduces_the_canonical_port_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source_iso = validate_source(disc, verify_hash=False)
        _extent, source = read_iso9660_file(
            source_iso,
            disc.entries["regdata"].path,
        )
        result = build_btl_mes(source)
        self.assertEqual(result.changed_member_indices, (18,))
        self.assertEqual(result.translated_record_count, 313)
        self.assertEqual(result.preserved_record_count, 45)
        self.assertEqual(result.body_size, 3_136)
        self.assertEqual(result.free_bytes, 922)
        self.assertEqual(
            result.output_member_sha256,
            "6d9cf516bbf0971b96bbf4b9ed54562f6108e27edcac1deffdb09fbee499630e",
        )
        self.assertEqual(
            result.output_sha256,
            "fb4a7f6aacca3243625c54b22bd1b520c38589afb19598d2974a0f5e8db0022c",
        )


if __name__ == "__main__":
    unittest.main()
