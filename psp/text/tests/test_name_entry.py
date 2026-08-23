from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from psp.text.util.name_entry import ASSET_PATH, CONFIG_PATH, load_name_entry_text


class NameEntryTextTests(unittest.TestCase):
    def test_canonical_profile_asset_forms_the_psp_contract(self) -> None:
        text = load_name_entry_text()
        self.assertEqual(
            tuple((grid.key, grid.label, grid.rows) for grid in text.grids),
            (
                ("upper", "UPPER", ("ABCDEFGHIJKLM", "NOPQRSTUVWXYZ")),
                ("lower", "lower", ("abcdefghijklm", "nopqrstuvwxyz")),
                ("symbol", "SYMBOL", ("0123456789.,'", "-!?/&: ")),
            ),
        )
        self.assertEqual(
            tuple((field.key, field.prompt, field.max_length) for field in text.fields),
            (
                ("first", "First name?", 8),
                ("last", "Last name?", 8),
                ("codename", "Codename?", 8),
                ("city", "City?", 8),
                ("ward", "Ward?", 8),
            ),
        )
        self.assertEqual(text.occupations[2], "Civil Servant")
        self.assertEqual((text.default_city, text.default_ward), ("Hirasaki", "Asahi"))

    def test_text_remains_editable_within_the_shared_ascii_boundary(self) -> None:
        asset = json.loads(ASSET_PATH.read_text(encoding="utf-8"))
        asset["entries"]["prompt_first"]["text"]["translation"] = "Given name?"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile_entry.json"
            path.write_text(json.dumps(asset), encoding="utf-8")
            text = load_name_entry_text(path, CONFIG_PATH)
        self.assertEqual(text.field("first").prompt, "Given name?")

    def test_non_ascii_and_overlong_defaults_fail_closed(self) -> None:
        for key, value, message in (
            ("prompt_first", "Namé?", "printable ASCII"),
            ("default_city", "123456789", "exceeds 8"),
        ):
            with self.subTest(key=key):
                asset = json.loads(ASSET_PATH.read_text(encoding="utf-8"))
                asset["entries"][key]["text"]["translation"] = value
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "profile_entry.json"
                    path.write_text(json.dumps(asset), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        load_name_entry_text(path, CONFIG_PATH)


if __name__ == "__main__":
    unittest.main()
