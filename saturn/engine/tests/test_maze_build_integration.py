from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH,
    DUNGEON_LOCATIONS_MAZE_PATH,
    FIELD_MESSAGES_BUILD_MANIFEST_PATH,
    FIELD_MESSAGES_OUTPUT_PATH,
    GENERATED_ROOT,
    build_dungeon_locations_surface,
    build_field_messages_surface,
)
from engine.surfaces.dungeon_locations import (  # noqa: E402
    MAZE_TARGET,
    _configuration,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _generated_path(target: str) -> Path:
    return GENERATED_ROOT.joinpath(*PurePosixPath(target).parts)


class MazeBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = _configuration()

        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            resolved = path.resolve()
            if resolved.is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(f"engine build read mutable extracted input: {path}")
            return original_open(path, *args, **kwargs)

        # These are real end-to-end surface builds. Rejecting every open below the
        # editable mirror proves they continue to read stock files from the disc.
        with patch.object(Path, "open", reject_extracted_input):
            cls.location_outputs = build_dungeon_locations_surface()
            cls.field_outputs = build_field_messages_surface()

        cls.location_manifest = json.loads(
            cls.location_outputs[DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH]
        )
        cls.field_manifest = json.loads(
            cls.field_outputs[FIELD_MESSAGES_BUILD_MANIFEST_PATH]
        )

    def test_parent_installs_exactly_the_117_declared_location_targets(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {step["id"]: step for step in document["steps"]}
        install = steps["install_maze_engine"]
        files = install["files"]

        self.assertEqual(len(files), 117)
        self.assertEqual(len({row["source"] for row in files}), 117)
        self.assertEqual(len({row["destination"] for row in files}), 117)

        source_prefix = "engine/generated/game/"
        destination_prefix = "rom/extracted/game/"
        installed: set[str] = set()
        for row in files:
            self.assertTrue(row["source"].startswith(source_prefix))
            self.assertTrue(row["destination"].startswith(destination_prefix))
            source_target = row["source"].removeprefix(source_prefix)
            destination_target = row["destination"].removeprefix(destination_prefix)
            self.assertEqual(source_target, destination_target)
            installed.add(source_target)

        self.assertEqual(installed, set(self.config.targets))
        self.assertNotIn(
            "engine/generated/game/dungeon_locations/MAZE.BIN",
            {row["source"] for row in files},
        )
        self.assertNotIn("build_dungeon_locations_engine", steps)
        self.assertNotIn("build_field_messages_engine", steps)
        self.assertEqual(
            steps["build_maze_party_panel_engine"]["arguments"],
            ["maze.party_panel"],
        )
        profile = document["profiles"]["default"]["steps"]
        start = profile.index("build_maze_party_panel_engine")
        self.assertEqual(
            profile[start : start + 2],
            [
                "build_maze_party_panel_engine",
                "install_maze_engine",
            ],
        )

    def test_maze_stage_and_terminal_output_have_distinct_owners(self) -> None:
        location_paths = {
            _generated_path(target)
            for target in self.config.targets
            if target != MAZE_TARGET
        } | {
            DUNGEON_LOCATIONS_MAZE_PATH,
            DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH,
        }
        self.assertEqual(set(self.location_outputs), location_paths)
        self.assertEqual(len(self.location_outputs), 118)
        self.assertNotIn(FIELD_MESSAGES_OUTPUT_PATH, self.location_outputs)

        field_paths = location_paths | {
            FIELD_MESSAGES_OUTPUT_PATH,
            FIELD_MESSAGES_BUILD_MANIFEST_PATH,
        }
        self.assertEqual(set(self.field_outputs), field_paths)
        self.assertEqual(len(self.field_outputs), 120)
        for path in location_paths:
            self.assertEqual(self.field_outputs[path], self.location_outputs[path])

        staged_maze = self.location_outputs[DUNGEON_LOCATIONS_MAZE_PATH]
        terminal_maze = self.field_outputs[FIELD_MESSAGES_OUTPUT_PATH]
        self.assertNotEqual(terminal_maze, staged_maze)

        self.assertEqual(self.location_manifest["surface"], "dungeon.locations")
        self.assertEqual(self.location_manifest["targets"], 117)
        self.assertEqual(self.location_manifest["patches"], 302)
        self.assertEqual(
            set(self.location_manifest["outputs"]), set(self.config.targets)
        )
        self.assertEqual(
            self.location_manifest["outputs"][MAZE_TARGET]["sha256"],
            _sha256(staged_maze),
        )

        self.assertEqual(self.field_manifest["surface"], "field.messages")
        self.assertEqual(
            self.field_manifest["base"],
            {
                "surface": "dungeon.locations",
                "sha256": _sha256(staged_maze),
                "manifest_sha256": _sha256(
                    self.location_outputs[DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH]
                ),
            },
        )
        self.assertEqual(
            self.field_manifest["output"],
            {"file": MAZE_TARGET, "sha256": _sha256(terminal_maze)},
        )

    def test_manifests_name_only_verified_disc_or_immutable_build_inputs(self) -> None:
        self.assertEqual(
            set(self.location_manifest["source_inputs"]),
            {f"game:{target}" for target in self.config.targets},
        )
        self.assertEqual(
            set(self.field_manifest["source_inputs"]),
            {MAZE_TARGET},
        )
        manifest_paths = {
            *self.location_manifest["asset_inputs"],
            *self.location_manifest["runtime_inputs"],
            *self.location_manifest["assembly_inputs"],
            *self.field_manifest["asset_inputs"],
            *self.field_manifest["runtime_inputs"],
            *self.field_manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in manifest_paths)
        )


if __name__ == "__main__":
    unittest.main()
