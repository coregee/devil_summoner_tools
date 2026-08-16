from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.surfaces.save_load_ui import (  # noqa: E402
    ASSET_FILES,
    CONFIG_PATH,
    ENGINE_ROOT,
    FONT16_PATH,
    FONT8_PATH,
    LOAD_TARGET,
    LOCATION_FORMAT_BINDING_PATH,
    RUNTIME_INPUT_FILES,
    SAVE_TARGET,
    TARGETS,
    _asset_text,
    _configuration,
    _floor_templates,
    _location_text,
    _materialize_capacity,
    _font16_layout,
    _slot_templates,
    _system_component,
    build_save_load_ui,
)


ENGINE_HASHES = {
    SAVE_TARGET: "3f97ac9b7f40af32c1314a00311a15079c1a402bc0b3822d2b1d90fbab2c5b57",
    LOAD_TARGET: "a9a58b2fa5c4c0e96298c6ec2fcdf84999e695d084556f53c33db3c2afad959f",
}
VISUAL_SPANS = {
    SAVE_TARGET: (0x383F0, 0x37070, 0x3FD30, 0x34970),
    LOAD_TARGET: (0x380EC, 0x36D6C, 0x3FA2C, 0x3466C),
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class SaveLoadUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = _configuration()
        cls.build = build_save_load_ui()

    def test_trusted_engine_only_outputs_are_reproduced_exactly(self) -> None:
        self.assertEqual(
            {target: _sha256(self.build.data[target]) for target in TARGETS},
            ENGINE_HASHES,
        )
        self.assertEqual(
            {target: len(self.build.patches[target]) for target in TARGETS},
            {SAVE_TARGET: 48, LOAD_TARGET: 46},
        )

    def test_caves_have_explicit_nonoverlapping_capacity_and_mature_usage(self) -> None:
        self.assertEqual(
            {target: dict(rows) for target, rows in self.build.runtime_used_sizes.items()},
            {
                SAVE_TARGET: {
                    "name_strip": 1486,
                    "ui": 7596,
                    "system_data": 392,
                },
                LOAD_TARGET: {
                    "name_rebuild": 1020,
                    "name_strip": 1486,
                    "ui": 7596,
                    "system_data": 1508,
                },
            },
        )
        self.assertEqual(
            {target: dict(rows) for target, rows in self.build.runtime_capacities.items()},
            {
                SAVE_TARGET: {
                    "name_strip": 0x7C0,
                    "ui": 0x1DAC,
                    "system_data": 392,
                },
                LOAD_TARGET: {
                    "name_rebuild": 0x400,
                    "name_strip": 0x7C0,
                    "ui": 0x1DAC,
                    "system_data": 1508,
                },
            },
        )

    def test_system_data_links_are_anchored_to_the_configured_cave(self) -> None:
        recipe = next(
            row
            for row in self.config.patches[SAVE_TARGET]
            if row.name == "save_system_data"
        )
        with self.assertRaisesRegex(ValueError, "cave contract changed"):
            _system_component(
                SAVE_TARGET,
                replace(recipe, address=recipe.address + 4),
                _font16_layout(),
            )

    def test_executable_payloads_are_owned_by_readable_assembly(self) -> None:
        self.assertEqual(
            {
                path.relative_to(ENGINE_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "asm/save_load_ui/dungeon_hook.s",
                "asm/save_load_ui/dungeon_location_drawer.s",
                "asm/save_load_ui/font16_vwf.s",
                "asm/save_load_ui/load_name_rebuild.s",
                "asm/save_load_ui/name_strip.s",
            },
        )
        module = ENGINE_ROOT / "surfaces" / "save_load_ui.py"
        self.assertNotIn("bytes.fromhex", module.read_text(encoding="utf-8"))
        document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        rows = [row for group in document["groups"] for row in group["patches"]]
        self.assertNotIn("replacement", CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sum("assembly" in row for row in rows), 7)
        self.assertEqual(sum("generated" in row for row in rows), 17)
        generated = {
            group["target"]: {
                row["name"]
                for selected in document["groups"]
                if selected["target"] == group["target"]
                for row in selected["patches"]
                if "generated" in row
            }
            for group in document["groups"]
        }
        self.assertEqual(
            generated[SAVE_TARGET],
            {
                "name_strip_edge_left",
                "name_strip_edge_right",
                "level_prefix",
                "date_separator",
                "time_separator",
                "empty",
                "prompt_overwrite",
                "confirm_yes",
                "confirm_no",
                "prompt_quit_game",
                "save_system_data",
            },
        )
        self.assertEqual(
            generated[LOAD_TARGET],
            {
                "level_prefix",
                "date_separator",
                "time_separator",
                "capacity_number",
                "empty",
                "load_system_data",
            },
        )

    def test_runtime_abi_and_binding_provenance_are_explicit(self) -> None:
        self.assertEqual(
            {path.relative_to(SATURN_ROOT.parent).as_posix() for path in ASSET_FILES},
            {
                "assets/text/save_load.json",
                "assets/text/locations.json",
                "assets/text/field/location_formats.json",
            },
        )
        self.assertIn(FONT16_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(FONT8_PATH, RUNTIME_INPUT_FILES)
        self.assertIn(LOCATION_FORMAT_BINDING_PATH, RUNTIME_INPUT_FILES)
        self.assertEqual(
            set(self.build.source_inputs),
            {"game:SAVE.BIN", "game:LOAD.BIN", "game:MAZE.BIN"},
        )

    def test_all_visible_save_fields_rebuild_from_authored_assets(self) -> None:
        originals = {
            name: _asset_text(name)
            for name in (
                "empty",
                "prompt_overwrite",
                "prompt_quit_game",
                "confirm_yes",
                "confirm_no",
                "slot_name",
                "slot_level",
                "slot_date",
                "slot_time",
                "save_write_failure",
                "save_capacity_error",
                "save_capacity_failure",
                "start_without_save_warning",
                "insufficient_free_space_instructions",
                "load_failure",
                "capacity_number",
            )
        }
        edits = {
            "empty": "BLANK",
            "prompt_overwrite": "Replace?",
            "prompt_quit_game": "Quit now?",
            "confirm_yes": "YEP",
            "confirm_no": "NAY",
            "slot_name": "{first_name}-{last_name}",
            "slot_level": "LV{level}",
            "slot_date": "{day}-{month}",
            "slot_time": "{hour}.{minute}",
            "save_write_failure": "Save failed.{n}Try again.",
            "save_capacity_error": "No save space.{n}Need {capacity_blocks} blocks.",
            "save_capacity_failure": "Save failed.{n}{capacity_blocks} blocks needed.",
            "start_without_save_warning": "Saving is unavailable.{n}Press START to continue.",
            "insufficient_free_space_instructions": "Need {capacity_blocks} blocks.{n}Free space and restart.",
            "load_failure": "Load failed.{n}Try again.",
            "capacity_number": "128",
        }

        def edited_text(name: str) -> str:
            value = edits.get(name, originals[name])
            return value.replace("{capacity_blocks}", edits["capacity_number"])

        with patch(
            "engine.surfaces.save_load_ui._asset_text", side_effect=edited_text
        ):
            changed = build_save_load_ui()
        for target in TARGETS:
            self.assertNotEqual(changed.data[target], self.build.data[target])
        save = {row.name: row for row in changed.patches[SAVE_TARGET]}
        load = {row.name: row for row in changed.patches[LOAD_TARGET]}
        for name in (
            "empty",
            "prompt_overwrite",
            "prompt_quit_game",
            "confirm_yes",
            "confirm_no",
            "level_prefix",
            "date_separator",
            "time_separator",
            "save_name_strip",
            "save_system_data",
        ):
            self.assertNotEqual(save[name].replacement, save[name].expected)
        for name in (
            "empty",
            "level_prefix",
            "date_separator",
            "time_separator",
            "capacity_number",
            "load_name_rebuild",
            "load_name_strip",
            "load_system_data",
        ):
            self.assertNotEqual(load[name].replacement, load[name].expected)

    def test_capacity_substitution_is_token_safe(self) -> None:
        self.assertEqual(
            _materialize_capacity(
                "Literal {{capacity_blocks}}; use {capacity_blocks}.", "129"
            ),
            "Literal {capacity_blocks}; use 129.",
        )
        with self.assertRaisesRegex(ValueError, "must contain one"):
            _materialize_capacity("Literal {{capacity_blocks}} only.", "129")

    def test_slot_name_compiler_is_honest_about_fixed_field_order(self) -> None:
        original = _asset_text

        def reversed_name(name: str) -> str:
            return (
                "{last_name}, {first_name}"
                if name == "slot_name"
                else original(name)
            )

        with patch(
            "engine.surfaces.save_load_ui._asset_text", side_effect=reversed_name
        ), self.assertRaisesRegex(ValueError, "first_name"):
            _slot_templates(_font16_layout())

    def test_slot_name_separator_must_exist_in_the_generated_font(self) -> None:
        original = _asset_text

        def unsupported_separator(name: str) -> str:
            return (
                "{first_name}\t{last_name}"
                if name == "slot_name"
                else original(name)
            )

        with patch(
            "engine.surfaces.save_load_ui._asset_text",
            side_effect=unsupported_separator,
        ), self.assertRaisesRegex(ValueError, "supported ASCII glyph"):
            _slot_templates(_font16_layout())

    def test_location_and_floor_template_edits_rebuild_both_ui_caves(self) -> None:
        dungeon, special = _location_text()
        changed_dungeon = ("Archives", *dungeon[1:])
        changed_special = ("Safe House", *special[1:])
        with patch(
            "engine.surfaces.save_load_ui._location_text",
            return_value=(changed_dungeon, changed_special),
        ):
            changed_locations = build_save_load_ui()

        formats = dict(_floor_templates())
        formats["save_load_basement"] = "{location} B{floor}"
        formats["save_load_above_ground"] = "{location} {floor}"
        with patch(
            "engine.surfaces.save_load_ui._floor_templates",
            return_value=formats,
        ):
            changed_formats = build_save_load_ui()

        for target in TARGETS:
            original = next(
                row
                for row in self.build.patches[target]
                if row.name.endswith("ui_runtime")
            )
            location_cave = next(
                row
                for row in changed_locations.patches[target]
                if row.name.endswith("ui_runtime")
            )
            format_cave = next(
                row
                for row in changed_formats.patches[target]
                if row.name.endswith("ui_runtime")
            )
            self.assertNotEqual(location_cave.replacement, original.replacement)
            self.assertNotEqual(format_cave.replacement, original.replacement)
            self.assertEqual(len(location_cave.replacement), len(original.replacement))
            self.assertEqual(len(format_cave.replacement), len(original.replacement))

    def test_basement_scaffold_is_proven_dormant_under_both_live_hooks(self) -> None:
        scaffold = 0x06071B8A
        self.assertNotIn(
            scaffold,
            {
                recipe.address
                for target in TARGETS
                for recipe in self.config.patches[target]
            },
        )
        for target in TARGETS:
            hook = next(
                patch
                for patch in self.build.patches[target]
                if patch.name == "dungeon_hook"
            )
            # mov.l literal,r0 / jmp @r0 / nop / aligned absolute pointer.
            self.assertEqual(hook.replacement[:6], bytes.fromhex("d001402b0009"))
            destination = int.from_bytes(hook.replacement[-4:], "big")
            ui = next(
                patch
                for patch in self.build.patches[target]
                if patch.name.endswith("ui_runtime")
            )
            self.assertTrue(ui.address <= destination < ui.address + len(ui.replacement))

    def test_engine_surface_never_owns_visual_storage_selector_spans(self) -> None:
        for target in TARGETS:
            for offset in VISUAL_SPANS[target]:
                span = range(0x06020000 + offset, 0x06020000 + offset + 104 * 24 * 2)
                self.assertFalse(
                    any(patch.address in span for patch in self.build.patches[target])
                )


if __name__ == "__main__":
    unittest.main()
