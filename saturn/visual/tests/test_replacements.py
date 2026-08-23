from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

from PIL import Image


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from visual.util.paths import (  # noqa: E402
    IMAGE_CATALOG_PATH,
    IMAGE_ROOT,
    MANIFEST_ROOT,
)
from visual.util.replacements import load_replacements  # noqa: E402
from visual.util.workflow import changes, load_manifest  # noqa: E402


class ReplacementCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game = load_replacements("game")

    def test_game_bindings_cover_the_current_sparse_translation(self) -> None:
        self.assertEqual(len(self.game), 44)
        self.assertEqual(len({row.asset for row in self.game}), 44)
        self.assertEqual(len({row.view.casefold() for row in self.game}), 44)
        self.assertEqual(len({row.path for row in self.game}), 44)
        self.assertEqual(load_replacements("compendium"), ())

    def test_catalog_records_the_cross_platform_reuse_boundary(self) -> None:
        portability = {}
        for row in self.game:
            portability[row.portability] = portability.get(row.portability, 0) + 1
        self.assertEqual(
            portability,
            {
                "pixel_identical_saturn_psp": 39,
                "saturn_layout": 4,
                "shared_semantics_platform_layout": 1,
            },
        )

    def test_every_bound_image_exists_with_its_declared_dimensions(self) -> None:
        for row in self.game:
            self.assertTrue(row.path.is_relative_to(IMAGE_ROOT))
            with self.subTest(asset=row.asset), Image.open(row.path) as image:
                self.assertEqual(image.size, row.size)

    def test_catalog_does_not_store_duplicate_pixel_encodings(self) -> None:
        document = json.loads(IMAGE_CATALOG_PATH.read_text(encoding="utf-8"))
        catalog_paths = {
            IMAGE_ROOT.joinpath(*metadata["path"].split("/"))
            for metadata in document["images"].values()
        }
        actual_paths = set(IMAGE_ROOT.rglob("*.png"))
        self.assertEqual(actual_paths, catalog_paths)

        owners = {}
        for path in sorted(actual_paths):
            with Image.open(path) as image:
                pixels = image.convert("RGBA")
                fingerprint = (
                    pixels.size,
                    hashlib.sha256(pixels.tobytes()).hexdigest(),
                )
            self.assertNotIn(
                fingerprint, owners, f"duplicates {owners.get(fingerprint)}"
            )
            owners[fingerprint] = path

    def test_all_bound_images_are_active_manifest_changes(self) -> None:
        changed = changes("game", load_manifest("game"))
        self.assertEqual(len(changed), 44)
        self.assertEqual(sum(len(view.targets) for _row, view, _asset in changed), 56)
        self.assertEqual(
            len(
                {
                    target.source
                    for _row, view, _asset in changed
                    for target in view.targets
                }
            ),
            19,
        )

    def test_manifest_tree_contains_no_replacement_pngs(self) -> None:
        self.assertEqual(list(MANIFEST_ROOT.rglob("*.png")), [])


if __name__ == "__main__":
    unittest.main()
