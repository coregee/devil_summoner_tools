from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from repack import (  # noqa: E402
    GENERATED_ROOT,
    SHOPSMP_BUILD_PATH,
    _stock_files,
    build_shopsmp_outputs,
)
from util.event_repack import (  # noqa: E402
    SHOP_EVENT_SOURCES,
    EveBank,
    load_event_source_translations,
    message_encoding_overrides,
)
from util.sources import load_manifest, manifest_path  # noqa: E402


OUTPUT_HASH = "ac12a847c6b14ec3e9effb143cbcca0e8762701caab094c4a5517f36cc181773"
GOOFY_MESSAGE_HASH = "9f585bc2c60caabda79858496a9bd7e69636d589c057e47b1b5e2141ad13a2c7"


class ShopEventRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_shopsmp_outputs()
        cls.output = cls.outputs[GENERATED_ROOT / "SHOPSMP.EVE"]
        cls.stock = _stock_files((PurePosixPath("SHOPSMP.EVE"),))[
            PurePosixPath("SHOPSMP.EVE")
        ]
        cls.output_bank = EveBank.parse(cls.output, 0x47FE, 0x5000)
        cls.stock_bank = EveBank.parse(cls.stock, 0x47FE, 0x5000)

    def test_complete_mixed_bank_is_deterministic(self) -> None:
        self.assertEqual(hashlib.sha256(self.output).hexdigest(), OUTPUT_HASH)
        document = json.loads(self.outputs[SHOPSMP_BUILD_PATH])
        self.assertEqual(document["surface"], "event.dialogue")
        self.assertEqual(
            document["records"],
            {"translated": 763, "deferred": 0, "total": 763},
        )
        self.assertIsNone(document["deferred"])
        self.assertEqual(
            document["outputs"]["SHOPSMP.EVE"],
            {
                "sha256": OUTPUT_HASH,
                "messages": 815,
                "pages": 763,
                "body_bytes": 27984,
            },
        )

    def test_every_translator_facing_fusion_message_is_compiled(self) -> None:
        manifest = load_manifest(manifest_path("game"))
        source = next(
            row for row in manifest.sources if row.name == SHOP_EVENT_SOURCES[0]
        )
        overrides = message_encoding_overrides(source.container, source.name)
        fusion_messages = {
            message
            for message, encoding in overrides.items()
            if encoding == "game_font12_event_space"
        }
        self.assertEqual(len(fusion_messages), 194)
        translations = load_event_source_translations(SHOP_EVENT_SOURCES)
        expected_ids = {
            f"game.shopsmp.m{message:04d}.p00"
            for message in fusion_messages - {96}
        }
        self.assertTrue(expected_ids <= set(translations))
        unchanged = {
            message
            for message in fusion_messages
            if self.output_bank.messages[message].words
            == self.stock_bank.messages[message].words
        }
        # m0096 is structural-only. The authored '#' and 'ER' happen to use
        # the same physical glyph codes as stock and are still compiled.
        self.assertEqual(unchanged, {96, 105, 266})
        self.assertEqual(translations["game.shopsmp.m0105.p00"], "#")
        self.assertEqual(translations["game.shopsmp.m0266.p00"], "ER")

    def test_goofy_shop_dialogue_uses_the_authored_translation(self) -> None:
        translations = load_event_source_translations(SHOP_EVENT_SOURCES)
        self.assertEqual(
            translations["game.shopsmp.m0741.p00"],
            "Goofy: Much obliged.{WAIT}{n}I change the stock now and then,"
            "{n}so come by often!",
        )
        words = self.output_bank.messages[741].words
        encoded = struct.pack(f">{len(words)}H", *words)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), GOOFY_MESSAGE_HASH)
        self.assertNotEqual(words, self.stock_bank.messages[741].words)


if __name__ == "__main__":
    unittest.main()
