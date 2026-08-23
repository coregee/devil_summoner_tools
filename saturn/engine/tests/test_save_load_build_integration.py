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
    SAVE_LOAD_BUILD_MANIFEST_PATH,
    SAVE_LOAD_OUTPUT_PATHS,
    SAVE_LOAD_VISUAL_MANIFEST_PATH,
    SAVE_LOAD_VISUAL_PREFIX,
    _save_load_visual_spans,
    _verify_save_load_install,
    build_save_load_surface,
)
from engine.surfaces.save_load_ui import TARGETS  # noqa: E402
from visual.util.replacements import load_replacements  # noqa: E402


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
VISUAL_REPLACEMENTS = {
    replacement.view: replacement.path for replacement in load_replacements("game")
}
ENGINE_HASHES = {
    "SAVE.BIN": "3f97ac9b7f40af32c1314a00311a15079c1a402bc0b3822d2b1d90fbab2c5b57",
    "LOAD.BIN": "a9a58b2fa5c4c0e96298c6ec2fcdf84999e695d084556f53c33db3c2afad959f",
}
FINAL_HASHES = {
    "SAVE.BIN": "ccbff9a2dedd4b65c073dd1e59b343602c52f80f2ad431309b23dba86e1c0d31",
    "LOAD.BIN": "13ea4b16836906ae75e5d08d622bd10f513c31bdbf42d7a8930abd99475eb82a",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class SaveLoadBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"SAVE/LOAD engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_save_load_surface()
        cls.manifest = json.loads(cls.outputs[SAVE_LOAD_BUILD_MANIFEST_PATH])
        cls.visual_manifest = json.loads(
            SAVE_LOAD_VISUAL_MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_parent_build_publishes_both_targets_and_one_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {*SAVE_LOAD_OUTPUT_PATHS.values(), SAVE_LOAD_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(self.manifest["surface"], "save_load.ui")
        self.assertEqual(set(self.manifest["outputs"]), set(TARGETS))
        for target in TARGETS:
            data = self.outputs[SAVE_LOAD_OUTPUT_PATHS[target]]
            self.assertEqual(_sha256(data), ENGINE_HASHES[target])
            self.assertEqual(
                self.manifest["outputs"][target],
                {"sha256": ENGINE_HASHES[target]},
            )

        self.assertEqual(
            set(self.manifest["runtime"]["SAVE.BIN"]),
            {"name_strip", "ui", "system_data"},
        )
        self.assertEqual(
            set(self.manifest["runtime"]["LOAD.BIN"]),
            {"name_rebuild", "name_strip", "ui", "system_data"},
        )
        for components in self.manifest["runtime"].values():
            for component in components.values():
                self.assertGreater(component["bytes"], 0)
                self.assertLessEqual(component["bytes"], component["capacity"])

    def test_manifest_names_verified_sources_and_no_downstream_inputs(self) -> None:
        self.assertEqual(
            set(self.manifest["source_inputs"]),
            {"game:SAVE.BIN", "game:LOAD.BIN", "game:MAZE.BIN"},
        )
        paths = {
            *self.manifest["asset_inputs"],
            *self.manifest["runtime_inputs"],
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )
        self.assertFalse(
            any(path.startswith("saturn/visual/modified/") for path in paths)
        )
        for expected in (
            "assets/text/save_load.json",
            "assets/text/locations.json",
            "assets/text/field/location_formats.json",
            "assets/text/player_profile.json",
        ):
            self.assertIn(expected, self.manifest["asset_inputs"])
        self.assertIn(
            "saturn/engine/shared/player_names.py",
            self.manifest["runtime_inputs"],
        )

    def test_default_build_installs_once_immediately_before_visuals(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_save_load_engine"]["arguments"], ["save_load.ui"]
        )
        self.assertEqual(
            steps["install_save_load_engine"],
            {
                "id": "install_save_load_engine",
                "description": (
                    "Install SAVE and LOAD engine bytes before applying their "
                    "visual overlays."
                ),
                "type": "python",
                "script": "engine/build.py",
                "arguments": ["save_load.ui", "--install"],
                "check_arguments": ["save_load.ui", "--install", "--check"],
            },
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_save_load_engine"), 1)
        self.assertEqual(profile.count("install_save_load_engine"), 1)
        visual_index = profile.index("repack_visuals")
        self.assertEqual(
            profile[visual_index - 2 : visual_index + 1],
            [
                "build_save_load_engine",
                "install_save_load_engine",
                "repack_visuals",
            ],
        )

    def test_visual_package_owns_only_four_spans_per_target(self) -> None:
        spans = _save_load_visual_spans()
        self.assertEqual(set(spans), set(TARGETS))
        for target in TARGETS:
            self.assertEqual(len(spans[target]), 4)
            self.assertTrue(
                all(
                    end - start == 104 * 24 * 2
                    for start, end in spans[target]
                )
            )

            expected = self.outputs[SAVE_LOAD_OUTPUT_PATHS[target]]
            visual_only_difference = bytearray(expected)
            for start, end in spans[target]:
                visual_only_difference[start:end] = bytes([0xA5]) * (end - start)
            _verify_save_load_install(
                target, expected, bytes(visual_only_difference), spans[target]
            )

            non_visual_difference = bytearray(visual_only_difference)
            non_visual_difference[0] ^= 1
            with self.assertRaisesRegex(ValueError, "stale non-visual"):
                _verify_save_load_install(
                    target, expected, bytes(non_visual_difference), spans[target]
                )

    def test_visual_overlays_compose_to_the_final_mature_outputs(self) -> None:
        try:
            from PIL import Image
            from visual.util.codec import encode
            from visual.util.model import ImageAsset
        except ModuleNotFoundError:
            self.skipTest("Pillow is required to exercise visual composition")

        rows = [
            row
            for row in self.visual_manifest["images"]
            if row["path"].startswith(SAVE_LOAD_VISUAL_PREFIX)
        ]
        self.assertEqual(len(rows), 4)
        for target in TARGETS:
            composed = bytearray(self.outputs[SAVE_LOAD_OUTPUT_PATHS[target]])
            for row in rows:
                matches = [
                    ImageAsset.from_dict(image)
                    for image in row["targets"]
                    if image["source"] == target
                ]
                self.assertEqual(len(matches), 1)
                with Image.open(VISUAL_REPLACEMENTS[row["path"]]) as image:
                    encode(composed, matches[0], image)
            self.assertEqual(_sha256(bytes(composed)), FINAL_HASHES[target])


if __name__ == "__main__":
    unittest.main()
