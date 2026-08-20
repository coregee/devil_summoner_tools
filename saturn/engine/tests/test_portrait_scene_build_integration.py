from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    PORTRAIT_SCENE_BUILD_MANIFEST_PATH,
    PORTRAIT_SCENE_OUTPUT_PATH,
    build_portrait_scene_surface,
    main,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
VISUAL_MANIFEST_PATH = SATURN_ROOT / "visual" / "modified" / "game" / "manifest.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
EXPECTED_OUTPUT_SHA256 = (
    "3cbbf6ec70887cdb49a46c006767550438da684a30b5a754d6ce7c811d337814"
)
STOCK_MSGR_SHA256 = (
    "fc483f3483b14591bef0af1981d2d142c3621506981a596b31595283daa183fa"
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class PortraitSceneBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"portrait-scene engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_portrait_scene_surface()
        cls.data = cls.outputs[PORTRAIT_SCENE_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[PORTRAIT_SCENE_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_one_terminal_target_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {PORTRAIT_SCENE_OUTPUT_PATH, PORTRAIT_SCENE_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(_sha256(self.data), EXPECTED_OUTPUT_SHA256)
        self.assertEqual(self.manifest["surface"], "portrait_scene.ui")
        self.assertEqual(
            self.manifest["output"],
            {"file": "MSGR.COF", "sha256": EXPECTED_OUTPUT_SHA256},
        )
        self.assertEqual(self.manifest["patches"], 37)
        self.assertEqual(
            self.manifest["patch_groups"],
            [
                "msgr.dialogue_vwf",
                "msgr.term_inserts",
                "msgr.player_name_adapters",
                "msgr.fixed_text_compatibility",
                "msgr.debug_messages",
            ],
        )

    def test_manifest_records_each_runtime_arena(self) -> None:
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 6679,
                "capacity": 24928,
                "arenas": {
                    "dialogue_window": {
                        "address": "0x06060400",
                        "bytes": 2113,
                        "capacity": 19456,
                    },
                    "full_term_inserts": {
                        "address": "0x06065000",
                        "bytes": 4480,
                        "capacity": 5376,
                    },
                    "player_name_raw_menu": {
                        "address": "0x0606c63c",
                        "bytes": 86,
                        "capacity": 96,
                    },
                },
            },
        )

    def test_manifest_names_verified_sources_and_every_input_kind(self) -> None:
        self.assertEqual(
            self.manifest["source_inputs"],
            {"game:MSGR.COF": STOCK_MSGR_SHA256},
        )
        self.assertEqual(
            set(self.manifest["asset_inputs"]),
            {
                "assets/text/demons.json",
                "assets/text/characters.json",
                "assets/text/races.json",
                "assets/text/system/debug.json",
            },
        )
        self.assertEqual(len(self.manifest["assembly_inputs"]), 11)
        for expected in (
            "saturn/engine/asm/shared/event_window/advance.s",
            "saturn/engine/asm/shared/event_window/full_term_inserts.s",
            "saturn/engine/asm/shared/player_name_inserts/raw_menu_inserts.s",
        ):
            self.assertIn(expected, self.manifest["assembly_inputs"])

        runtime_inputs = set(self.manifest["runtime_inputs"])
        for expected in (
            "saturn/font/generated/game/FONT16.FON",
            "saturn/font/generated/game/FONT12.FON",
            "saturn/font/generated/game/FONT8.FON",
            "saturn/font/generated/game/FONT8_metrics.json",
            "saturn/text/generated/game/event_build.json",
            "saturn/text/generated/game/MESFILE.EVE",
            "saturn/text/generated/game/EVFILE_2.EVE",
            "saturn/text/bindings/portrait_scene_debug.json",
            "saturn/text/corpus/game/addressed/msgr_debug_ascii.json",
            "saturn/engine/shared/player_name_adapters.py",
        ):
            self.assertIn(expected, runtime_inputs)
        self.assertNotIn(
            "saturn/text/generated/game/SHOPSMP.EVE", runtime_inputs
        )

        paths = {
            *self.manifest["asset_inputs"],
            *runtime_inputs,
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )

    def test_default_build_installs_once_after_general_event_banks(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_portrait_scene_engine"],
            {
                "id": "build_portrait_scene_engine",
                "description": (
                    "Build the complete portrait-scene event-window runtime "
                    "from shared authored text, generated fonts, and "
                    "player-name adapters."
                ),
                "type": "python",
                "script": "engine/build.py",
                "arguments": ["portrait_scene.ui"],
                "check_arguments": ["portrait_scene.ui", "--check"],
            },
        )
        self.assertEqual(
            steps["install_portrait_scene_engine"],
            {
                "id": "install_portrait_scene_engine",
                "description": "Install the terminal MSGR portrait-scene runtime.",
                "type": "copy",
                "files": [
                    {
                        "source": "engine/generated/game/MSGR.COF",
                        "destination": "rom/extracted/game/MSGR.COF",
                    }
                ],
            },
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_portrait_scene_engine"), 1)
        self.assertEqual(profile.count("install_portrait_scene_engine"), 1)
        event_install = profile.index("install_event_text")
        self.assertEqual(
            profile[event_install + 1 : event_install + 3],
            ["build_portrait_scene_engine", "install_portrait_scene_engine"],
        )
        self.assertLess(
            profile.index("install_portrait_scene_engine"),
            profile.index("repack_shopsmp_text"),
        )

        installers = [
            row["id"]
            for row in document["steps"]
            if any(
                file.get("destination") == "rom/extracted/game/MSGR.COF"
                for file in row.get("files", ())
            )
        ]
        self.assertEqual(installers, ["install_portrait_scene_engine"])

    def test_cli_dispatch_and_visual_ownership(self) -> None:
        with patch.object(
            sys, "argv", ["build.py", "portrait_scene.ui", "--check"]
        ), patch(
            "engine.build.build_portrait_scene_surface", return_value=self.outputs
        ) as builder, patch("engine.build._publish") as publish, redirect_stdout(
            io.StringIO()
        ):
            self.assertEqual(main(), 0)
        builder.assert_called_once_with()
        publish.assert_called_once_with(self.outputs, check=True)

        visual = json.loads(VISUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("MSGR.COF", visual["sources"])


if __name__ == "__main__":
    unittest.main()
