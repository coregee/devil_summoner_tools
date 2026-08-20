from __future__ import annotations

import json
import unittest
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ENGINE_ROOT / "config"
PURE_DATA_GENERATORS = {
    "confirmation_label_no",
    "confirmation_label_yes",
    "confirmation_level_too_low",
    "confirmation_main",
    "compendium_data",
    "combat_compatibility_data",
    "combat_debug_data",
    "credits_data",
    "diagnostics_ascii",
    "dungeon_locations",
    "field_messages",
    "fmv_subtitle_data",
    "facilities_status_data",
    "font16_scratch",
    "horoscope_data",
    "analyze_ui_data",
    "level_up_data",
    "map_2d_data",
    "options_data",
    "profile_entry_data",
    "portrait_scene_data",
    "save_load_data",
    "status_data",
    "zero_scratch",
}


def _walk_json(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


class EnginePackageLayoutTests(unittest.TestCase):
    def test_package_root_contains_only_the_build_entrypoint(self) -> None:
        modules = {path.name for path in ENGINE_ROOT.glob("*.py")}

        self.assertEqual(modules, {"__init__.py", "build.py"})

    def test_all_patch_configs_use_readable_version_two_recipes(self) -> None:
        paths = sorted(CONFIG_ROOT.glob("*.json"))
        self.assertTrue(paths)
        forbidden = {"replacement", "replacement_zero_bytes"}
        for path in paths:
            with self.subTest(config=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(document.get("version"), 2)
                for value in _walk_json(document):
                    if isinstance(value, dict):
                        self.assertTrue(forbidden.isdisjoint(value))
                        if "generated" in value:
                            self.assertIn(
                                value["generated"], PURE_DATA_GENERATORS
                            )

    def test_legacy_blob_configuration_loader_is_gone(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ENGINE_ROOT / "core").glob("*.py"))
        )

        self.assertNotIn("PatchConfiguration", source)
        self.assertNotIn("load_patch_configuration", source)


if __name__ == "__main__":
    unittest.main()
