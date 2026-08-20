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
    CREDITS_BUILD_MANIFEST_PATH,
    CREDITS_OUTPUT_PATH,
    build_credits_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
VISUAL_MANIFEST_PATH = SATURN_ROOT / "visual" / "modified" / "game" / "manifest.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
OUTPUT_HASH = "cb9059287736d1c173c8fd2a3757409a8fd2f80cf23d5880c310df9a7f618a42"
STOCK_HASH = "b72559e959c0e4392557b540f9bd09652cb06d9c061a160f9274e2f2fed63b5f"


class CreditsBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(f"credits build read mutable input: {path}")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted):
            cls.outputs = build_credits_surface()
        cls.data = cls.outputs[CREDITS_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[CREDITS_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_exact_output_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs), {CREDITS_OUTPUT_PATH, CREDITS_BUILD_MANIFEST_PATH}
        )
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), OUTPUT_HASH)
        self.assertEqual(self.manifest["surface"], "credits.ui")
        self.assertEqual(
            self.manifest["output"],
            {"file": "END_ROLL.BIN", "sha256": OUTPUT_HASH},
        )
        self.assertEqual(self.manifest["patches"], 10)
        self.assertEqual(
            self.manifest["patch_groups"],
            ["credits.runtime", "credits.main", "credits.test"],
        )
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 8528,
                "capacity": 23888,
                "arenas": [
                    {"address": "0x06025000", "bytes": 8528, "capacity": 23888}
                ],
            },
        )

    def test_provenance_is_complete_and_visuals_do_not_own_end_roll(self) -> None:
        self.assertEqual(
            self.manifest["source_inputs"], {"game:END_ROLL.BIN": STOCK_HASH}
        )
        self.assertEqual(
            set(self.manifest["asset_inputs"]), {"assets/text/credits/names.json"}
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {
                "saturn/engine/asm/credits_ui/main_hook.s",
                "saturn/engine/asm/credits_ui/renderer.s",
                "saturn/engine/asm/credits_ui/test_wrapper.s",
                "saturn/engine/asm/credits_ui/trampoline.s",
            },
        )
        runtime = set(self.manifest["runtime_inputs"])
        self.assertIn("saturn/text/bindings/end_roll_credits.json", runtime)
        self.assertIn(
            "saturn/text/corpus/game/addressed/end_roll_names.json", runtime
        )
        visual = json.loads(VISUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("END_ROLL.BIN", visual["sources"])

    def test_default_plan_installs_once_after_horoscope_before_diagnostics(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_credits_engine"), 1)
        self.assertEqual(profile.count("install_credits_engine"), 1)
        self.assertEqual(
            profile[
                profile.index("install_horoscope_engine") + 1 :
                profile.index("build_diagnostics_engine")
            ],
            ["build_credits_engine", "install_credits_engine"],
        )
        installers = [
            row["id"]
            for row in document["steps"]
            if any(
                item.get("destination") == "rom/extracted/game/END_ROLL.BIN"
                for item in row.get("files", ())
            )
        ]
        self.assertEqual(installers, ["install_credits_engine"])


if __name__ == "__main__":
    unittest.main()
