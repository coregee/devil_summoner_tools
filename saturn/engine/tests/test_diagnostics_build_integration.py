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
    DIAGNOSTICS_BUILD_MANIFEST_PATH,
    DIAGNOSTICS_OUTPUT_PATHS,
    build_diagnostics_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()


class DiagnosticsBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(f"diagnostics build read mutable input: {path}")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted):
            cls.outputs = build_diagnostics_surface()
        cls.manifest = json.loads(
            cls.outputs[DIAGNOSTICS_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_both_outputs_and_complete_provenance(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {*DIAGNOSTICS_OUTPUT_PATHS.values(), DIAGNOSTICS_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(self.manifest["surface"], "diagnostics.ui")
        self.assertEqual(self.manifest["patches"], 11)
        self.assertEqual(
            self.manifest["patch_groups"],
            ["diagnostics.sound_test", "diagnostics.test_3d"],
        )
        self.assertEqual(self.manifest["runtime"], {"bytes": 0, "capacity": 0, "arenas": []})
        for target, output_path in DIAGNOSTICS_OUTPUT_PATHS.items():
            self.assertEqual(
                self.manifest["outputs"][target]["sha256"],
                hashlib.sha256(self.outputs[output_path]).hexdigest(),
            )
        self.assertEqual(
            set(self.manifest["asset_inputs"]),
            {
                "assets/text/diagnostics/sound_test.json",
                "assets/text/diagnostics/test_3d.json",
            },
        )
        self.assertEqual(self.manifest["assembly_inputs"], {})

    def test_default_plan_builds_and_installs_each_target_once(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_diagnostics_engine"), 1)
        self.assertEqual(profile.count("install_diagnostics_engine"), 1)
        self.assertEqual(
            profile[
                profile.index("install_credits_engine") + 1 :
                profile.index("repack_event_text")
            ],
            ["build_diagnostics_engine", "install_diagnostics_engine"],
        )
        install = next(
            step
            for step in document["steps"]
            if step["id"] == "install_diagnostics_engine"
        )
        self.assertEqual(
            {row["destination"] for row in install["files"]},
            {
                "rom/extracted/game/SNDTEST.BIN",
                "rom/extracted/game/TEST3D.BIN",
            },
        )


if __name__ == "__main__":
    unittest.main()
