from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import IsoFileExtent, read_iso9660_file
from psp.rom.util.publication import (
    IsoReplacement,
    replaced_iso_sha256,
    verify_replaced_iso,
    write_replaced_iso,
)


class PspRomTests(unittest.TestCase):
    def test_catalog_declares_the_complete_ported_extent_set(self) -> None:
        disc = load_catalog()["game"]
        self.assertEqual(
            set(disc.entries),
            {"boot", "eboot", "datapack", "eve_files", "regdata", "start2_pmf"},
        )

    def test_atomic_publication_changes_only_declared_extents(self) -> None:
        source = bytearray((index % 251 for index in range(4096)))
        first = IsoReplacement(
            IsoFileExtent("FIRST.BIN", 0, 4),
            bytes(source[:4]),
            b"ABCD",
        )
        second_start = 2048
        second = IsoReplacement(
            IsoFileExtent("SECOND.BIN", 1, 5),
            bytes(source[second_start : second_start + 5]),
            b"12345",
        )
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            source_path = root / "source.iso"
            output_path = root / "output.iso"
            source_path.write_bytes(source)
            digest = replaced_iso_sha256(
                source_path,
                image_size=len(source),
                replacements=(second, first),
            )
            write_replaced_iso(
                source_path,
                output_path,
                image_size=len(source),
                replacements=(second, first),
                expected_sha256=digest,
            )
            verify_replaced_iso(
                source_path,
                output_path,
                image_size=len(source),
                replacements=(first, second),
                expected_sha256=digest,
            )
            output = output_path.read_bytes()
        self.assertEqual(output[:4], b"ABCD")
        self.assertEqual(output[second_start : second_start + 5], b"12345")
        self.assertEqual(output[4:second_start], source[4:second_start])

    def test_private_source_entries_match_the_catalog_when_available(self) -> None:
        disc = load_catalog()["game"]
        if not disc.source_path.is_file():
            self.skipTest("private PSP source ISO is unavailable")
        source = validate_source(disc, verify_hash=False)
        for contract in disc.entries.values():
            with self.subTest(entry=contract.id):
                extent, data = read_iso9660_file(source, contract.path)
                self.assertEqual(extent.size, contract.size)
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    contract.sha256,
                )


if __name__ == "__main__":
    unittest.main()
