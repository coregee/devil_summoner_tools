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

from engine.surfaces.dungeon_locations import (  # noqa: E402
    AUTOMAP_TARGET,
    CONFIG_PATH,
    ENGINE_ROOT,
    MAZE_TARGET,
    PRIMARY_TARGETS,
    _configuration,
    _elevator_format,
    _font16_metrics,
    _location_text,
    _marker_text,
    _mirror_text,
    _source_files,
    build_dungeon_locations,
)


MAIN_OUTPUT_SHA256 = {
    MAZE_TARGET: "7f85c7dd54c89d403b33aed18db627cb0ec1666f74283438e4fe6d8cc82a7a7d",
    AUTOMAP_TARGET: "d57132654f52e413e0643839919088c5a6534f8ad09be534800964cc2bff4023",
}
RUNTIME_SHA256 = {
    MAZE_TARGET: "c3d082bc146ee7b5332ee3f157528191491a9394b2542317d94cb6c461a5038d",
    AUTOMAP_TARGET: "bf288f8cb05ceb6905c45f8cbdf86df688d06f564f57994d1f6dc3eb451e1fec",
}
MIRROR_CATALOGS = {
    "dungeon_location_landing_mirrors": {
        "count": 17,
        "patches": 56,
        "source": "2cc2323095843025361fb1aa065bb99453ba6e8e8971ae00f98ddbbbab68dc3e",
        "output": "07eb6da28da34a6d11c04038cb63f8dc199c01fd06a2ce577d182f4cf49e683a",
    },
    "dungeon_location_kai_mirrors": {
        "count": 98,
        "patches": 232,
        "source": "48eb224fbd6cccbdcb182099485116c4c92b3f85c4f0d44fb92039e1593ffd6a",
        "output": "fa921908520007f2ed4628605ad9cd5c0033359e3ce39a061eb08c29314cdb43",
    },
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _catalog(names: list[str], values: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(Path(name).name.encode("ascii"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(values[name])))
    return digest.hexdigest()


class DungeonLocationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = _configuration()
        cls.sources = dict(_source_files(cls.config))
        cls.build = build_dungeon_locations(cls.sources)

    def test_proven_main_outputs_are_reproduced_exactly(self) -> None:
        self.assertEqual(
            {
                target: _sha256(self.build.outputs[target])
                for target in PRIMARY_TARGETS
            },
            MAIN_OUTPUT_SHA256,
        )
        self.assertEqual(
            {
                target: _sha256(self.build.runtime_used[target])
                for target in PRIMARY_TARGETS
            },
            RUNTIME_SHA256,
        )
        self.assertEqual(
            {target: len(self.build.runtime_used[target]) for target in PRIMARY_TARGETS},
            {MAZE_TARGET: 8728, AUTOMAP_TARGET: 9296},
        )
        self.assertEqual(
            {target: len(self.build.labels[target]) for target in PRIMARY_TARGETS},
            {MAZE_TARGET: 30, AUTOMAP_TARGET: 30},
        )

    def test_every_mirror_matches_the_mature_aggregate_oracle(self) -> None:
        for group, oracle in MIRROR_CATALOGS.items():
            targets = [
                target
                for target, recipes in self.config.patches.items()
                if recipes[0].group == group
            ]
            self.assertEqual(len(targets), oracle["count"])
            self.assertEqual(
                sum(len(self.config.patches[target]) for target in targets),
                oracle["patches"],
            )
            self.assertEqual(_catalog(targets, self.sources), oracle["source"])
            self.assertEqual(_catalog(targets, self.build.outputs), oracle["output"])

    def test_patch_inventory_is_typed_and_physically_explicit(self) -> None:
        source = CONFIG_PATH.read_text(encoding="utf-8")
        document = json.loads(source)
        rows = [row for group in document["groups"] for row in group["patches"]]
        self.assertEqual(document["version"], 2)
        self.assertEqual(document["surface"], "dungeon.locations")
        self.assertEqual(len(document["targets"]), 117)
        self.assertEqual(len(rows), 302)
        self.assertNotIn('"replacement"', source)
        self.assertEqual(
            {
                key: sum(key in row for row in rows)
                for key in (
                    "assembly",
                    "generated",
                    "linked_pointer",
                    "instruction",
                    "pointer",
                )
            },
            {
                "assembly": 4,
                "generated": 290,
                "linked_pointer": 8,
                "instruction": 0,
                "pointer": 0,
            },
        )
        cave_sizes = {
            target: len(
                next(
                    recipe.expected
                    for recipe in self.config.patches[target]
                    if recipe.name == "renderer_cave"
                )
            )
            for target in PRIMARY_TARGETS
        }
        self.assertEqual(cave_sizes, {MAZE_TARGET: 0x2400, AUTOMAP_TARGET: 0x6100})

    def test_mirror_binding_owns_every_configured_selector(self) -> None:
        translations = _mirror_text(self.config)
        self.assertEqual(len(translations), 288)
        self.assertEqual(
            sum(
                len(patches)
                for target, patches in self.build.patches.items()
                if target not in PRIMARY_TARGETS
            ),
            len(translations),
        )

    def test_runtime_executable_is_owned_by_readable_assembly(self) -> None:
        self.assertEqual(
            {
                path.relative_to(ENGINE_ROOT).as_posix()
                for path in self.build.assembly_files
            },
            {
                "asm/dungeon_locations/automap_wrapper.s",
                "asm/dungeon_locations/elevator_surface.s",
                "asm/dungeon_locations/floor_compositor.s",
                "asm/dungeon_locations/floor_hook.s",
                "asm/dungeon_locations/marker_ui.s",
                "asm/dungeon_locations/maze_wrapper.s",
            },
        )
        module = ENGINE_ROOT / "surfaces" / "dungeon_locations.py"
        module_source = module.read_text(encoding="utf-8")
        self.assertNotIn("bytes.fromhex", module_source)
        self.assertNotIn(".glob(", module_source)
        compositor = ENGINE_ROOT / "asm" / "dungeon_locations" / "floor_compositor.s"
        compositor_source = compositor.read_text(encoding="utf-8")
        self.assertIn("CODE_NEGATIVE_PREFIX", compositor_source)
        self.assertIn("CODE_SUFFIX", compositor_source)
        self.assertNotIn("CODE_B", compositor_source)
        self.assertNotIn("CODE_F", compositor_source)

    def test_elevator_owns_a_distinct_vwf_format_and_drawer_link(self) -> None:
        asset = json.loads(
            (
                ENGINE_ROOT.parents[1]
                / "assets"
                / "text"
                / "field"
                / "elevator.json"
            ).read_text(encoding="utf-8")
        )
        entries = asset["entries"]
        self.assertEqual(entries["lower_symbol"]["text"]["translation"], "B")
        self.assertEqual(entries["floor_symbol"]["text"]["translation"], "F")
        self.assertEqual(
            entries["floor_definition"]["text"]["translation"],
            "{lower_symbol}{floor_number}{floor_symbol}",
        )
        pointer = next(
            patch
            for patch in self.build.patches[MAZE_TARGET]
            if patch.name == "elevator_drawer_pointer"
        )
        self.assertEqual(pointer.address, 0x0603CFC4)
        self.assertEqual(pointer.expected, bytes.fromhex("0603fcfc"))
        entry = int.from_bytes(pointer.replacement, "big")
        self.assertTrue(0x06020400 <= entry < 0x06022800)

        source = (
            ENGINE_ROOT / "asm" / "dungeon_locations" / "elevator_surface.s"
        ).read_text(encoding="utf-8")
        self.assertIn("ELEVATOR_CODE_LOWER", source)
        self.assertIn("ELEVATOR_CODE_FLOOR", source)
        self.assertIn("ELEVATOR_PART_0", source)

        values = {
            "lower_symbol": "B",
            "floor_symbol": "F",
            "floor_definition": "{floor_symbol}{floor_number}{lower_symbol}",
        }
        with patch(
            "engine.surfaces.dungeon_locations._surface_text",
            side_effect=lambda _asset, entry: values[entry],
        ):
            reordered = _elevator_format(_font16_metrics())
        self.assertEqual(reordered.parts, (3, 2, 1))

    def test_tables_use_selectors_without_overwriting_floor_metadata(self) -> None:
        for target in PRIMARY_TARGETS:
            table_patch = next(
                patch
                for patch in self.build.patches[target]
                if patch.name == "location_table"
            )
            for index in range(144):
                start = index * 0x20
                self.assertEqual(
                    table_patch.replacement[start],
                    table_patch.expected[start],
                )
                selector = int.from_bytes(
                    table_patch.replacement[start + 2 : start + 4], "big"
                )
                self.assertTrue(0x7E00 <= selector < 0x7F00)
                self.assertEqual(
                    table_patch.replacement[start + 4 : start + 12],
                    bytes(8),
                )

    def test_authored_name_edits_rebuild_runtime_with_mirrors_bound(self) -> None:
        texts, aliases = _location_text()
        old = "Library"
        new = "Library Annex"
        changed_texts = tuple(new if value == old else value for value in texts)
        mirrors = _mirror_text(self.config)
        changed_mirrors = {
            key: new if value == old else value for key, value in mirrors.items()
        }
        with patch(
            "engine.surfaces.dungeon_locations._location_text",
            return_value=(changed_texts, aliases),
        ), self.assertRaisesRegex(ValueError, "unknown landing location"):
            build_dungeon_locations(self.sources)
        with patch(
            "engine.surfaces.dungeon_locations._location_text",
            return_value=(changed_texts, aliases),
        ), patch(
            "engine.surfaces.dungeon_locations._mirror_text",
            return_value=changed_mirrors,
        ):
            edited = build_dungeon_locations(self.sources)
        self.assertNotEqual(edited.outputs[MAZE_TARGET], self.build.outputs[MAZE_TARGET])
        self.assertNotEqual(
            edited.outputs[AUTOMAP_TARGET], self.build.outputs[AUTOMAP_TARGET]
        )
        # Mirror records store semantic selectors, so a prose edit does not need to
        # churn their bytes once their authored bindings agree with the core table.
        self.assertEqual(
            edited.outputs["MAZEDATA/ITOSELV.BIN"],
            self.build.outputs["MAZEDATA/ITOSELV.BIN"],
        )
        for target in PRIMARY_TARGETS:
            cave = next(
                patch for patch in edited.patches[target] if patch.name == "renderer_cave"
            )
            self.assertEqual(len(cave.expected), len(cave.replacement))

    def test_no_data_edit_can_use_the_full_authored_automap_width(self) -> None:
        marker_text = dict(_marker_text())
        marker_text["marker_no_data"] = "Map data unavailable"
        with patch(
            "engine.surfaces.dungeon_locations._marker_text",
            return_value=marker_text,
        ):
            edited = build_dungeon_locations(self.sources)
        self.assertGreater(
            len(edited.runtime_used[AUTOMAP_TARGET]),
            len(self.build.runtime_used[AUTOMAP_TARGET]),
        )
        cave = next(
            patch
            for patch in edited.patches[AUTOMAP_TARGET]
            if patch.name == "renderer_cave"
        )
        self.assertEqual(len(cave.expected), len(cave.replacement))

    def test_stock_hash_guard_rejects_a_changed_physical_target(self) -> None:
        changed = dict(self.sources)
        target = "MAZEDATA/CHI1KAI0.BIN"
        payload = bytearray(changed[target])
        payload[-1] ^= 1
        changed[target] = bytes(payload)
        with self.assertRaisesRegex(ValueError, "expected stock SHA-256"):
            build_dungeon_locations(changed)


if __name__ == "__main__":
    unittest.main()
