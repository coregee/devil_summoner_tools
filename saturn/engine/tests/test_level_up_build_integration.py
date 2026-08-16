from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    LEVEL_UP_BUILD_MANIFEST_PATH,
    LEVEL_UP_OUTPUT_PATH,
    build_level_up_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
EXPECTED_HASH = "466c552e95bb5c7bd808f550e8f0832077715f20fd5427dedf412793fe5d1ed1"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class LevelUpBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"Level Up engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_level_up_surface()
        cls.manifest = json.loads(cls.outputs[LEVEL_UP_BUILD_MANIFEST_PATH])

    def test_parent_build_publishes_one_terminal_binary_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {LEVEL_UP_OUTPUT_PATH, LEVEL_UP_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(_sha256(self.outputs[LEVEL_UP_OUTPUT_PATH]), EXPECTED_HASH)
        self.assertEqual(self.manifest["surface"], "level_up.ui")
        self.assertEqual(
            self.manifest["output"],
            {"file": "LEVEL_UP.BIN", "sha256": EXPECTED_HASH},
        )
        self.assertEqual(self.manifest["runtime"]["bytes"], 1279)
        self.assertEqual(self.manifest["runtime"]["capacity"], 1280)

    def test_parent_build_names_every_direct_dependency(self) -> None:
        self.assertEqual(
            set(self.manifest["source_inputs"]),
            {"game:LEVEL_UP.BIN", "game:FONT16.FON"},
        )
        paths = {
            *self.manifest["asset_inputs"],
            *self.manifest["runtime_inputs"],
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )
        self.assertIn(
            "saturn/text/generated/game/battle_ui_build.json",
            self.manifest["runtime_inputs"],
        )
        self.assertIn(
            "saturn/text/generated/game/MAGNAME.DAT",
            self.manifest["runtime_inputs"],
        )

    def test_default_build_installs_the_level_up_surface_once(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_level_up_engine"]["arguments"], ["level_up.ui"]
        )
        self.assertEqual(
            steps["install_level_up_engine"]["files"],
            [
                {
                    "source": "engine/generated/game/LEVEL_UP.BIN",
                    "destination": "rom/extracted/game/LEVEL_UP.BIN",
                }
            ],
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_level_up_engine"), 1)
        self.assertEqual(profile.count("install_level_up_engine"), 1)
        self.assertLess(
            profile.index("repack_battle_ui_text"),
            profile.index("build_level_up_engine"),
        )
        self.assertLess(
            profile.index("build_level_up_engine"),
            profile.index("install_level_up_engine"),
        )


if __name__ == "__main__":
    unittest.main()
