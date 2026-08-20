from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    FMV_SUBTITLES_BUILD_MANIFEST_PATH,
    FMV_SUBTITLES_OUTPUT_PATH,
    build_fmv_subtitle_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"


class FmvSubtitleBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_fmv_subtitle_surface()
        cls.data = cls.outputs[FMV_SUBTITLES_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[FMV_SUBTITLES_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_terminal_event_and_manifest(self) -> None:
        digest = hashlib.sha256(self.data).hexdigest()
        self.assertEqual(self.manifest["surface"], "fmv.subtitles")
        self.assertEqual(self.manifest["base"]["surface"], "facilities.status_ui")
        self.assertEqual(
            self.manifest["output"], {"file": "EVENT.BIN", "sha256": digest}
        )
        self.assertEqual(self.manifest["cues"], 9)
        self.assertEqual(self.manifest["patches"], 9)
        self.assertEqual(self.manifest["patch_groups"], ["fmv.runtime_subtitles"])
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 2454,
                "capacity": 2656,
                "arenas": {
                    "data_primary": {
                        "address": "0x06020000",
                        "bytes": 998,
                        "capacity": 1024,
                    },
                    "code": {
                        "address": "0x060260a8",
                        "bytes": 560,
                        "capacity": 704,
                    },
                    "data_secondary": {
                        "address": "0x06026368",
                        "bytes": 384,
                        "capacity": 408,
                    },
                    "data_tertiary": {
                        "address": "0x06020df8",
                        "bytes": 512,
                        "capacity": 520,
                    },
                },
            },
        )

    def test_manifest_tracks_text_font_assembly_and_unchanged_movie(self) -> None:
        self.assertEqual(
            set(self.manifest["asset_inputs"]), {"assets/text/fmv/subtitles.json"}
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {"saturn/engine/asm/fmv_subtitles/runtime.s"},
        )
        self.assertIn(
            "saturn/font/generated/game/FONT16.FON", self.manifest["runtime_inputs"]
        )
        self.assertIn(
            "saturn/font/generated/game/FONT16_metrics.json",
            self.manifest["runtime_inputs"],
        )
        self.assertIn("game:BGDATA/START2.CPK", self.manifest["source_inputs"])
        self.assertFalse(
            any("START2.CPK" in path.as_posix() for path in self.outputs)
        )

    def test_default_build_runs_fmv_last_before_event_install(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_fmv_subtitles_engine"]["arguments"], ["fmv.subtitles"]
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_fmv_subtitles_engine"), 1)
        self.assertEqual(
            profile[profile.index("build_analyze_engine") + 1 :][:2],
            ["build_fmv_subtitles_engine", "install_event_normcom_engine"],
        )


if __name__ == "__main__":
    unittest.main()
