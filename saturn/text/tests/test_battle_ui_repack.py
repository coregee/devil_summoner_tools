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


MATURE_HASHES = {
    "BTL_HELP.DAT": "ba5fadaac6dd9474645df15f935abbbf78891665b1cd614f91321d0c7c8fae95",
    "BTL_MES.MD8": "fbac4c8b5c5dd8fd45313ce7559dec292cbadd4a8853fc37c4aa81cf207e9405",
    "BTL_SRF.MDT": "82fb778e383cfd38e3808966fc108b9a02cba60cd8c7fe4d732a2e80f1a45f1a",
    "BUTU_SRF.MDT": "b92ae19e0effab3a82341e488e1bd988ab8238951e5e396242643bffe13c35e4",
    "ITEMNAME.DAT": "ef7529cb8d5b3ace761172c79c9359a7d588bfda0260a00c754dfdec8e2be140",
    "MAGNAME.DAT": "b6904502a2f6a04dcd3c1074bc7d2852eb25fe89c11561214292370b47df3e0c",
}


class BattleUiRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_battle_ui_outputs()

    def test_all_six_files_match_the_mature_saturn_output(self) -> None:
        actual = {
            name: hashlib.sha256(
                self.outputs[TEXT_ROOT / "generated" / "game" / name]
            ).hexdigest()
            for name in MATURE_HASHES
        }
        self.assertEqual(actual, MATURE_HASHES)

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
