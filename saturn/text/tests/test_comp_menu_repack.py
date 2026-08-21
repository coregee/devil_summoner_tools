from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
TEXT_ROOT = SATURN_ROOT / "text"
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from repack import build_comp_menu_outputs  # noqa: E402
from util.assets import load_bound_translations  # noqa: E402
from util.event_repack import FontMetrics  # noqa: E402


GENERATED_ROOT = SATURN_ROOT / "text" / "generated" / "game"
FONT8_METRICS = SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"
OUTPUT_HASHES = {
    "DVLNAME.DAT": "8dc63eb84662c567c6584b92c2838d7f067195f5191c879907f26b5deaa6d12e",
    "NORMHELP.DAT": "965071d279caf0a4558e183c20cab69666905a5733d434b0eecf6e9f8d657529",
}


class CompMenuRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_comp_menu_outputs()
        cls.manifest = json.loads(
            cls.outputs[GENERATED_ROOT / "comp_menu_build.json"].decode("utf-8")
        )

    def test_two_files_are_deterministic(self) -> None:
        for name, expected in OUTPUT_HASHES.items():
            with self.subTest(name=name):
                data = self.outputs[GENERATED_ROOT / name]
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_manifest_accounts_for_direct_and_overflow_names(self) -> None:
        names = self.manifest["outputs"]["DVLNAME.DAT"]
        self.assertEqual(names["records"], 319)
        self.assertEqual(names["direct_names"], 210)
        self.assertEqual(names["overflow_names"], 109)
        self.assertEqual(names["direct_names"] + names["overflow_names"], 319)
        help_text = self.manifest["outputs"]["NORMHELP.DAT"]
        self.assertEqual(help_text["records"], 24)
        self.assertEqual(help_text["translated"], 24)
        self.assertLessEqual(
            help_text["longest_record_words"], help_text["capacity_words"]
        )

    def test_every_direct_name_is_rebuilt_from_its_asset(self) -> None:
        metrics = FontMetrics.load(FONT8_METRICS)
        ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(319)]
        values = load_bound_translations(("game.dvlname.",), required_ids=set(ids))
        data = self.outputs[GENERATED_ROOT / "DVLNAME.DAT"]
        checked = 0
        for index, physical_id in enumerate(ids):
            glyphs = metrics.segment_output(values[physical_id])
            encoded = bytes(glyph.code for glyph in glyphs)
            pixels = sum(glyph.advance for glyph in glyphs)
            if len(encoded) <= 8 and pixels <= 64:
                self.assertEqual(
                    data[index * 8:(index + 1) * 8], encoded.ljust(8, b"\0")
                )
                checked += 1
        self.assertEqual(checked, 210)


if __name__ == "__main__":
    unittest.main()
