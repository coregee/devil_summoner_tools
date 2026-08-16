from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import (  # noqa: E402
    ASSET_ROOT,
    BINDING_ROOT,
    load_asset,
    load_binding,
    validate_asset_document,
)
from util.surfaces import load_surfaces  # noqa: E402


CHARACTER_KEYS = (
    "hajime_tanigawa",
    "rei_reiho",
    "kyouji_kuzunoha",
    "taro_tanigawa",
    "jiro_tanigawa",
    "saburo_tanigawa",
)

CHARACTER_TRANSLATIONS = (
    "Hajime Tanigawa",
    "Rei Reiho",
    "Kyouji",
    "Taro Tanigawa",
    "Jiro Tanigawa",
    "Saburo Tanigawa",
)

RUNTIME_PROFILE_ENTRIES = {
    "grid_upper_row_1",
    "grid_upper_row_2",
    "grid_lower_row_1",
    "grid_lower_row_2",
    "grid_symbol_row_1",
    "grid_symbol_row_2",
    "default_city",
    "default_ward",
    "grid_move_left",
    "grid_move_right",
    "grid_end",
}


class CharacterAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("characters.json")
        cls.binding = load_binding(BINDING_ROOT / "characters.json")
        cls.physical = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "fixed" / "charname.json").read_text(
                encoding="utf-8"
            )
        )
        cls.surfaces = load_surfaces()

    def test_six_shared_character_identities_use_the_mature_output(self) -> None:
        self.assertEqual(tuple(self.catalog.entries), CHARACTER_KEYS)
        self.assertEqual(
            tuple(
                self.catalog.entries[key].fields["name"].translation
                for key in CHARACTER_KEYS
            ),
            CHARACTER_TRANSLATIONS,
        )
        self.assertEqual(
            sum(len(entry.fields) for entry in self.catalog.entries.values()),
            11,
        )
        self.assertIn(
            "Live player-name consumers",
            self.catalog.entries["hajime_tanigawa"].note,
        )
        for entry in self.catalog.entries.values():
            for field in entry.fields.values():
                self.assertFalse(field.reviewed)
                self.assertEqual(dict(field.variants), {})

    def test_all_charname_rows_bind_by_identity_without_content_joining(self) -> None:
        expected = {
            row["id"]: f"{key}.name"
            for key, row in zip(CHARACTER_KEYS, self.physical, strict=True)
        }
        self.assertEqual(dict(self.binding.records), expected)
        self.assertEqual(len(expected), 6)
        self.assertEqual(
            [
                self.catalog.field(asset_ref).reference
                for asset_ref in self.binding.records.values()
            ],
            [row["reference"] for row in self.physical],
        )

    def test_kyouji_full_name_is_authored_instead_of_runtime_prose(self) -> None:
        fields = self.catalog.entries["kyouji_kuzunoha"].fields
        self.assertEqual(
            {
                key: (value.reference, value.translation)
                for key, value in fields.items()
            },
            {
                "name": ("キョウジ", "Kyouji"),
                "full_name": ("葛葉キョウジ", "Kyouji Kuzunoha"),
                "given_name": ("キョウジ", "Kyouji"),
                "family_name": ("葛葉", "Kuzunoha"),
                "battle_test_name": ("葛葉キョウジ", "Kyouji"),
            },
        )
        rei = self.catalog.entries["rei_reiho"].fields["battle_test_name"]
        self.assertEqual((rei.reference, rei.translation), ("レイ", "Rei"))

    def test_character_consumers_and_proven_widths_are_explicit(self) -> None:
        self.assertEqual(
            self.binding.field_surfaces["name"],
            (
                "event.dialogue",
                "party.character_name",
                "status.character_name",
                "level_up.character_name",
                "fusion.table_character_name",
                "shop.character_name",
                "bar.status_name",
                "healer.member_name",
                "battle.result_name",
            ),
        )
        party = self.surfaces.surface("party.character_name")
        shop = self.surfaces.surface("shop.character_name")
        self.assertEqual(
            (party.en.font, party.en.rows, party.en.width.unit, party.en.width.value),
            ("font8", 1, "pixels", 80),
        )
        self.assertEqual(
            (shop.en.font, shop.en.rows, shop.en.width.unit, shop.en.width.value),
            ("font8", 1, "pixels", 72),
        )


class ProfileEntryAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("ui/profile_entry.json")
        cls.player_profile = load_asset("player_profile.json")
        cls.binding = load_binding(BINDING_ROOT / "profile_entry.json")
        cls.event_binding = load_binding(
            BINDING_ROOT / "profile_entry_events.json"
        )
        cls.physical = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "game"
                / "addressed"
                / "name_static.json"
            ).read_text(encoding="utf-8")
        )
        cls.surfaces = load_surfaces()

    def test_all_physical_name_entry_text_has_one_authored_owner(self) -> None:
        self.assertEqual(len(self.physical), 22)
        self.assertEqual(
            set(self.binding.records),
            {row["id"] for row in self.physical},
        )
        self.assertEqual(len(set(self.binding.records.values())), 22)
        self.assertEqual(
            [
                self.catalog.field(asset_ref).reference
                for asset_ref in self.binding.records.values()
            ],
            [row["reference"] for row in self.physical],
        )
        self.assertEqual(set(self.binding.record_surfaces), set(self.binding.records))

    def test_source_forks_remain_independently_editable(self) -> None:
        forks = (
            (
                "game.name_static.o020b78.prompt_first",
                "game.name_static.o020b78.prompt_last",
                ("First name?", "Last name?"),
            ),
            (
                "game.name_static.o020bc8.prompt_city",
                "game.name_static.o020bc8.prompt_ward",
                ("City?", "Ward?"),
            ),
            (
                "game.name_static.o020cb8.prompt_occupation",
                "game.name_static.o020cb8.label_occupation",
                ("Occupation", "Occupation"),
            ),
        )
        physical_by_id = {row["id"]: row for row in self.physical}
        for first, second, translations in forks:
            with self.subTest(first=first, second=second):
                self.assertEqual(
                    physical_by_id[first]["reference"],
                    physical_by_id[second]["reference"],
                )
                self.assertNotEqual(
                    self.binding.records[first], self.binding.records[second]
                )
                self.assertEqual(
                    (
                        self.catalog.field(self.binding.records[first]).translation,
                        self.catalog.field(self.binding.records[second]).translation,
                    ),
                    translations,
                )

    def test_runtime_grid_defaults_shared_name_format_and_actions_are_authored(
        self,
    ) -> None:
        bound_entries = {
            asset_ref.rsplit(".", 1)[0]
            for binding in (self.binding, self.event_binding)
            for asset_ref in binding.records.values()
        }
        self.assertEqual(
            set(self.catalog.entries) - bound_entries,
            RUNTIME_PROFILE_ENTRIES,
        )
        self.assertEqual(len(self.catalog.entries), 51)
        self.assertEqual(
            self.catalog.entries["grid_symbol_row_2"].fields["text"].translation,
            "-!?/&: ",
        )
        self.assertEqual(
            (
                self.catalog.entries["default_city"].fields["text"].translation,
                self.catalog.entries["default_ward"].fields["text"].translation,
                self.catalog.entries["grid_end"].fields["text"].translation,
            ),
            ("Hirasaki", "Asahi", "END"),
        )
        self.assertEqual(tuple(self.player_profile.entries), ("full_name_storage",))
        full_name = self.player_profile.entries["full_name_storage"]
        self.assertEqual(
            dict(full_name.placeholders),
            {"first_name": "player_name", "last_name": "player_name"},
        )
        self.assertEqual(
            (
                full_name.fields["text"].reference,
                full_name.fields["text"].translation,
            ),
            ("{last_name} {first_name}", "{first_name} {last_name}"),
        )
        self.assertIn("NAME_FW_FULL", full_name.fields["text"].note or "")
        slot_name = load_asset("save_load.json").entries["slot_name"]
        self.assertEqual(
            (
                slot_name.fields["text"].reference,
                slot_name.fields["text"].translation,
            ),
            ("{first_name} {last_name}", "{first_name} {last_name}"),
        )
        self.assertIn("visible slot layout", slot_name.fields["text"].note or "")
        self.assertNotEqual(
            full_name.fields["text"].reference,
            slot_name.fields["text"].reference,
        )
        document = json.loads(
            (ASSET_ROOT / "player_profile.json").read_text(encoding="utf-8")
        )
        document["entries"]["full_name_storage"]["text"]["reference"] = (
            "{first_name}"
        )
        document["entries"]["full_name_storage"]["text"]["translation"] = (
            "{first_name}"
        )
        with self.assertRaisesRegex(ValueError, "placeholders"):
            validate_asset_document(document, "profile_entry")
        self.assertIn(
            "0x074E",
            self.catalog.entries["grid_end"].fields["text"].note or "",
        )

    def test_stock_address_suffixes_and_retired_katakana_tab_are_inventoried(
        self,
    ) -> None:
        self.assertEqual(
            {
                key: (
                    self.catalog.entries[key].fields["text"].reference,
                    self.catalog.entries[key].fields["text"].translation,
                )
                for key in ("city_suffix", "ward_suffix", "tab_katakana")
            },
            {
                "city_suffix": ("市", " City"),
                "ward_suffix": ("区", " Ward"),
                "tab_katakana": ("カタカナ", "KATAKANA"),
            },
        )
        self.assertEqual(
            {
                record_id: self.binding.records[record_id]
                for record_id in (
                    "game.name_static.o020be2",
                    "game.name_static.o020bea",
                    "game.name_static.o020c90",
                )
            },
            {
                "game.name_static.o020be2": "city_suffix.text",
                "game.name_static.o020bea": "ward_suffix.text",
                "game.name_static.o020c90": "tab_katakana.text",
            },
        )
        manifest = json.loads(
            (TEXT_ROOT / "config" / "sources" / "game" / "manifest.json")
            .read_text(encoding="utf-8")
        )
        source = next(row for row in manifest["sources"] if row["id"] == "name_static")
        records = {
            row["name"]: row for row in source["container"]["records"]
        }
        self.assertEqual(
            {
                name: tuple(
                    location["spans"][0]["offset"]
                    for location in records[name]["locations"]
                )
                for name in ("tab_upper", "tab_lower", "tab_katakana")
            },
            {
                "tab_upper": ("0x20c40", "0x20bf2"),
                "tab_lower": ("0x20c68", "0x20bfe"),
                "tab_katakana": ("0x20c90", "0x20c0a"),
            },
        )
        self.assertTrue(
            all(
                records[name]["require_identical_bytes"]
                for name in ("tab_upper", "tab_lower", "tab_katakana")
            )
        )

    def test_opening_dds_net_workflow_uses_the_mature_saturn_output(self) -> None:
        self.assertEqual(len(self.event_binding.records), 18)
        self.assertEqual(
            set(self.event_binding.records),
            {
                f"game.evfile_0.m{message:04d}.p{page:02d}"
                for message in range(16)
                for page in range(2 if message in {0, 11} else 1)
            },
        )
        translations = tuple(
            self.catalog.field(asset_ref).translation
            for asset_ref in self.event_binding.records.values()
        )
        self.assertEqual(
            translations,
            (
                "Welcome to DDS-NET.",
                "All current members must renew their registration.{n}"
                "We apologize for the inconvenience.",
                "Please enter your name.{n}Use UPPER, lower, or SYMBOL.",
                "Is this correct?",
                "Please enter the reading for your name.",
                "Please enter your address.",
                "And your profession?",
                "So, you're an office worker?",
                "So, you're a student?",
                "So, you're a part-timer?",
                "So, you're unemployed?",
                "Is this correct?",
                "Thank you for your patience.{n}"
                "Your membership renewal is now complete.",
                "We hope you continue to enjoy DDS-NET.",
                "Employee",
                "Student",
                "Part-timer",
                "Unemployed",
            ),
        )
        self.assertEqual(dict(self.event_binding.glyph_equivalence), {"010d": "-"})
        self.assertEqual(
            dict(self.event_binding.field_surfaces),
            {"text": ("event.dialogue",)},
        )
        self.assertTrue(
            all(
                not self.catalog.field(asset_ref).reviewed
                for asset_ref in self.event_binding.records.values()
            )
        )

    def test_profile_and_name_entry_limits_match_the_mature_renderer(self) -> None:
        for field in ("first_name", "last_name", "codename", "city", "ward"):
            with self.subTest(field=field):
                layout = self.surfaces.surface(f"profile.{field}").en
                self.assertEqual(
                    (layout.font, layout.rows, layout.width.unit, layout.width.value),
                    ("font16", 1, "glyph_cells", 8),
                )
                self.assertEqual(layout.glyphs, 8)
        full_name = self.surfaces.surface("profile.full_name").en
        self.assertEqual(
            (
                full_name.font,
                full_name.rows,
                full_name.width.unit,
                full_name.width.value,
                full_name.glyphs,
            ),
            ("font16", 1, "glyph_cells", 17, 17),
        )
        occupation = self.surfaces.surface("profile.occupation").en
        self.assertEqual(
            (
                occupation.font,
                occupation.rows,
                occupation.width.unit,
                occupation.width.value,
            ),
            ("font16", 1, "pixels", 208),
        )
        expected = {
            "name_entry.prompt": ("font16", "pixels", 168, 11),
            "name_entry.confirm_prompt": ("font16", "glyph_cells", 11, 11),
            "name_entry.tab_label": ("font16", "pixels", 96, None),
            "name_entry.occupation_choice": ("font16", "pixels", 128, None),
            "name_entry.grid_row": ("kanji", "glyph_cells", 13, 13),
            "name_entry.grid_action": ("font16", "glyph_cells", 2, 2),
            "name_entry.address_suffix": ("font16", None, None, None),
            "name_entry.default_value": ("font16", "glyph_cells", 8, 8),
        }
        for surface_id, (font, unit, value, glyphs) in expected.items():
            with self.subTest(surface=surface_id):
                layout = self.surfaces.surface(surface_id).en
                self.assertEqual((layout.font, layout.rows), (font, 1))
                self.assertEqual((layout.width.unit, layout.width.value), (unit, value))
                self.assertEqual(layout.glyphs, glyphs)


if __name__ == "__main__":
    unittest.main()
