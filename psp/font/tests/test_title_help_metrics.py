from __future__ import annotations

import hashlib
import unittest

from psp.font.util.metrics import build_title_help_metrics, metric_bytes


class TitleHelpMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = build_title_help_metrics()
        cls.by_character = {
            row["character"]: row for row in cls.document["glyphs"]
        }

    def test_generated_metrics_are_deterministic(self) -> None:
        self.assertEqual(
            hashlib.sha256(metric_bytes(self.document)).hexdigest(),
            "f97675c7c7f06b66ee14132caf2a8d55cefaa0da41ca04506d9e5ee7e0505a1c",
        )
        self.assertEqual(len(self.document["storage_order"]), 95)
        self.assertEqual(len(self.document["glyphs"]), 95)

    def test_title_owned_glyphs_match_the_proved_psp_raster(self) -> None:
        expected = {
            " ": (4, None),
            "C": (7, [0, 4, 6, 13]),
            "D": (7, [0, 4, 6, 13]),
            "F": (7, [0, 4, 6, 13]),
            "R": (7, [0, 4, 6, 13]),
            "S": (7, [0, 4, 6, 13]),
            "V": (8, [0, 4, 7, 13]),
            "a": (6, [0, 7, 5, 13]),
            "f": (5, [0, 4, 4, 13]),
            "i": (4, [0, 4, 3, 13]),
            "m": (8, [0, 7, 7, 13]),
            "r": (5, [0, 7, 4, 13]),
            "w": (8, [0, 7, 7, 13]),
            ".": (2, [0, 12, 1, 13]),
        }
        for character, (advance, bounds) in expected.items():
            with self.subTest(character=character):
                row = self.by_character[character]
                self.assertEqual(row["advance"], advance)
                self.assertEqual(row["title_raster_advance"], advance)
                self.assertTrue(row["owned"])
                self.assertEqual(row["bounds"], bounds)

    def test_storage_indices_are_a_complete_permutation(self) -> None:
        indices = [row["storage_index"] for row in self.document["glyphs"]]
        self.assertEqual(sorted(indices), list(range(95)))
        for row in self.document["glyphs"]:
            self.assertEqual(
                self.document["storage_order"][row["storage_index"]],
                row["advance"],
            )


if __name__ == "__main__":
    unittest.main()
