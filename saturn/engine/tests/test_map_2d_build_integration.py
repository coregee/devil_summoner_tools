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
    MAP_2D_BUILD_MANIFEST_PATH,
    MAP_2D_OUTPUT_PATH,
    build_map_2d_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
VISUAL_MANIFEST_PATH = SATURN_ROOT / "visual" / "modified" / "game" / "manifest.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
EXPECTED_OUTPUT_SHA256 = (
    "dce250711d7a596bb6c675c76c8cc30542181f00570c5bd4a92d3b7eca6b1123"
)
STOCK_MAP_2D_SHA256 = (
    "1e8d00baefdfa282f3a63beb48ca13adec179935594bd5361bf8234c61ed6ecc"
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Map2dBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"MAP2D engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_map_2d_surface()
        cls.data = cls.outputs[MAP_2D_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[MAP_2D_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_one_terminal_target_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {MAP_2D_OUTPUT_PATH, MAP_2D_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(_sha256(self.data), EXPECTED_OUTPUT_SHA256)
        self.assertEqual(self.manifest["surface"], "map_2d.ui")
        self.assertEqual(
            self.manifest["output"],
            {"file": "MAP2D.BIN", "sha256": EXPECTED_OUTPUT_SHA256},
        )
        self.assertEqual(self.manifest["patches"], 24)
        self.assertEqual(
            self.manifest["patch_groups"],
            [
                "map_2d.runtime",
                "map_2d.prompt",
                "map_2d.labels",
                "map_2d.layout",
            ],
        )
        self.assertEqual(
            self.manifest["runtime"], {"bytes": 2166, "capacity": 2756}
        )

    def test_manifest_records_verified_sources_and_every_direct_input(self) -> None:
        self.assertEqual(
            self.manifest["source_inputs"],
            {"game:MAP2D.BIN": STOCK_MAP_2D_SHA256},
        )
        self.assertEqual(
            set(self.manifest["asset_inputs"]),
            {
                "assets/text/ui/map_2d.json",
                "assets/text/ui/profile_entry.json",
                "assets/text/locations.json",
                "assets/text/field/messages.json",
            },
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {
                "saturn/engine/asm/map_2d_ui/name_compositor.s",
                "saturn/engine/asm/map_2d_ui/prompt_wrapper.s",
            },
        )
        runtime_inputs = set(self.manifest["runtime_inputs"])
        for expected in (
            "saturn/font/generated/game/FONT16.FON",
            "saturn/font/generated/game/FONT16_metrics.json",
            "saturn/text/bindings/map_2d.json",
            "saturn/text/bindings/map_2d_profile.json",
            "saturn/text/bindings/map_2d_locations.json",
            "saturn/text/bindings/map_2d_messages.json",
            "saturn/text/corpus/game/addressed/map_static.json",
            "saturn/engine/shared/player_names.py",
        ):
            self.assertIn(expected, runtime_inputs)

        paths = {
            *self.manifest["asset_inputs"],
            *runtime_inputs,
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )
        self.assertFalse(any(path.endswith("/NAME.BIN") for path in paths))
        self.assertFalse(
            any("profile_entry_ui_build.json" in path for path in paths)
        )

    def test_default_build_installs_once_after_profile_and_before_visuals(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_map_2d_engine"],
            {
                "id": "build_map_2d_engine",
                "description": (
                    "Build the complete two-dimensional city map from shared "
                    "authored text and generated fonts."
                ),
                "type": "python",
                "script": "engine/build.py",
                "arguments": ["map_2d.ui"],
                "check_arguments": ["map_2d.ui", "--check"],
            },
        )
        self.assertEqual(
            steps["install_map_2d_engine"],
            {
                "id": "install_map_2d_engine",
                "description": "Install the terminal MAP2D city-map runtime.",
                "type": "copy",
                "files": [
                    {
                        "source": "engine/generated/game/MAP2D.BIN",
                        "destination": "rom/extracted/game/MAP2D.BIN",
                    }
                ],
            },
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_map_2d_engine"), 1)
        self.assertEqual(profile.count("install_map_2d_engine"), 1)
        profile_install = profile.index("install_profile_entry_engine")
        self.assertEqual(
            profile[profile_install + 1 : profile_install + 3],
            ["build_map_2d_engine", "install_map_2d_engine"],
        )
        self.assertLess(
            profile.index("install_map_2d_engine"), profile.index("repack_visuals")
        )

        map_installers = [
            row["id"]
            for row in document["steps"]
            if any(
                file.get("destination") == "rom/extracted/game/MAP2D.BIN"
                for file in row.get("files", ())
            )
        ]
        self.assertEqual(map_installers, ["install_map_2d_engine"])

    def test_visual_package_does_not_claim_the_engine_target(self) -> None:
        visual = json.loads(VISUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("MAP2D.BIN", visual["sources"])


if __name__ == "__main__":
    unittest.main()
