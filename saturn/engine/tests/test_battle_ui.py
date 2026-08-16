from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.surfaces.battle_ui import (  # noqa: E402
    BUILD_PATH,
    CHARACTER_OFFSETS,
    CHARACTER_POOL,
    COMBAT_OUTPUT_PATH,
    NAME_OFFSETS,
    NAME_POOL,
    NORMCOM_OUTPUT_PATH,
    RENDERER_RACES,
    RESULT_BEADS,
    RESULT_LIFE_STONES,
    build_battle_ui,
)
from text.util.assets import load_bound_translations  # noqa: E402
from text.util.event_repack import FontMetrics  # noqa: E402


LOAD_ADDRESS = 0x06020000
FONT8_METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"


class BattleUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_battle_ui()
        cls.combat = cls.outputs[COMBAT_OUTPUT_PATH]
        cls.metrics = FontMetrics.load(FONT8_METRICS_PATH)
        cls.by_code = {glyph.code: glyph.text for glyph in cls.metrics.glyphs}

    def _cstring(self, address: int) -> str:
        position = address - LOAD_ADDRESS
        output = []
        while self.combat[position]:
            output.append(self.by_code[self.combat[position]])
            position += 1
        return "".join(output)

    def test_isolated_mature_runtime_is_reproduced(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.combat).hexdigest(),
            "c779593dc1fd0aca649e4e65a1af834b49dc153c32fc9a74b5be2b7257b7ce77",
        )
        self.assertEqual(
            hashlib.sha256(self.outputs[NORMCOM_OUTPUT_PATH]).hexdigest(),
            "4cbd006bb9df41e17b258562e19dd5275243ce35be753bd10beaba0aca046821",
        )

    def test_analysis_and_party_names_come_from_authored_assets(self) -> None:
        demon_ids = [f"game.dvlname.o{index * 8:06x}.text" for index in range(319)]
        demons = load_bound_translations(
            ("game.dvlname.",), required_ids=set(demon_ids)
        )
        for index in (0, 61, 259, 302, 318):
            relative = struct.unpack_from(
                ">H", self.combat, NAME_OFFSETS - LOAD_ADDRESS + index * 2
            )[0]
            self.assertEqual(
                self._cstring(NAME_POOL + relative), demons[demon_ids[index]]
            )

        character_ids = [
            f"game.charname.o{index * 8:06x}.text" for index in range(6)
        ]
        characters = load_bound_translations(
            ("game.charname.",), required_ids=set(character_ids)
        )
        for index, physical_id in enumerate(character_ids):
            relative = struct.unpack_from(
                ">H", self.combat, CHARACTER_OFFSETS - LOAD_ADDRESS + index * 2
            )[0]
            self.assertEqual(
                self._cstring(CHARACTER_POOL + relative), characters[physical_id]
            )

    def test_race_heading_and_result_labels_are_asset_owned(self) -> None:
        races = load_bound_translations(
            ("game.normcom_tables.races.",),
            required_ids={
                f"game.normcom_tables.races.r{index:04d}" for index in range(43)
            },
        )
        first_race = self.combat[
            RENDERER_RACES - LOAD_ADDRESS:
            RENDERER_RACES - LOAD_ADDRESS + 8
        ].rstrip(b"\0")
        self.assertEqual(
            "".join(self.by_code[code] for code in first_race),
            races["game.normcom_tables.races.r0000"] + ":",
        )
        labels = load_bound_translations(
            ("game.combat_result_labels.",),
            required_ids={
                "game.combat_result_labels.o053b8c",
                "game.combat_result_labels.o053ce0",
            },
        )
        self.assertEqual(
            self._cstring(RESULT_LIFE_STONES),
            labels["game.combat_result_labels.o053ce0"],
        )
        self.assertEqual(
            self._cstring(RESULT_BEADS),
            labels["game.combat_result_labels.o053b8c"],
        )

    def test_build_manifest_is_published_with_the_two_targets(self) -> None:
        self.assertIn(BUILD_PATH, self.outputs)
        self.assertEqual(len(self.combat), 351064)
        self.assertEqual(len(self.outputs[NORMCOM_OUTPUT_PATH]), 352360)

    def test_patch_recipes_are_readable_and_all_assembly_is_provenanced(self) -> None:
        engine_root = SATURN_ROOT / "engine"
        config = json.loads(
            (engine_root / "config" / "battle_ui.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["version"], 2)
        assembly = set()
        for group in config["groups"]:
            for patch in group["patches"]:
                self.assertNotIn("replacement", patch)
                self.assertNotIn("replacement_zero_bytes", patch)
                for source in patch.get("assembly", ()):  # executable sources
                    path = engine_root / "asm" / source
                    self.assertTrue(path.is_file(), source)
                    assembly.add(f"asm/{source}")
        manifest = json.loads(self.outputs[BUILD_PATH])
        self.assertEqual(set(manifest["assembly_inputs"]), assembly)

    def test_shadowed_surface_blitter_is_an_intentional_battle_variant(self) -> None:
        source = (
            SATURN_ROOT
            / "engine"
            / "asm"
            / "battle_ui"
            / "font16_surface_blitter.s"
        ).read_text(encoding="utf-8")
        self.assertIn("fixed palette-index-1 shadow", source)
        self.assertNotIn(".word", source)


if __name__ == "__main__":
    unittest.main()
