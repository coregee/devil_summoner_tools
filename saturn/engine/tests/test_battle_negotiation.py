from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path, PurePosixPath


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.surfaces.battle_negotiation import (  # noqa: E402
    BUILD_PATH,
    CONFIG_PATH,
    FONT16_METRICS_PATH,
    OUTPUT_PATH,
    build_battle_negotiation,
)
from engine.core.patch_recipes import (  # noqa: E402
    ASSEMBLY_ROOT,
    load_patch_recipe_configuration,
)
from text.util.assets import load_asset, load_bound_translations  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


LOAD_ADDRESS = 0x06020000


class BattleNegotiationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_battle_negotiation()
        cls.combat = cls.outputs[OUTPUT_PATH]
        cls.manifest = json.loads(cls.outputs[BUILD_PATH].decode("utf-8"))
        cls.metrics = FontMetrics.load(FONT16_METRICS_PATH)
        cls.config = load_patch_recipe_configuration(
            CONFIG_PATH,
            surface="battle.negotiation",
            target_names={"COMBAT.BIN"},
            input_names={
                "font16_metrics_sha256",
                "font8_metrics_sha256",
                "event_runtime_table_sha256",
            },
        )

    def _decode(self, address: int) -> str:
        position = address - LOAD_ADDRESS
        codes: list[int] = []
        while True:
            code = struct.unpack_from(">H", self.combat, position)[0]
            position += 2
            if code == 0x8000:
                break
            codes.append(code)
        by_code = {glyph.code: glyph.text for glyph in self.metrics.glyphs}
        return "".join(by_code[code] for code in codes)

    def test_deterministic_negotiation_runtime_is_reproduced(self) -> None:
        self.assertEqual(len(self.combat), 351064)
        self.assertEqual(
            hashlib.sha256(self.combat).hexdigest(),
            "457cea3774d7894736aa5ecf02bcbcf95a0a731f008d963b78d57f8fc8fe2d1a",
        )

    def test_all_demon_and_race_inserts_come_from_authored_assets(self) -> None:
        demon_ids = {
            f"game.dvlname.o{index * 8:06x}.text" for index in range(319)
        }
        race_ids = {f"game.normcom_tables.races.r{index:04d}" for index in range(43)}
        expected = load_bound_translations(
            ("game.dvlname.", "game.normcom_tables.races."),
            required_ids=demon_ids | race_ids,
        )
        for index in range(319):
            relative = struct.unpack_from(">H", self.combat, 0x4000 + index * 2)[0]
            self.assertEqual(
                self._decode(0x060244D4 + relative),
                expected[f"game.dvlname.o{index * 8:06x}.text"],
            )
        for index in range(43):
            relative = struct.unpack_from(">H", self.combat, 0x427E + index * 2)[0]
            self.assertEqual(
                self._decode(0x060244D4 + relative),
                expected[f"game.normcom_tables.races.r{index:04d}"],
            )

    def test_kyouji_full_name_comes_from_the_character_asset(self) -> None:
        _reference, translation, _reviewed = load_asset(
            PurePosixPath("characters.json")
        ).field("kyouji_kuzunoha.full_name").resolve()
        self.assertEqual(self._decode(0x060219C6), translation)

    def test_executable_replacements_are_readable_assembly(self) -> None:
        recipes = self.config.patches["COMBAT.BIN"]
        kinds = [recipe.replacement.kind for recipe in recipes]
        self.assertEqual(
            {kind: kinds.count(kind) for kind in set(kinds)},
            {
                "assembly": 9,
                "linked_pointer": 28,
                "pointer": 2,
                "instruction": 19,
            },
        )
        sources = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        self.assertEqual(
            sources,
            {
                "battle_negotiation/dialogue_vwf.s",
                "battle_negotiation/dispatch_hook.s",
                "battle_negotiation/english_inserts.s",
                "battle_negotiation/font16_surface_blitter.s",
                "battle_negotiation/packed_dispatch.s",
                "battle_negotiation/store_hook.s",
                "battle_negotiation/typewriter_reset_hook.s",
                "battle_negotiation/typewriter_reset.s",
                "battle_negotiation/typewriter_visible_hook.s",
                "battle_negotiation/typewriter_visible.s",
            },
        )
        self.assertEqual(len(self.manifest["assembly_inputs"]), len(sources))
        self.assertNotIn(
            '"replacement"', CONFIG_PATH.read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()
