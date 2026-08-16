from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402


KAI_CATALOG_SHA256 = (
    "48eb224fbd6cccbdcb182099485116c4c92b3f85c4f0d44fb92039e1593ffd6a"
)


class LocationMirrorAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("locations.json")
        cls.binding = load_binding(BINDING_ROOT / "location_mirrors.json")
        cls.physical = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "dungeon_location_mirrors.json"
            ).read_text(encoding="utf-8")
        )
        cls.manifest = load_manifest(manifest_path("game"))
        cls.source = next(
            source
            for source in cls.manifest.sources
            if source.name == "dungeon_location_mirrors"
        )

    def test_all_288_mirror_uses_bind_to_existing_location_assets(self) -> None:
        physical_ids = {row["id"] for row in self.physical}
        self.assertEqual(len(physical_ids), 288)
        self.assertEqual(set(self.binding.records), physical_ids)
        self.assertEqual(len(set(self.binding.records.values())), 14)
        self.assertTrue(
            set(self.binding.records.values())
            <= {
                f"{key}.name"
                for key in self.catalog.entries
                if "name" in self.catalog.entries[key].fields
            }
        )
        for row in self.physical:
            with self.subTest(record=row["id"]):
                asset = self.catalog.field(self.binding.records[row["id"]])
                self.assertEqual(asset.reference, row["reference"])

    def test_inventory_keeps_every_elv_and_kai_use_physically_distinct(self) -> None:
        tables = self.source.container["tables"]
        elv = [table for table in tables if "elv" in table["name"]]
        kai = [table for table in tables if "kai" in table["name"]]
        self.assertEqual((len(elv), sum(table["count"] for table in elv)), (17, 56))
        self.assertEqual((len(kai), sum(table["count"] for table in kai)), (98, 232))
        self.assertEqual(len(tables), 115)
        self.assertEqual(
            {row["id"] for row in self.physical},
            {
                f"game.dungeon_location_mirrors.{table['name']}.r{index:04d}"
                for table in tables
                for index in range(table["count"])
            },
        )

    def test_offsets_and_full_file_identities_are_fail_closed(self) -> None:
        files = self.manifest.files
        for table in self.source.container["tables"]:
            with self.subTest(table=table["name"]):
                self.assertFalse(table["require_identical_bytes"])
                self.assertEqual(table["framing"], {"type": "none"})
                self.assertEqual(len(table["locations"]), 1)
                location = table["locations"][0]
                file = files[location["file"]]
                self.assertEqual(file.path.parent, PurePosixPath("MAZEDATA"))
                self.assertIsNotNone(file.owned_sha256)
                self.assertEqual(location["units"], 5)
                if "elv" in table["name"]:
                    self.assertEqual(
                        (location["base"], location["stride"]),
                        ("0x5e", "0x20"),
                    )
                else:
                    self.assertEqual(
                        (location["base"], location["stride"]),
                        ("0x12", "0x28"),
                    )

        kai_catalog = hashlib.sha256()
        for table in sorted(
            (table for table in self.source.container["tables"] if "kai" in table["name"]),
            key=lambda table: files[table["locations"][0]["file"]].path.name,
        ):
            file = files[table["locations"][0]["file"]]
            kai_catalog.update(file.path.name.encode("ascii"))
            kai_catalog.update(b"\0")
            kai_catalog.update(bytes.fromhex(file.stock_sha256))
        self.assertEqual(kai_catalog.hexdigest(), KAI_CATALOG_SHA256)
        self.assertFalse(
            any(file.path.name == "ELV00.BIN" for file in files.values())
        )


if __name__ == "__main__":
    unittest.main()
