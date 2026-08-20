from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.sources import load_manifest, manifest_path  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


MSGR_LOAD_ADDRESS = 0x06060000
DEBUG_RECORDS = {
    "game.msgr_debug_ascii.o00ae04": (
        0xAE04,
        16,
        "NAME TO ID ERR",
        "portrait_name_id_error.text",
    ),
    "game.msgr_debug_ascii.o00ae14": (
        0xAE14,
        10,
        "LOAD ERR",
        "portrait_load_error.text",
    ),
    "game.msgr_debug_ascii.o00c1b4": (
        0xC1B4,
        24,
        "ERROR: MENU COUNT OVER",
        "portrait_menu_count_over.text",
    ),
}


class PortraitSceneAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_manifest(manifest_path("game"))
        cls.debug_source = next(
            source
            for source in cls.manifest.sources
            if source.name == "msgr_debug_ascii"
        )
        cls.term_source = next(
            source
            for source in cls.manifest.sources
            if source.name == "normcom_tables"
        )
        cls.corpus = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "msgr_debug_ascii.json"
            ).read_text(encoding="utf-8")
        )
        cls.debug_asset = load_asset("system/debug.json")
        cls.debug_binding = load_binding(
            BINDING_ROOT / "portrait_scene_debug.json"
        )
        cls.demon_binding = load_binding(BINDING_ROOT / "demons.json")
        cls.character_binding = load_binding(BINDING_ROOT / "characters.json")
        cls.race_binding = load_binding(BINDING_ROOT / "races.json")
        cls.races = load_asset("races.json")
        cls.surfaces = load_surfaces()
        # Tests must remain independent of the mutable extracted/build mirror,
        # which may already contain the installed portrait-scene patch.
        validated = validate_source(load_catalog()["game"])
        cls.stock = read_source_files(validated, ("MSGR.COF",))["MSGR.COF"]

    def test_manifest_pins_all_three_padded_diagnostics(self) -> None:
        self.assertEqual(
            self.debug_source.corpus_path,
            PurePosixPath("addressed/msgr_debug_ascii.json"),
        )
        container = self.debug_source.container
        self.assertEqual(container["type"], "addressed")
        self.assertEqual(container["file"], "msgr_cof")
        self.assertEqual(container["default_source_encoding"], "ascii")
        self.assertEqual(container["tables"], [])
        self.assertEqual(
            [
                (
                    record["name"],
                    record["framing"],
                    record["locations"][0]["spans"][0],
                )
                for record in container["records"]
            ],
            [
                (
                    "name_id_error",
                    {"type": "zero_terminated"},
                    {"offset": "0xae04", "units": 16},
                ),
                (
                    "load_error",
                    {"type": "zero_terminated"},
                    {"offset": "0xae14", "units": 10},
                ),
                (
                    "menu_count_over",
                    {"type": "zero_terminated"},
                    {"offset": "0xc1b4", "units": 24},
                ),
            ],
        )
        target = self.manifest.files["msgr_cof"]
        self.assertEqual(target.size, 103792)
        self.assertEqual(
            target.stock_sha256,
            "fc483f3483b14591bef0af1981d2d142c3621506981a596b31595283daa183fa",
        )
        self.assertEqual(
            target.owned_sha256,
            "aa1ddd442655db67044fe6a1dc658c9f39f288a1f56e16ba646358a0d0a0d08c",
        )

    def test_generated_corpus_is_complete_and_lossless(self) -> None:
        self.assertEqual(
            {
                row["id"]: (row["source_encoding"], row["reference"])
                for row in self.corpus
            },
            {
                physical_id: ("ascii", reference)
                for physical_id, (_offset, _capacity, reference, _asset) in (
                    DEBUG_RECORDS.items()
                )
            },
        )
        for offset, capacity, reference, _asset_ref in DEBUG_RECORDS.values():
            with self.subTest(offset=f"{offset:#x}"):
                expected = reference.encode("ascii") + b"\0"
                actual = self.stock[offset : offset + capacity]
                self.assertEqual(actual[: len(expected)], expected)
                self.assertEqual(actual[len(expected) :], bytes(capacity - len(expected)))

    def test_debug_fields_are_editable_within_their_physical_caps(self) -> None:
        self.assertEqual(
            dict(self.debug_binding.records),
            {
                physical_id: asset_ref
                for physical_id, (_offset, _capacity, _reference, asset_ref) in (
                    DEBUG_RECORDS.items()
                )
            },
        )
        self.assertEqual(
            dict(self.debug_binding.field_surfaces),
            {"text": ("portrait_scene.debug_message",)},
        )
        for physical_id, (_offset, capacity, reference, asset_ref) in (
            DEBUG_RECORDS.items()
        ):
            with self.subTest(record=physical_id):
                field = self.debug_asset.field(asset_ref)
                self.assertEqual((field.reference, field.translation), (reference, reference))
                self.assertLessEqual(len(field.translation.encode("ascii")), capacity - 1)
                self.assertIn(f"{capacity - 1} visible bytes", field.note or "")
                self.assertIn("embedded fixed-cell ASCII tile set", field.note or "")

    def test_diagnostics_reach_the_embedded_tile_surface(self) -> None:
        # 0x0606A608 computes base + page + y*128 + x*2.  The literal at
        # file 0xA628 is the VDP2 pattern-name buffer base; 0x0606A62C then
        # copies each ASCII byte as a doubled 16-bit tile code.
        self.assertEqual(
            self.stock[0xA608:0xA62C].hex(),
            "c580440045184501610cd005412841094101301c304c000b305c00000000000025e00000",
        )
        self.assertEqual(
            self.stock[0xA62C:0xA640].hex(),
            "6044600c20088d03300c2501aff87502000b0009",
        )
        self.assertEqual(
            struct.unpack_from(">I", self.stock, 0xA628)[0],
            0x25E00000,
        )
        self.assertEqual(
            {
                0xAE88: MSGR_LOAD_ADDRESS + 0xAE04,
                0xAE8C: MSGR_LOAD_ADDRESS + 0xA62C,
                0xAE94: MSGR_LOAD_ADDRESS + 0xAE14,
                0xC344: MSGR_LOAD_ADDRESS + 0xC1B4,
                0xC348: MSGR_LOAD_ADDRESS + 0xA62C,
            },
            {
                offset: struct.unpack_from(">I", self.stock, offset)[0]
                for offset in (0xAE88, 0xAE8C, 0xAE94, 0xC344, 0xC348)
            },
        )

        surface = self.surfaces.surface("portrait_scene.debug_message")
        for layout in (surface.ja, surface.en):
            self.assertEqual(
                (
                    layout.font,
                    layout.rows,
                    layout.width.unit,
                    layout.width.value,
                    layout.glyphs,
                ),
                (None, 1, "glyph_cells", 64, None),
            )

    def test_portrait_dialogue_reuses_all_shared_fixed_terms(self) -> None:
        cases = (
            (self.demon_binding, "game.dvlname.", 319),
            (self.character_binding, "game.charname.", 6),
            (self.race_binding, "game.normcom_tables.races.", 43),
        )
        for binding, prefix, count in cases:
            with self.subTest(asset=binding.asset.as_posix()):
                self.assertIn("event.dialogue", binding.field_surfaces["name"])
                self.assertEqual(
                    sum(physical_id.startswith(prefix) for physical_id in binding.records),
                    count,
                )

        # The only mature direct table edit is still the shared UMA race row;
        # it does not acquire an MSGR-local duplicate asset.
        physical_id = "game.normcom_tables.races.r0022"
        self.assertEqual(self.race_binding.records[physical_id], "uma.name")
        self.assertEqual(self.races.field("uma.name").translation, "UMA")
        table = self.term_source.container["tables"][0]
        self.assertEqual(table["name"], "races")
        self.assertEqual(table["count"], 43)
        self.assertIn(
            {
                "file": "msgr_cof",
                "base": "0x18d90",
                "stride": "0x8",
                "units": 4,
            },
            table["locations"],
        )

    def test_player_fields_stay_on_the_shared_event_surface(self) -> None:
        expected = {
            "first_name": "player_name",
            "last_name": "player_name",
            "codename": "player_codename",
            "city": "location_name",
            "ward": "location_name",
        }
        actual: dict[str, str] = {}
        for path in sorted(BINDING_ROOT.glob("*.json")):
            raw = path.read_text(encoding="utf-8")
            if "event.dialogue" not in raw:
                continue
            binding = load_binding(path)
            catalog = load_asset(binding.asset)
            for physical_id, asset_ref in binding.records.items():
                field_name = asset_ref.rsplit(".", 1)[-1]
                surfaces = binding.record_surfaces.get(
                    physical_id,
                    binding.field_surfaces.get(field_name, ()),
                )
                if "event.dialogue" not in surfaces:
                    continue
                entry_name = asset_ref.rsplit(".", 1)[0]
                for placeholder, placeholder_type in (
                    catalog.entries[entry_name].placeholders.items()
                ):
                    if placeholder in expected:
                        actual[placeholder] = placeholder_type
        self.assertEqual(actual, expected)
        self.assertNotIn("portrait_scene.dialogue", self.surfaces.surfaces)
        self.assertNotIn("portrait_scene.choice_option", self.surfaces.surfaces)


if __name__ == "__main__":
    unittest.main()
