from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.shared.compendium_codec import (
    CompactCodec,
    build_dictionary,
    build_embedded_font,
    encode_profile_tail,
    encode_text_rows,
    wrap_rows,
)
from text.util.assets import load_asset
from text.util.event_repack import FontMetrics


SATURN_ROOT = Path(__file__).resolve().parents[2]
BINDING_ROOT = SATURN_ROOT / "text" / "bindings"
METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"
FONT_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8.FON"


def _translations() -> tuple[dict[str, str], set[str]]:
    translated: dict[str, str] = {}
    unresolved: set[str] = set()
    for path in sorted(BINDING_ROOT.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        catalog = load_asset(document["asset"])
        variants = document.get("variants", {})
        for physical_id, asset_ref in document["records"].items():
            if not physical_id.startswith("compendium."):
                continue
            _reference, translation, _reviewed = catalog.field(asset_ref).resolve(
                variants.get(physical_id)
            )
            if translation:
                translated[physical_id] = translation
            else:
                unresolved.add(physical_id)
    return translated, unresolved


class CompendiumCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.translations, cls.unresolved = _translations()
        cls.codec = CompactCodec(build_dictionary(cls.translations.values()))
        metrics = FontMetrics.load(METRICS_PATH)
        cls.metrics = metrics
        cls.advances = {text: glyph.advance for text, glyph in metrics.by_text.items()}
        cls.advances[";"] = max(cls.advances[":"], cls.advances[","])

    def test_embedded_font_covers_every_decoder_character(self) -> None:
        codes = {text: glyph.code for text, glyph in self.metrics.by_text.items()}
        embedded = build_embedded_font(
            FONT_PATH.read_bytes(), codes, self.advances
        )
        self.assertEqual(len(embedded.bitmaps), 96 * 8)
        self.assertEqual(len(embedded.advances), 96)
        used = set("".join(self.translations.values()))
        for character in used:
            index = ord(character) - 0x20
            self.assertGreater(embedded.advances[index], 0)
            if character != " ":
                glyph = embedded.bitmaps[index * 8 : index * 8 + 8]
                self.assertNotEqual(glyph, bytes(8))

    def test_inventory_has_only_two_unknown_rows_and_three_blanks(self) -> None:
        self.assertEqual(len(self.translations), 1612)
        self.assertEqual(
            self.unresolved,
            {
                "compendium.race_names.supplement.r0003",
                "compendium.race_names.supplement.r0004",
                "compendium.race_descriptions.o06c2e8.description",
                "compendium.race_descriptions.o06c518.description",
                "compendium.race_descriptions.o06c5a4.description",
            },
        )

    def test_dictionary_and_rows_are_deterministic_and_reversible(self) -> None:
        self.assertEqual(len(self.codec.dictionary), 64)
        self.assertEqual(self.codec.dictionary[:5], (" the ", " the", " and ", "the ", "and "))
        for value in self.translations.values():
            encoded = self.codec.encode_row(value, (self.codec.required_bits(value) + 15) // 16)
            self.assertEqual(self.codec.decode_row(encoded), value)

    def test_all_profile_fields_fit_the_proved_layout(self) -> None:
        layouts = {
            # Retail starts summary at the final origin-layout word and detail
            # at the final summary-layout word. The aggregate tail compiler
            # owns those two scaffold words, giving every prose row 14 words
            # without changing any call site.
            "origin": ((9,), 144),
            "summary": ((14, 14, 14, 14), 224),
            "detail": ((14,) * 12, 224),
        }
        counts = {name: 0 for name in layouts}
        for physical_id, value in self.translations.items():
            field = physical_id.rsplit(".", 1)[-1]
            if field not in layouts:
                continue
            capacities, pixels = layouts[field]
            rows = wrap_rows(value, self.codec, capacities, self.advances, pixels)
            encoded = encode_text_rows(
                value, self.codec, capacities, self.advances, pixels
            )
            self.assertEqual(len(encoded), sum(capacities) * 2)
            self.assertEqual(" ".join(rows), value)
            offset = 0
            decoded = []
            for words in capacities:
                decoded.append(self.codec.decode_row(encoded[offset : offset + words * 2]))
                offset += words * 2
            self.assertEqual(" ".join(row for row in decoded if row), value)
            counts[field] += 1
        self.assertEqual(counts, {"origin": 292, "summary": 292, "detail": 292})

        by_profile: dict[str, dict[str, str]] = {}
        for physical_id, value in self.translations.items():
            if not physical_id.startswith("compendium.profiles."):
                continue
            profile = physical_id.split(".")[2]
            by_profile.setdefault(profile, {})[physical_id.rsplit(".", 1)[-1]] = value
        self.assertEqual(len(by_profile), 292)
        for fields in by_profile.values():
            tail = encode_profile_tail(
                fields["origin"],
                fields["summary"],
                fields["detail"],
                self.codec,
                self.advances,
            )
            self.assertEqual(len(tail), 0x1DC)
            self.assertEqual(self.codec.decode_row(tail[:18]), fields["origin"])
            summary = [
                self.codec.decode_row(tail[offset : offset + 28])
                for offset in range(0x1C, 0x8C, 28)
            ]
            detail = [
                self.codec.decode_row(tail[offset : offset + 28])
                for offset in range(0x8C, 0x1DC, 28)
            ]
            self.assertEqual(" ".join(row for row in summary if row), fields["summary"])
            self.assertEqual(" ".join(row for row in detail if row), fields["detail"])

    def test_all_a_dic_names_fit_storage_and_pixel_geometry(self) -> None:
        layouts = {
            "compendium.demon_names.": (8, 128, 319),
            "compendium.ability_names.": (8, 128, 255),
            "compendium.race_names.": (3, 48, 46),
        }
        for prefix, (words, pixels, expected_count) in layouts.items():
            selected = {
                key: value
                for key, value in self.translations.items()
                if key.startswith(prefix)
            }
            self.assertEqual(len(selected), expected_count)
            for value in selected.values():
                self.assertLessEqual(
                    sum(self.advances[character] for character in value), pixels
                )
                encoded = self.codec.encode_row(value, words)
                self.assertEqual(self.codec.decode_row(encoded), value)

    def test_all_a_dic_prose_fits_proved_rows(self) -> None:
        layouts = {
            ".description": ((14,) * 4, 224, 45),
            "compendium.fusion_help.": ((20, 20), 320, 11),
        }
        descriptions = {
            key: value
            for key, value in self.translations.items()
            if key.startswith("compendium.race_descriptions.")
            and key.endswith(".description")
        }
        help_rows = {
            key: value
            for key, value in self.translations.items()
            if key.startswith("compendium.fusion_help.")
        }
        for selected, (capacities, pixels, count) in zip(
            (descriptions, help_rows), layouts.values(), strict=True
        ):
            self.assertEqual(len(selected), count)
            for value in selected.values():
                rows = wrap_rows(
                    value, self.codec, capacities, self.advances, pixels
                )
                self.assertEqual(" ".join(rows), value)

    def test_compendium_status_labels_fit_their_two_blitter_paths(self) -> None:
        base = {
            key: value
            for key, value in self.translations.items()
            if key.startswith("compendium.status_base_labels.")
        }
        derived = {
            key: value
            for key, value in self.translations.items()
            if key.startswith("compendium.status_derived_labels.")
        }
        self.assertEqual(len(base), 6)
        self.assertEqual(len(derived), 6)
        for value in base.values():
            self.assertLessEqual(
                sum(self.advances[character] for character in value), 16
            )
        for value in derived.values():
            self.assertLessEqual(
                sum(self.advances[character] for character in value), 64
            )
            encoded = self.codec.encode_row(value, 4)
            self.assertEqual(self.codec.decode_row(encoded), value)


if __name__ == "__main__":
    unittest.main()
