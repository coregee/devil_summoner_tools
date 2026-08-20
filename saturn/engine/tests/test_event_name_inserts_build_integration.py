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
    EQUIPMENT_BUILD_MANIFEST_PATH,
    EQUIPMENT_EVENT_OUTPUT_PATH,
    EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH,
    EVENT_NAME_INSERTS_OUTPUT_PATH,
    FUSION_BUILD_MANIFEST_PATH,
    FUSION_OUTPUT_PATH,
    build_equipment_surface,
    build_event_name_inserts_surface,
)


FUSION_SHA256 = (
    "906ffa353eceb0e09ad10f5dde4cbdc08e469dfe11e43d1ff653b2c004f4d826"
)
NAME_INSERTS_SHA256 = (
    "587683072bb86e91085d752c0ea7399182667a417c2618754888e687e93679f6"
)
EQUIPMENT_INTERMEDIATE_SHA256 = (
    "1ffb315598c74bf0b0cb1a85b68097ba10ed050fdb6b1795ef00f2c8485f695e"
)


class EventNameInsertsBuildIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_event_name_inserts_surface()
        cls.data = cls.outputs[EVENT_NAME_INSERTS_OUTPUT_PATH]
        cls.manifest_bytes = cls.outputs[EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH]
        cls.manifest = json.loads(cls.manifest_bytes.decode("utf-8"))

    def test_adapter_has_a_distinct_checkable_intermediate(self) -> None:
        self.assertNotEqual(
            EVENT_NAME_INSERTS_OUTPUT_PATH, EQUIPMENT_EVENT_OUTPUT_PATH
        )
        self.assertEqual(
            hashlib.sha256(self.outputs[FUSION_OUTPUT_PATH]).hexdigest(),
            FUSION_SHA256,
        )
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), NAME_INSERTS_SHA256)
        self.assertIn(FUSION_BUILD_MANIFEST_PATH, self.outputs)
        self.assertIn(EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH, self.outputs)

    def test_manifest_records_fusion_base_shared_abi_and_cave_capacity(self) -> None:
        self.assertEqual(self.manifest["surface"], "event.name_inserts")
        self.assertEqual(
            self.manifest["base"],
            {
                "surface": "fusion.menu",
                "sha256": FUSION_SHA256,
                "manifest_sha256": hashlib.sha256(
                    self.outputs[FUSION_BUILD_MANIFEST_PATH]
                ).hexdigest(),
            },
        )
        self.assertEqual(
            self.manifest["runtime"], {"bytes": 86, "capacity": 96}
        )
        self.assertEqual(self.manifest["patches"], 15)
        self.assertTrue(
            any(
                path.endswith("engine/shared/player_names.py")
                for path in self.manifest["runtime_inputs"]
            )
        )

    def test_equipment_consumes_adapter_and_publishes_distinct_intermediate(self) -> None:
        equipment = build_equipment_surface()
        manifest = json.loads(equipment[EQUIPMENT_BUILD_MANIFEST_PATH])
        self.assertEqual(
            hashlib.sha256(equipment[EQUIPMENT_EVENT_OUTPUT_PATH]).hexdigest(),
            EQUIPMENT_INTERMEDIATE_SHA256,
        )
        self.assertEqual(
            manifest["bases"]["EVENT.BIN"],
            {
                "surface": "event.name_inserts",
                "sha256": NAME_INSERTS_SHA256,
                "manifest_sha256": hashlib.sha256(
                    equipment[EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH]
                ).hexdigest(),
            },
        )

    def test_default_build_orders_adapter_between_fusion_and_equipment(self) -> None:
        config = json.loads((SATURN_ROOT / "build_config.json").read_text("utf-8"))
        steps = {row["id"]: row for row in config["steps"]}
        self.assertEqual(
            steps["build_event_name_inserts_engine"]["check_arguments"],
            ["event.name_inserts", "--check"],
        )
        profile = config["profiles"]["default"]["steps"]
        self.assertLess(
            profile.index("build_fusion_engine"),
            profile.index("build_event_name_inserts_engine"),
        )
        self.assertLess(
            profile.index("build_event_name_inserts_engine"),
            profile.index("build_equipment_engine"),
        )


if __name__ == "__main__":
    unittest.main()
