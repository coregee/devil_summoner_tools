from __future__ import annotations

import hashlib
import json
import struct
import unittest
from dataclasses import replace

from psp.engine.surfaces.command_menu_help import load_eve_widths
from psp.text.util.compendium import (
    CONFIG_PATH,
    COMPENDIUM_BODY_WIDTH,
    COMPENDIUM_DETAIL_LINE_LIMIT,
    COMPENDIUM_LIVE_PROFILE_COUNT,
    COMPENDIUM_ORIGIN_LINE_LIMIT,
    COMPENDIUM_ORIGIN_WIDTH,
    COMPENDIUM_SUMMARY_LINE_LIMIT,
    COMPENDIUM_TEXT_ARENA_SIZE,
    build_compendium_text,
    load_compendium_profiles,
)
from psp.text.util.event_packed import encode_ascii


class CompendiumTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.widths = load_eve_widths()
        cls.profiles = load_compendium_profiles()
        cls.build = build_compendium_text(
            cls.profiles,
            lambda value: sum(
                cls.widths[code - 0x1F] for code in encode_ascii(value)
            ),
            arena_size=COMPENDIUM_TEXT_ARENA_SIZE,
            arena_raw_address=0x26518,
        )

    def test_binding_keeps_every_physical_row_and_psp_only_profile(self) -> None:
        binding = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(binding["rows"]), 319)
        self.assertEqual(
            {row["status"] for row in binding["rows"]},
            {"live_saturn", "live_psp", "empty", "orphan_unbound"},
        )
        self.assertEqual(
            [binding["rows"][index]["asset"] for index in range(308, 312)],
            ["david", "enoch", "leviathan", "skoll"],
        )
        self.assertEqual(len(self.profiles), 319)
        self.assertEqual(sum(profile.live for profile in self.profiles), 292)
        self.assertFalse(self.profiles[260].live)
        self.assertFalse(self.profiles[273].live)
        self.assertFalse(self.profiles[318].live)

    def test_canonical_build_matches_the_mature_port_exactly(self) -> None:
        self.assertEqual(len(self.build.profiles), COMPENDIUM_LIVE_PROFILE_COUNT)
        self.assertEqual(self.build.translated_field_count, 876)
        self.assertEqual(self.build.reviewed_field_count, 0)
        self.assertEqual(self.build.unique_string_count, 635)
        self.assertEqual(self.build.used_size, 116_577)
        self.assertEqual(len(self.build.text_arena), 0x1D028)
        self.assertEqual(
            hashlib.sha256(self.build.text_arena).hexdigest(),
            "d9028b2de27b5040972c97b277cde5110333d3fd7e11b709b9db85504146150f",
        )
        self.assertEqual(
            hashlib.sha256(self.build.pointer_table).hexdigest(),
            "d1674c16e137bce21cc2d3e867e5638cfa05b0acc962c11fb6c4bf2b3e76dc5b",
        )
        self.assertEqual(
            struct.unpack_from("<IIII", self.build.pointer_table, 308 * 0x10)[3],
            0x00010001,
        )

    def test_geometry_matches_the_stock_viewer(self) -> None:
        self.assertEqual(COMPENDIUM_ORIGIN_WIDTH, 13 * 15)
        self.assertEqual(COMPENDIUM_BODY_WIDTH, 21 * 15)
        self.assertEqual(COMPENDIUM_ORIGIN_LINE_LIMIT, 1)
        self.assertEqual(COMPENDIUM_SUMMARY_LINE_LIMIT, 3)
        self.assertEqual(COMPENDIUM_DETAIL_LINE_LIMIT, 11)
        self.assertTrue(
            all(
                sum(self.widths[code - 0x1F] for code in encode_ascii(line))
                <= (
                    COMPENDIUM_ORIGIN_WIDTH
                    if field == "origin"
                    else COMPENDIUM_BODY_WIDTH
                )
                for profile in self.build.profiles
                for field, lines in (
                    ("origin", profile.origin_lines),
                    ("summary", profile.summary_lines),
                    ("detail", profile.detail_lines),
                )
                for line in lines
            )
        )

    def test_builder_rejects_changed_row_identity_and_missing_text(self) -> None:
        profiles = list(self.profiles)
        profiles[0] = replace(profiles[0], row_index=1)
        with self.assertRaisesRegex(ValueError, "physical row identity changed"):
            build_compendium_text(
                profiles,
                lambda value: len(value) * 5,
                arena_size=COMPENDIUM_TEXT_ARENA_SIZE,
                arena_raw_address=0x26518,
            )
        profiles = list(self.profiles)
        profiles[0] = replace(profiles[0], detail=None)
        with self.assertRaisesRegex(ValueError, "needs all three translations"):
            build_compendium_text(
                profiles,
                lambda value: len(value) * 5,
                arena_size=COMPENDIUM_TEXT_ARENA_SIZE,
                arena_raw_address=0x26518,
            )


if __name__ == "__main__":
    unittest.main()

