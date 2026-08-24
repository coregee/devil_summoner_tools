from __future__ import annotations

import unittest

from psp.text.util.map2d import load_map2d_text


class Map2dTextTests(unittest.TestCase):
    def test_shared_catalogues_form_the_complete_static_contract(self) -> None:
        text = load_map2d_text()
        self.assertEqual(
            text.locations,
            (
                "Rinkai Park",
                "Mt. Kasagi",
                "Yarai Ward",
                "Chuo Ward",
                "Hibarigaoka",
            ),
        )
        self.assertEqual(
            text.runtime_records,
            ("> Someone is here. Talk to them?", "Yes", "No"),
        )


if __name__ == "__main__":
    unittest.main()
