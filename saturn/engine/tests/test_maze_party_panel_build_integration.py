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
    FIELD_MESSAGES_BUILD_MANIFEST_PATH,
    FIELD_MESSAGES_OUTPUT_PATH,
    MAZE_PARTY_PANEL_BUILD_MANIFEST_PATH,
    build_maze_party_panel_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MazePartyPanelBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(f"MAZE party build read mutable input: {path}")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted):
            cls.outputs = build_maze_party_panel_surface()
        cls.manifest = json.loads(
            cls.outputs[MAZE_PARTY_PANEL_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_terminal_maze_composes_on_the_checked_field_stage(self) -> None:
        terminal = self.outputs[FIELD_MESSAGES_OUTPUT_PATH]
        field_manifest = self.outputs[FIELD_MESSAGES_BUILD_MANIFEST_PATH]
        self.assertEqual(
            _sha256(terminal),
            "4acac957d02e706eab0e76344e5d82ed1aa672e7ae39d739ad9f40e3d5669b6d",
        )
        self.assertEqual(self.manifest["surface"], "maze.party_panel")
        self.assertEqual(self.manifest["patches"], 5)
        self.assertEqual(self.manifest["patch_groups"], ["maze.party_panel"])
        self.assertEqual(
            self.manifest["base"],
            {
                "surface": "field.messages",
                "sha256": self.manifest["source_inputs"]["composed:MAZE.BIN"],
                "manifest_sha256": _sha256(field_manifest),
            },
        )
        self.assertEqual(
            self.manifest["output"],
            {"file": "MAZE.BIN", "sha256": _sha256(terminal)},
        )
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 2038,
                "capacity": 3072,
                "arenas": [
                    {"address": "0x06022800", "bytes": 574, "capacity": 1024},
                    {"address": "0x06023800", "bytes": 1464, "capacity": 2048},
                ],
            },
        )

    def test_default_plan_has_one_terminal_maze_builder_and_installer(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        profile = document["profiles"]["default"]["steps"]
        self.assertNotIn("build_field_messages_engine", profile)
        start = profile.index("build_maze_party_panel_engine")
        self.assertEqual(
            profile[start:start + 2],
            ["build_maze_party_panel_engine", "install_maze_engine"],
        )
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_maze_party_panel_engine"]["arguments"],
            ["maze.party_panel"],
        )


if __name__ == "__main__":
    unittest.main()
