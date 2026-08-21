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
    "COMBDATA/BOSSTALK.EVE": "780e578a0ab0f99bed7be4060fe4f0c50df163ed1a0f99cb2cc879cb0cac053a",
    "COMBDATA/TLK_BST.EVE": "29ca6855c6344343d044eb91be95b9b3158e8aa7ba12d5584a68a6442be55fa8",
    "COMBDATA/KEMO.EVE": "f26efd52f0edc1a4866b8ae26d4475c1335d4b71e11c23d438258148cef8703b",
    "COMBDATA/TLK_KOFU.EVE": "c858534b308e746f8551830f0259d1dbe0546d7a88c4120935407293a4d3cd5e",
    "COMBDATA/NBL_M.EVE": "6c9ea93dafa8c70923fe9e8fea9cd3bf8a215af7b735746455a4bd45be5c570c",
    "COMBDATA/TLK_HIRK.EVE": "ffaaf4141323c8117157f2e10cfcdcbb153c079869070946ca5c0376a51f3aa5",
    "COMBDATA/TLK_YNGM.EVE": "44333f1b164a3cd1a0101df60678cb8a9bc744af4cfbaf8005a62550950279e4",
    "COMBDATA/GRL.EVE": "62aed64f6163a3307b049d80a4948d1bfc7ed82aac1c92d6f94365f18d134a46",
    "COMBDATA/TLK_BOY.EVE": "cb5f44f8577f209a33885e2ff6878dfae42253de0aeee672b5705628d6c18d8c",
    "COMBDATA/CLD_F.EVE": "c1d8ed1806853eb1ff63a600b7788b0050c52f5e74897fa00139e1cb9855217a",
    "COMBDATA/TLK_LADY.EVE": "587d9e4dc6904f41294e5270db0587919f753de2310f6d835a307beb5e67c2fb",
    "COMBDATA/TLK_CRZY.EVE": "d54403a02fbb68921c3350e41be5c67f4ab7304d643d83546cf7fbdc81749d8b",
    "COMBDATA/JIJY.EVE": "d3c3dfecfcc05a1235d510e98a4a0fc6ded93880a904493236552dcfb877d5a6",
    "COMBDATA/CYNI.EVE": "6b3149a3834280a2a71b8057fe36608f021ebefba2e69bde8235dc260664140a",
    "COMBDATA/TLK_WEST.EVE": "c9140c60ab26a02f08bef4df1f8559adbfcbc200282678298f89cf19204242c8",
    "COMBDATA/SLM.EVE": "070da9fef163013db3b592e18ce5e25e56cf73ff80f01ca88730e90e935c6540",
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
            "7fa8643884fedecbd70bbb2074336c1e4e06b1455178afeb6e6456ca2ac58048",
        )
        self.assertEqual(
            hashlib.sha256(
                self.outputs[TEXT_ROOT / "generated" / "game" / "ITEMNAME.DAT"]
            ).hexdigest(),
            "ef7529cb8d5b3ace761172c79c9359a7d588bfda0260a00c754dfdec8e2be140",
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
