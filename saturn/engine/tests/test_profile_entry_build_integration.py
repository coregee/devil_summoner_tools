from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    PROFILE_ENTRY_BUILD_MANIFEST_PATH,
    PROFILE_ENTRY_OUTPUT_PATH,
    build_profile_entry_surface,
    install_profile_entry_surface,
)


EXPECTED_OUTPUT_SHA256 = (
    "bde4ea3bd7edd9bd9427aeaed68637bb597163a6c1db73e3d720222d5ebf8397"
)
STOCK_NAME_SHA256 = (
    "cafacc4bfdd8dd1d3255d48814829e564926f6425576b82de45b54310ebcb538"
)


class ProfileEntryBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_profile_entry_surface()
        cls.data = cls.outputs[PROFILE_ENTRY_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[PROFILE_ENTRY_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_one_terminal_target_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {PROFILE_ENTRY_OUTPUT_PATH, PROFILE_ENTRY_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(
            hashlib.sha256(self.data).hexdigest(), EXPECTED_OUTPUT_SHA256
        )
        self.assertEqual(
            self.manifest["output"],
            {"file": "NAME.BIN", "sha256": EXPECTED_OUTPUT_SHA256},
        )

    def test_manifest_records_stock_provenance_and_owned_region(self) -> None:
        self.assertEqual(self.manifest["surface"], "profile_entry.ui")
        self.assertEqual(
            self.manifest["source_inputs"], {"game:NAME.BIN": STOCK_NAME_SHA256}
        )
        self.assertEqual(
            self.manifest["runtime"], {"bytes": 5112, "capacity": 6840}
        )
        self.assertEqual(self.manifest["patches"], 22)
        self.assertTrue(self.manifest["asset_inputs"])
        self.assertTrue(self.manifest["runtime_inputs"])
        self.assertTrue(self.manifest["assembly_inputs"])

    def test_build_profile_runs_after_fonts_and_installs_before_event_stages(self) -> None:
        config = json.loads((SATURN_ROOT / "build_config.json").read_text("utf-8"))
        steps = {row["id"]: row for row in config["steps"]}
        self.assertEqual(
            steps["build_profile_entry_engine"],
            {
                "id": "build_profile_entry_engine",
                "description": (
                    "Build the complete Profile Entry controller and data from "
                    "authored text and generated fonts."
                ),
                "type": "python",
                "script": "engine/build.py",
                "arguments": ["profile_entry.ui"],
                "check_arguments": ["profile_entry.ui", "--check"],
            },
        )
        self.assertEqual(
            steps["install_profile_entry_engine"]["check_arguments"],
            ["profile_entry.ui", "--install", "--check"],
        )
        profile = config["profiles"]["default"]["steps"]
        self.assertLess(
            profile.index("install_fonts"),
            profile.index("build_profile_entry_engine"),
        )
        self.assertLess(
            profile.index("build_profile_entry_engine"),
            profile.index("install_profile_entry_engine"),
        )
        self.assertLess(
            profile.index("install_profile_entry_engine"),
            profile.index("build_fusion_engine"),
        )

    def test_install_is_exact_and_check_rejects_stale_name_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated" / "NAME.BIN"
            installed = root / "installed" / "NAME.BIN"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(self.data)
            with patch("engine.build.PROFILE_ENTRY_OUTPUT_PATH", generated), patch(
                "engine.build.PROFILE_ENTRY_INSTALL_PATH", installed
            ):
                install_profile_entry_surface(check=False)
                self.assertEqual(installed.read_bytes(), self.data)
                install_profile_entry_surface(check=True)
                installed.write_bytes(self.data[:-1] + bytes((self.data[-1] ^ 1,)))
                with self.assertRaisesRegex(ValueError, "stale Profile Entry"):
                    install_profile_entry_surface(check=True)


if __name__ == "__main__":
    unittest.main()
