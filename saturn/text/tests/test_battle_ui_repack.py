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

from repack import BATTLE_UI_BUILD_PATH, build_battle_ui_outputs  # noqa: E402
from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


OUTPUT_HASHES = {
    "BTL_HELP.DAT": "b909eb2a41bd3e961902436dec04a71931ff325bcebb01909f823b501f8b0a6c",
    "BTL_MES.MD8": "54d0e90507106050f61e09793389d195478c967b328ecd2c4d09234d426c1cda",
    "BTL_SRF.MDT": "d3ff95ee68d82b029b9e21bda5f3a298e5d8733075e2c0678506e5bcae51add5",
    "BUTU_SRF.MDT": "09ce50c4f2568a61823f8c803907caf2a65295ac5c4121f259aca8f96a94be54",
    "ITEMNAME.DAT": "67eff5fd43eb7408dc1f7d6dff1c00c862d4ae9f4f020388280de16d4392f526",
    "MAGNAME.DAT": "6feee6313b73840fc52bbfc256b244a75faade8320ba135679d9f7bd5c1769a7",
}


class BattleUiRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_battle_ui_outputs()

    def test_all_six_files_are_deterministic(self) -> None:
        actual = {
            name: hashlib.sha256(
                self.outputs[TEXT_ROOT / "generated" / "game" / name]
            ).hexdigest()
            for name in OUTPUT_HASHES
        }
        self.assertEqual(actual, OUTPUT_HASHES)

    def test_build_manifest_records_capacity_without_fallbacks(self) -> None:
        document = json.loads(self.outputs[BATTLE_UI_BUILD_PATH])
        self.assertEqual(document["surface"], "battle.ui")
        self.assertEqual(
            {name: row["records"] for name, row in document["outputs"].items()},
            {
                "BTL_HELP.DAT": 19,
                "BTL_MES.MD8": 358,
                "BTL_SRF.MDT": 363,
                "BUTU_SRF.MDT": 144,
                "ITEMNAME.DAT": 287,
                "MAGNAME.DAT": 255,
            },
        )
        self.assertEqual(document["outputs"]["BTL_MES.MD8"]["translated"], 313)
        self.assertEqual(document["outputs"]["BTL_SRF.MDT"]["translated"], 203)
        self.assertEqual(document["outputs"]["BUTU_SRF.MDT"]["translated"], 64)
        for name in ("BTL_MES.MD8", "BTL_SRF.MDT", "BUTU_SRF.MDT"):
            row = document["outputs"][name]
            self.assertLessEqual(row["body_bytes"], row["capacity_bytes"])

    def test_ritual_console_surfaces_every_nonempty_row(self) -> None:
        asset = load_asset("ritual/console.json")
        binding = load_binding(BINDING_ROOT / "ritual_console.json")
        self.assertEqual(len(asset.entries), 64)
        self.assertEqual(len(binding.records), 64)
        self.assertEqual(
            set(binding.records),
            {
                *(f"game.butu_srf.p{index:04d}" for index in range(0, 16)),
                *(f"game.butu_srf.p{index:04d}" for index in range(36, 52)),
                *(f"game.butu_srf.p{index:04d}" for index in range(72, 88)),
                *(f"game.butu_srf.p{index:04d}" for index in range(108, 124)),
            },
        )
        self.assertEqual(dict(binding.field_surfaces), {"text": ("ritual.console",)})


if __name__ == "__main__":
    unittest.main()
