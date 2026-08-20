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
    HOROSCOPE_BUILD_MANIFEST_PATH,
    HOROSCOPE_OUTPUT_PATH,
    build_horoscope_surface,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
OUTPUT_HASH = "b51a5611e1095387c92baec2a5f8a8965eb47794cab0b774add3eb310f04b041"
STOCK_HASH = "676303bc0382e64429eea5bb5df3a274e83d61fe4ad39490fa4876265910ff72"


class HoroscopeBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(f"horoscope build read mutable input: {path}")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted):
            cls.outputs = build_horoscope_surface()
        cls.data = cls.outputs[HOROSCOPE_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[HOROSCOPE_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_parent_publishes_exact_terminal_output_and_manifest(self) -> None:
        self.assertEqual(
            set(self.outputs),
            {HOROSCOPE_OUTPUT_PATH, HOROSCOPE_BUILD_MANIFEST_PATH},
        )
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), OUTPUT_HASH)
        self.assertEqual(self.manifest["surface"], "horoscope.ui")
        self.assertEqual(
            self.manifest["output"],
            {"file": "HOSI.BIN", "sha256": OUTPUT_HASH},
        )
        self.assertEqual(self.manifest["patches"], 10)
        self.assertEqual(
            self.manifest["patch_groups"], ["horoscope.messages"]
        )
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 668,
                "capacity": 1024,
                "arenas": [
                    {"address": "0x06020400", "bytes": 668, "capacity": 1024}
                ],
            },
        )

    def test_manifest_records_every_direct_and_verified_input(self) -> None:
        self.assertEqual(
            self.manifest["source_inputs"], {"game:HOSI.BIN": STOCK_HASH}
        )
        self.assertEqual(
            set(self.manifest["asset_inputs"]), {"assets/text/ui/horoscope.json"}
        )
        self.assertEqual(self.manifest["assembly_inputs"], {})
        runtime = set(self.manifest["runtime_inputs"])
        for expected in (
            "saturn/font/generated/game/FONT16.FON",
            "saturn/font/generated/game/FONT16_metrics.json",
            "saturn/text/config/surfaces.json",
            "saturn/text/bindings/horoscope.json",
            "saturn/text/corpus/game/fixed/hosi_messages.json",
        ):
            self.assertIn(expected, runtime)
        self.assertFalse(any(path.startswith("saturn/rom/extracted/") for path in runtime))

    def test_default_plan_installs_horoscope_once_before_event_and_visuals(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["install_horoscope_engine"]["files"],
            [
                {
                    "source": "engine/generated/game/HOSI.BIN",
                    "destination": "rom/extracted/game/HOSI.BIN",
                }
            ],
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_horoscope_engine"), 1)
        self.assertEqual(profile.count("install_horoscope_engine"), 1)
        self.assertEqual(
            profile[profile.index("install_map_2d_engine") + 1 :][:2],
            ["build_horoscope_engine", "install_horoscope_engine"],
        )
        self.assertLess(
            profile.index("install_horoscope_engine"), profile.index("repack_visuals")
        )
        installers = [
            row["id"]
            for row in document["steps"]
            if any(
                file.get("destination") == "rom/extracted/game/HOSI.BIN"
                for file in row.get("files", ())
            )
        ]
        self.assertEqual(installers, ["install_horoscope_engine"])


if __name__ == "__main__":
    unittest.main()
