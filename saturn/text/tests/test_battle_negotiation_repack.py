from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from repack import NEGOTIATION_BUILD_PATH, build_negotiation_outputs  # noqa: E402


MATURE_BANK_HASHES = {
    "COMBDATA/BOSSTALK.EVE": "dc6d622803592163839f0b288b9bc4a5cbdc83821d0b67d2140f68ff15062662",
    "COMBDATA/TLK_BST.EVE": "ec75075e13ed5e6db092e8b8a0355bb9271f6ffc277296211caa822ff0040482",
    "COMBDATA/KEMO.EVE": "8c6096362135ee4910d097c8eded083e3379a87d4ea205e59fac7d023c4682ed",
    "COMBDATA/TLK_KOFU.EVE": "e5a8879335804e50b69bda1823f6055bdffd423b237eb32c4b3d274e669545ef",
    "COMBDATA/NBL_M.EVE": "5053cee9d59f9e96707e4fa6d8098d1ea94c8decb48a42e4e85d9c7b3e0a5d89",
    "COMBDATA/TLK_HIRK.EVE": "2197946e339c422b2056b2fb72be209f7762d55ac3ded55e8924c6f1c50e9cc7",
    "COMBDATA/TLK_YNGM.EVE": "eb71de0c33b48576b52f5cec933f2abad862611d967e3e37d6d2406d87585949",
    "COMBDATA/GRL.EVE": "c4cd4b28eefd1cf465d68552abf30c9c2a28eb25299f32a3449a5c7948b6500b",
    "COMBDATA/TLK_BOY.EVE": "784ab2182e1f799229276b3fe2c1bd392015880a9eb05bac530558e32d29ec04",
    "COMBDATA/CLD_F.EVE": "0cf16b9e51d55def0e73c796b9e209d0a672e5cb4531147f8128a145e7f62ba7",
    "COMBDATA/TLK_LADY.EVE": "395912e732cc72d03c33603009de02fb02bbf53dca52d14d77a0b253718b19b8",
    "COMBDATA/TLK_CRZY.EVE": "f97aa11aec74337be09b3cda07662316dfdb7aa20f118512d9101cb68f37bb1a",
    "COMBDATA/JIJY.EVE": "f752096febc19a9e87a05fcd6d5456cc6cd866bad344d4beacbde43e73ec6b7c",
    "COMBDATA/CYNI.EVE": "513ab1e806a7fa5152667815043e585984aa53298f64fdea7eb28500385351bb",
    "COMBDATA/TLK_WEST.EVE": "96816863fdac215b5e93a121aa8df4dffed5c88e87ef007c7edd2f3fb559a0bf",
    "COMBDATA/SLM.EVE": "8994844ebba21dc2b4ba4c220088f1ad91caad835ea86a882429fc87e92e3a61",
}


class BattleNegotiationRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_negotiation_outputs()

    def test_all_sixteen_banks_match_the_mature_saturn_output(self) -> None:
        actual = {
            path.relative_to(TEXT_ROOT / "generated" / "game").as_posix():
            hashlib.sha256(value).hexdigest()
            for path, value in self.outputs.items()
            if path.suffix == ".EVE"
        }
        self.assertEqual(actual, MATURE_BANK_HASHES)

    def test_fixed_text_and_item_insert_tables_are_deterministic(self) -> None:
        self.assertEqual(
            hashlib.sha256(
                self.outputs[TEXT_ROOT / "generated" / "game" / "COMBAT.BIN"]
            ).hexdigest(),
            "91e273875fe578be8e5fdac1be46ef0cc896fbad8bb51c8f6e6d5e0074eee5f3",
        )
        self.assertEqual(
            hashlib.sha256(
                self.outputs[TEXT_ROOT / "generated" / "game" / "ITEMNAME.DAT"]
            ).hexdigest(),
            "67eff5fd43eb7408dc1f7d6dff1c00c862d4ae9f4f020388280de16d4392f526",
        )

    def test_manifest_covers_every_translator_facing_page(self) -> None:
        document = json.loads(self.outputs[NEGOTIATION_BUILD_PATH])
        self.assertEqual(document["surface"], "battle.negotiation")
        self.assertEqual(
            document["records"],
            {
                "dialogue_pages": 9920,
                "fixed_messages": 117,
                "item_names": 287,
                "item_descriptions": 287,
                "translated_item_descriptions": 265,
                "total": 10611,
            },
        )
        self.assertEqual(set(document["outputs"]), {
            *MATURE_BANK_HASHES,
            "COMBAT.BIN",
            "ITEMNAME.DAT",
        })
        self.assertEqual(
            sum(row.get("pages", 0) for row in document["outputs"].values()),
            9920,
        )


if __name__ == "__main__":
    unittest.main()
