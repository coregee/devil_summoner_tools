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
    ANALYZE_BUILD_MANIFEST_PATH,
    ANALYZE_OUTPUT_PATH,
    build_analyze_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
EXPECTED_HASH = "3d84b647018108d6a2f1f74a068336d6166766b1a3d25d826f7eb05c66f2efe7"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class AnalyzeBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"Analyze engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_analyze_surface()
        cls.manifest = json.loads(cls.outputs[ANALYZE_BUILD_MANIFEST_PATH])

    def test_parent_build_publishes_one_terminal_binary_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {ANALYZE_OUTPUT_PATH, ANALYZE_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(_sha256(self.outputs[ANALYZE_OUTPUT_PATH]), EXPECTED_HASH)
        self.assertEqual(self.manifest["surface"], "map_3d.analyze")
        self.assertEqual(
            self.manifest["output"],
            {"file": "DA_3D.BIN", "sha256": EXPECTED_HASH},
        )
        self.assertEqual(self.manifest["patches"], 37)
        self.assertEqual(
            self.manifest["runtime"],
            {
                "detail": {
                    "address": "0x06064386",
                    "bytes": 3510,
                    "capacity": 3522,
                },
                "table": {
                    "address": "0x0606517c",
                    "bytes": 256,
                    "capacity": 258,
                },
            },
        )

    def test_parent_build_names_every_direct_dependency(self) -> None:
        self.assertEqual(
            set(self.manifest["source_inputs"]),
            {"game:DA_3D.BIN", "game:FONT16.FON"},
        )
        paths = {
            *self.manifest["asset_inputs"],
            *self.manifest["runtime_inputs"],
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )
        for expected in (
            "saturn/text/generated/game/comp_menu_build.json",
            "saturn/text/generated/game/battle_ui_build.json",
            "saturn/text/generated/game/DVLNAME.DAT",
            "saturn/text/generated/game/MAGNAME.DAT",
            "saturn/text/config/glyph_sets.json",
        ):
            self.assertIn(expected, self.manifest["runtime_inputs"])

    def test_default_build_installs_the_analyze_surface_once(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_analyze_engine"]["arguments"],
            ["map_3d.analyze"],
        )
        self.assertEqual(
            steps["install_analyze_engine"]["files"],
            [
                {
                    "source": "engine/generated/game/DA_3D.BIN",
                    "destination": "rom/extracted/game/DA_3D.BIN",
                }
            ],
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_analyze_engine"), 1)
        self.assertEqual(profile.count("install_analyze_engine"), 1)
        self.assertLess(
            profile.index("repack_battle_ui_text"),
            profile.index("build_analyze_engine"),
        )
        self.assertLess(
            profile.index("repack_comp_text"),
            profile.index("build_analyze_engine"),
        )
        self.assertLess(
            profile.index("build_analyze_engine"),
            profile.index("install_analyze_engine"),
        )


if __name__ == "__main__":
    unittest.main()
