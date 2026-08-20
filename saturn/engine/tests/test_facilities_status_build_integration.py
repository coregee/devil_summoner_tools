from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import (  # noqa: E402
    EQUIPMENT_BUILD_MANIFEST_PATH,
    EQUIPMENT_EVENT_OUTPUT_PATH,
    FACILITIES_STATUS_BUILD_MANIFEST_PATH,
    FACILITIES_STATUS_OUTPUT_PATH,
    build_facilities_status_surface,
    main,
)


BUILD_CONFIG_PATH = SATURN_ROOT / "build_config.json"
EXTRACTED_ROOT = (SATURN_ROOT / "rom" / "extracted").resolve()
EQUIPMENT_SHA256 = (
    "1ffb315598c74bf0b0cb1a85b68097ba10ed050fdb6b1795ef00f2c8485f695e"
)
OUTPUT_SHA256 = (
    "04926f92d670726412b91f7925cd3086c1e64d09a8344956a544cdc686ba892a"
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FacilitiesStatusBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        original_open = Path.open

        def reject_extracted_input(path: Path, *args: object, **kwargs: object):
            if path.resolve().is_relative_to(EXTRACTED_ROOT):
                raise AssertionError(
                    f"facilities/status engine read mutable extracted input: {path}"
                )
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", reject_extracted_input):
            cls.outputs = build_facilities_status_surface()
        cls.data = cls.outputs[FACILITIES_STATUS_OUTPUT_PATH]
        cls.manifest = json.loads(
            cls.outputs[FACILITIES_STATUS_BUILD_MANIFEST_PATH].decode("utf-8")
        )

    def test_terminal_event_composes_on_a_distinct_equipment_intermediate(self) -> None:
        self.assertNotEqual(
            EQUIPMENT_EVENT_OUTPUT_PATH, FACILITIES_STATUS_OUTPUT_PATH
        )
        self.assertEqual(
            _sha256(self.outputs[EQUIPMENT_EVENT_OUTPUT_PATH]), EQUIPMENT_SHA256
        )
        self.assertEqual(_sha256(self.data), OUTPUT_SHA256)
        self.assertEqual(
            self.manifest["base"],
            {
                "surface": "equipment.ui",
                "sha256": EQUIPMENT_SHA256,
                "manifest_sha256": _sha256(
                    self.outputs[EQUIPMENT_BUILD_MANIFEST_PATH]
                ),
            },
        )
        self.assertEqual(
            self.manifest["output"],
            {"file": "EVENT.BIN", "sha256": OUTPUT_SHA256},
        )

    def test_manifest_records_complete_recipe_and_runtime_ownership(self) -> None:
        self.assertEqual(self.manifest["surface"], "facilities.status_ui")
        self.assertEqual(self.manifest["patches"], 72)
        self.assertEqual(
            self.manifest["patch_groups"],
            [
                "fusion.status_ui",
                "event.term_inserts",
                "facilities.command_ui",
                "bar.status_ui",
                "healer.status_ui",
                "event.fixed_text_compatibility",
            ],
        )
        self.assertEqual(
            self.manifest["runtime"],
            {
                "bytes": 11838,
                "capacity": 12908,
                "arenas": {
                    "event_facilities_status": {
                        "address": "0x06023294",
                        "bytes": 11838,
                        "capacity": 12908,
                    }
                },
            },
        )

    def test_manifest_names_authored_generated_and_verified_inputs(self) -> None:
        self.assertEqual(
            set(self.manifest["asset_inputs"]),
            {
                "assets/text/ui/status.json",
                "assets/text/races.json",
                "assets/text/affinities.json",
                "assets/text/demons.json",
                "assets/text/characters.json",
                "assets/text/magic.json",
                "assets/text/skills.json",
                "assets/text/facilities/bar.json",
                "assets/text/facilities/healer.json",
                "assets/text/facilities/common.json",
            },
        )
        self.assertEqual(len(self.manifest["assembly_inputs"]), 11)
        runtime_inputs = set(self.manifest["runtime_inputs"])
        for expected in (
            "saturn/font/generated/game/FONT8.FON",
            "saturn/font/generated/game/FONT8_metrics.json",
            "saturn/font/generated/game/FONT16.FON",
            "saturn/font/generated/game/FONT16_metrics.json",
            "saturn/text/generated/game/DVLNAME.DAT",
            "saturn/text/generated/game/MAGNAME.DAT",
            "saturn/text/generated/game/comp_menu_build.json",
            "saturn/text/generated/game/battle_ui_build.json",
            "saturn/text/bindings/facilities_bar.json",
            "saturn/text/bindings/facilities_healer.json",
            "saturn/text/corpus/game/addressed/normcom_tables.json",
        ):
            self.assertIn(expected, runtime_inputs)
        self.assertEqual(
            set(self.manifest["source_inputs"]),
            {
                "game:EVENT.BIN",
                "game:DVLNAME.DAT",
                "game:CHARNAME.DAT",
                "game:FONT16.FON",
            },
        )
        paths = {
            *self.manifest["asset_inputs"],
            *runtime_inputs,
            *self.manifest["assembly_inputs"],
        }
        self.assertFalse(
            any(path.startswith("saturn/rom/extracted/") for path in paths)
        )

    def test_default_build_has_one_terminal_event_owner_and_installer(self) -> None:
        document = json.loads(BUILD_CONFIG_PATH.read_text(encoding="utf-8"))
        steps = {row["id"]: row for row in document["steps"]}
        self.assertEqual(
            steps["build_facilities_status_engine"]["check_arguments"],
            ["facilities.status_ui", "--check"],
        )
        profile = document["profiles"]["default"]["steps"]
        self.assertEqual(profile.count("build_facilities_status_engine"), 1)
        self.assertLess(
            profile.index("build_equipment_engine"),
            profile.index("build_facilities_status_engine"),
        )
        self.assertLess(
            profile.index("build_facilities_status_engine"),
            profile.index("install_event_normcom_engine"),
        )

        event_installers = [
            row["id"]
            for row in document["steps"]
            if any(
                file.get("destination") == "rom/extracted/game/EVENT.BIN"
                for file in row.get("files", ())
            )
        ]
        self.assertEqual(event_installers, ["install_event_normcom_engine"])
        install = steps["install_event_normcom_engine"]
        event_source = next(
            row["source"]
            for row in install["files"]
            if row["destination"] == "rom/extracted/game/EVENT.BIN"
        )
        self.assertEqual(event_source, "engine/generated/game/EVENT.BIN")

    def test_cli_dispatches_the_terminal_surface(self) -> None:
        with patch.object(
            sys, "argv", ["build.py", "facilities.status_ui", "--check"]
        ), patch(
            "engine.build.build_facilities_status_surface",
            return_value=self.outputs,
        ) as builder, patch("engine.build._publish") as publish, redirect_stdout(
            io.StringIO()
        ):
            self.assertEqual(main(), 0)
        builder.assert_called_once_with()
        publish.assert_called_once_with(self.outputs, check=True)


if __name__ == "__main__":
    unittest.main()
