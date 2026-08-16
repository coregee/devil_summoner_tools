from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


class FieldAutomapAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.automap = load_asset("field/automap.json")
        cls.messages = load_asset("field/messages.json")
        cls.automap_binding = load_binding(BINDING_ROOT / "field_automap.json")
        cls.choice_binding = load_binding(
            BINDING_ROOT / "field_automap_choices.json"
        )
        cls.message_binding = load_binding(BINDING_ROOT / "field_messages.json")
        cls.surfaces = load_surfaces()
        cls.manifest = load_manifest(manifest_path("game"))

    def test_all_six_physical_records_have_authored_owners(self) -> None:
        expected = {
            "game.maze_speech_choices_static.o0250d0": "talk_choice_yes.text",
            "game.maze_speech_choices_static.o0250d6": "talk_choice_no.text",
            "game.automap_marker_ui.o009aa8": "marker_no_data.text",
            "game.automap_marker_ui.o00a5e0": "talk_choice_yes.text",
            "game.automap_marker_ui.o00a5e4": "talk_choice_no.text",
            "game.automap_system.o00a69c": "marker_delete.text",
        }
        actual = {
            **self.message_binding.records,
            **self.automap_binding.records,
            **self.choice_binding.records,
        }
        self.assertEqual(
            {physical_id: actual[physical_id] for physical_id in expected},
            expected,
        )
        self.assertEqual(
            {
                key: entry.fields["text"].translation
                for key, entry in self.automap.entries.items()
            },
            {
                "marker_no_data": "(No data)",
                "marker_delete": "Delete?",
            },
        )
        self.assertEqual(
            (
                self.messages.field("talk_choice_yes.text").translation,
                self.messages.field("talk_choice_no.text").translation,
            ),
            ("Yes", "No"),
        )

    def test_maze_and_automap_choices_share_one_semantic_field(self) -> None:
        self.assertEqual(
            self.message_binding.records[
                "game.maze_speech_choices_static.o0250d0"
            ],
            self.choice_binding.records["game.automap_marker_ui.o00a5e0"],
        )
        self.assertEqual(
            self.message_binding.records[
                "game.maze_speech_choices_static.o0250d6"
            ],
            self.choice_binding.records["game.automap_marker_ui.o00a5e4"],
        )
        self.assertEqual(
            dict(self.choice_binding.variants),
            {"game.automap_marker_ui.o00a5e4": "automap"},
        )
        self.assertEqual(
            self.messages.field("talk_choice_no.text").resolve("automap")[:2],
            (" NO", "No"),
        )

    def test_manifest_pins_every_physical_offset_and_framing(self) -> None:
        sources = {source.name: source for source in self.manifest.sources}
        maze = sources["maze_speech_choices_static"].container
        self.assertEqual(
            [
                (
                    record["name"],
                    record["locations"][0]["spans"][0]["offset"],
                    record["locations"][0]["spans"][0]["units"],
                )
                for record in maze["records"]
            ],
            [("label_yes", "0x250d0", 3), ("label_no", "0x250d6", 3)],
        )

        marker = sources["automap_marker_ui"].container
        self.assertEqual(marker["default_source_encoding"], "ascii")
        self.assertEqual(
            [
                (
                    record["name"],
                    record["locations"][0]["spans"][0]["offset"],
                    record["locations"][0]["spans"][0]["units"],
                    record["framing"]["type"],
                )
                for record in marker["records"]
            ],
            [
                ("marker_no_data", "0x9aa8", 8, "zero_terminated"),
                ("marker_yes", "0xa5e0", 4, "zero_terminated"),
                ("marker_no", "0xa5e4", 4, "zero_terminated"),
            ],
        )
        delete = sources["automap_system"].container["records"][0]
        self.assertEqual(delete["name"], "marker_delete")
        self.assertEqual(
            delete["locations"][0]["spans"],
            [{"offset": "0xa69c", "units": 6}],
        )

    def test_each_record_uses_its_measured_surface(self) -> None:
        surfaces = {
            **self.message_binding.record_surfaces,
            **self.automap_binding.record_surfaces,
            **self.choice_binding.record_surfaces,
        }
        expected = {
            "game.maze_speech_choices_static.o0250d0": (
                "map_3d.field_choice",
            ),
            "game.maze_speech_choices_static.o0250d6": (
                "map_3d.field_choice",
            ),
            "game.automap_marker_ui.o009aa8": ("automap.entry",),
            "game.automap_marker_ui.o00a5e0": ("automap.marker_popup",),
            "game.automap_marker_ui.o00a5e4": ("automap.marker_popup",),
            "game.automap_system.o00a69c": ("automap.marker_popup",),
        }
        self.assertEqual(
            {physical_id: surfaces[physical_id] for physical_id in expected},
            expected,
        )
        choice = self.surfaces.surface("map_3d.field_choice")
        popup = self.surfaces.surface("automap.marker_popup")
        self.assertEqual(
            (choice.ja.font, choice.ja.rows, choice.ja.width.unit, choice.ja.width.value),
            ("font16", 1, "glyph_cells", 3),
        )
        self.assertEqual(
            (choice.en.font, choice.en.rows, choice.en.width.unit, choice.en.width.value),
            ("font16", 1, "pixels", 48),
        )
        self.assertEqual(
            (popup.en.font, popup.en.rows, popup.en.width.unit, popup.en.width.value),
            ("font16", 3, "pixels", 64),
        )


if __name__ == "__main__":
    unittest.main()
