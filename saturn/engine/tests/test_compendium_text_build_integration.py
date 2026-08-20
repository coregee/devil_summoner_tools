from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    COMPENDIUM_TEXT_BUILD_PATH,
    COMPENDIUM_TEXT_OUTPUT_ROOT,
    _verify_compendium_text_install,
    build_compendium_text_surface,
)
from engine.surfaces.compendium_text import (  # noqa: E402
    PROFILE_TAIL_BYTES,
    PROFILE_TAIL_OFFSET,
    TARGET,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()


class CompendiumTextBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"compendium engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_compendium_text_surface()
        cls.manifest = json.loads(
            cls.outputs[COMPENDIUM_TEXT_BUILD_PATH].decode("utf-8")
        )

    def test_parent_publishes_every_target_and_one_manifest(self) -> None:
        self.assertEqual(len(self.outputs), 294)
        self.assertEqual(self.manifest["surface"], "compendium.text")
        self.assertEqual(len(self.manifest["outputs"]), 293)
        self.assertEqual(
            set(self.outputs),
            {
                *(
                    COMPENDIUM_TEXT_OUTPUT_ROOT / target
                    for target in self.manifest["outputs"]
                ),
                COMPENDIUM_TEXT_BUILD_PATH,
            },
        )
        self.assertEqual(self.manifest["patches"], 315)
        self.assertEqual(
            self.manifest["patch_groups"],
            [
                "compendium.runtime",
                "compendium.catalogue_text",
                "compendium.drawer_links",
                "compendium.profile_text",
            ],
        )
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 1890,
                "capacity": 30722,
                "arenas": [
                    {
                        "address": "0x0603d200",
                        "bytes": 1890,
                        "capacity": 30722,
                    }
                ],
            },
        )
        self.assertEqual(len(self.manifest["unresolved_physical_ids"]), 2)

    def test_manifest_proves_all_direct_inputs_and_verified_sources(self) -> None:
        self.assertEqual(len(self.manifest["source_inputs"]), 293)
        self.assertIn("compendium:A_DIC.BIN", self.manifest["source_inputs"])
        self.assertEqual(
            set(self.manifest["asset_inputs"]),
            {
                "assets/text/demons.json",
                "assets/text/races.json",
                "assets/text/magic.json",
                "assets/text/skills.json",
                "assets/text/compendium/race_descriptions.json",
                "assets/text/compendium/ui.json",
            },
        )
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {"saturn/engine/asm/compendium_text/compact_drawer.s"},
        )
        runtime = set(self.manifest["runtime_inputs"])
        for expected in (
            "saturn/font/generated/game/FONT8.FON",
            "saturn/font/generated/game/FONT8_metrics.json",
            "saturn/text/config/sources/compendium/manifest.json",
            "saturn/text/corpus/compendium/profiles.json",
            "saturn/text/corpus/compendium/fixed/demon_names.json",
            "saturn/text/corpus/compendium/fixed/ability_names.json",
            "saturn/text/corpus/compendium/addressed/race_names.json",
            "saturn/text/corpus/compendium/fixed/race_descriptions.json",
            "saturn/text/corpus/compendium/fixed/fusion_help.json",
            "saturn/engine/shared/compendium_codec.py",
        ):
            self.assertIn(expected, runtime)
        paths = {
            *self.manifest["asset_inputs"],
            *runtime,
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )

    def test_install_check_allows_profile_images_but_not_text_changes(self) -> None:
        profile = self.outputs[COMPENDIUM_TEXT_OUTPUT_ROOT / "DVL_001.DAT"]
        visual_edit = bytearray(profile)
        visual_edit[0] ^= 0xFF
        _verify_compendium_text_install(
            "DVL_001.DAT", profile, bytes(visual_edit)
        )
        visual_edit[PROFILE_TAIL_OFFSET] ^= 1
        with self.assertRaisesRegex(ValueError, "stale"):
            _verify_compendium_text_install(
                "DVL_001.DAT", profile, bytes(visual_edit)
            )

        a_dic = self.outputs[COMPENDIUM_TEXT_OUTPUT_ROOT / TARGET]
        changed = bytearray(a_dic)
        changed[0] ^= 1
        with self.assertRaisesRegex(ValueError, "stale"):
            _verify_compendium_text_install(TARGET, a_dic, bytes(changed))
        with self.assertRaisesRegex(ValueError, "wrong size"):
            _verify_compendium_text_install(
                "DVL_001.DAT", profile, profile[:-PROFILE_TAIL_BYTES]
            )

    def test_default_plan_builds_and_installs_once_before_visuals(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_compendium_text_engine"]["arguments"],
            ["compendium.text"],
        )
        self.assertEqual(
            steps["install_compendium_text_engine"]["check_arguments"],
            ["compendium.text", "--install", "--check"],
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_compendium_text_engine"), 1)
        self.assertEqual(profile.count("install_compendium_text_engine"), 1)
        install = profile.index("install_fonts")
        self.assertEqual(
            profile[install + 1 : install + 3],
            ["build_compendium_text_engine", "install_compendium_text_engine"],
        )
        self.assertLess(
            profile.index("install_compendium_text_engine"),
            profile.index("repack_visuals"),
        )


if __name__ == "__main__":
    unittest.main()
