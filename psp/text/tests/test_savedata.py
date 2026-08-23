from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from psp.text.util.savedata import (
    CONFIG_PATH,
    LOCATION_ASSET_PATH,
    SAVE_ASSET_PATH,
    load_savedata_text,
)


class SavedataTextTests(unittest.TestCase):
    def test_canonical_assets_form_the_complete_metadata_contract(self) -> None:
        text = load_savedata_text()
        self.assertEqual(text.game_title, "Devil Summoner")
        self.assertEqual(text.slot_title, "Devil Summoner Save Data")
        self.assertEqual(text.difficulties, ("Normal", "Hard"))
        self.assertEqual((text.home, text.office, text.unknown), ("Home", "Detective Agency", "Unknown"))
        self.assertEqual(len(text.locations), 24)
        self.assertEqual((text.locations[0], text.locations[-1]), ("Library", "Ancient Tomb"))
        self.assertEqual(
            text.detail_template,
            "Shin Megami Tensei: Devil Summoner - Save Data{n}{codename} Lv. {level} ({difficulty}){n}{location} ({hours}:{minutes})",
        )

    def test_detail_placeholder_or_punctuation_drift_fails_closed(self) -> None:
        save = json.loads(SAVE_ASSET_PATH.read_text(encoding="utf-8"))
        save["entries"]["psp_detail"]["text"]["translation"] = (
            "Save Data{n}{codename} Level {level} ({difficulty}){n}"
            "{location} ({hours}:{minutes})"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save_load.json"
            path.write_text(json.dumps(save), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "punctuation changed"):
                load_savedata_text(path, LOCATION_ASSET_PATH, CONFIG_PATH)

    def test_location_inventory_and_ascii_are_guarded(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config["location_keys"][-1] = "missing"
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "savedata.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing.name"):
                load_savedata_text(SAVE_ASSET_PATH, LOCATION_ASSET_PATH, config_path)


if __name__ == "__main__":
    unittest.main()
