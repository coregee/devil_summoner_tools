from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from psp.rom.repack import _visual_replacements
from psp.rom.util.catalog import load_catalog
from psp.visual.util.workflow import (
    GENERATED_ROOT,
    MANIFEST_PATH,
    MAZE_BINDINGS_PATH,
    compose,
)


MATURE_OUTPUT_AGGREGATE = (
    "9dc56e9822c540588cf6b12f3d53366edee2ac7901024e643cbd1d909cc83962"
)


class PspVisualWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.disc = load_catalog()["game"]
        if not cls.disc.source_path.is_file():
            raise unittest.SkipTest("private PSP source ISO is unavailable")
        cls.files, cls.document = compose()

    def test_shared_asset_and_fanout_contracts(self) -> None:
        self.assertEqual(
            self.document["summary"],
            {
                "shared_assets": 40,
                "encoded_members": 18,
                "physical_bindings": 86,
            },
        )
        maze = json.loads(MAZE_BINDINGS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            (
                maze["asset_binding_count"],
                maze["logical_target_count"],
                maze["physical_binding_count"],
            ),
            (37, 45, 153),
        )

    def test_member_encodings_match_the_mature_project(self) -> None:
        digest = hashlib.sha256()
        for key, row in sorted(self.document["outputs"].items()):
            digest.update(key.encode("utf-8"))
            digest.update(bytes.fromhex(row["sha256"]))
        self.assertEqual(digest.hexdigest(), MATURE_OUTPUT_AGGREGATE)

    def test_generated_members_and_manifest_are_current(self) -> None:
        self.assertIn(MANIFEST_PATH, self.files)
        for path, expected in self.files.items():
            with self.subTest(path=path.relative_to(GENERATED_ROOT)):
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_bytes(), expected)

    def test_rom_composer_materializes_one_extent_per_target_pack(self) -> None:
        rows = _visual_replacements(self.disc.source_path, self.disc)
        self.assertEqual(len(rows), 84)
        self.assertEqual(len({row.extent.path.casefold() for row in rows}), 84)
        self.assertTrue(
            all(len(row.source_data) == len(row.replacement_data) for row in rows)
        )
        self.assertTrue(all(row.source_data != row.replacement_data for row in rows))


if __name__ == "__main__":
    unittest.main()
