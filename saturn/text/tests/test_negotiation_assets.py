from __future__ import annotations

import json
import re
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEXT_ROOT.parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402
from util.surfaces import load_surfaces  # noqa: E402


@dataclass(frozen=True, slots=True)
class Bank:
    source: str
    authored_count: int
    physical_count: int
    note_count: int
    reviewed_dialogue_count: int = 0


BANKS = {
    "archaic": Bank("tlk_kofu", 546, 573, 49),
    "beast": Bank("tlk_bst", 549, 599, 37),
    "boy": Bank("tlk_boy", 539, 581, 45),
    "cynical": Bank("cyni", 558, 798, 49),
    "feral": Bank("kemo", 647, 814, 10),
    "girl": Bank("grl", 676, 795, 29),
    "highborn_lady": Bank("tlk_hirk", 554, 600, 36),
    "kansai": Bank("tlk_west", 533, 583, 18),
    "lady": Bank("tlk_lady", 550, 620, 55),
    "little_girl": Bank("cld_f", 610, 723, 42, 108),
    "manic": Bank("tlk_crzy", 525, 590, 26),
    "nobleman": Bank("nbl_m", 639, 767, 18),
    "old_man": Bank("jijy", 511, 743, 20),
    "slime": Bank("slm", 394, 481, 28),
    "young_man": Bank("tlk_yngm", 587, 637, 52),
}
CONDITION_KEYS = {
    "condition_ally_veto",
    "condition_charmed",
    "condition_confused",
    "condition_enraged",
    "condition_full_moon",
    "condition_happy",
    "condition_talk_blocked",
}


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class NegotiationAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.physical_records: dict[str, str] = {}
        for path in sorted((TEXT_ROOT / "corpus").rglob("*.json")):
            for row in read_json(path):
                cls.physical_records[row["id"]] = row["reference"]

        cls.catalogs = {
            name: load_asset(f"negotiation/{name}.json") for name in BANKS
        }
        cls.bindings = {
            name: load_binding(
                BINDING_ROOT / f"negotiation_{name}.json",
                physical_records=cls.physical_records,
            )
            for name in BANKS
        }
        cls.physical_dialogue = {
            name: read_json(
                TEXT_ROOT / "corpus" / "game" / "eve" / f"{bank.source}.json"
            )
            for name, bank in BANKS.items()
        }

    def test_all_personality_files_are_human_facing(self) -> None:
        asset_names = {
            path.stem
            for path in (PROJECT_ROOT / "assets" / "text" / "negotiation").glob(
                "*.json"
            )
        }
        binding_names = {
            path.stem.removeprefix("negotiation_")
            for path in BINDING_ROOT.glob("negotiation_*.json")
        }
        self.assertEqual(asset_names, set(BANKS))
        self.assertEqual(binding_names, set(BANKS))

    def test_authored_inventories_are_complete_and_personality_local(self) -> None:
        total_entries = 0
        total_notes = 0
        for name, bank in BANKS.items():
            with self.subTest(personality=name):
                catalog = self.catalogs[name]
                dialogue_keys = {
                    f"dialogue_{index:04d}"
                    for index in range(bank.authored_count)
                }
                self.assertEqual(
                    set(catalog.entries), dialogue_keys | CONDITION_KEYS
                )
                self.assertEqual(
                    sum(
                        entry.fields["text"].reviewed
                        for entry in catalog.entries.values()
                    ),
                    bank.reviewed_dialogue_count + 7,
                )
                notes = sum(
                    entry.fields["text"].note is not None
                    for entry in catalog.entries.values()
                )
                self.assertEqual(notes, bank.note_count)
                total_notes += notes
                total_entries += len(catalog.entries)
                for key, entry in catalog.entries.items():
                    self.assertEqual(set(entry.fields), {"text"})
                    self.assertTrue(entry.fields["text"].reference)
                    self.assertTrue(entry.fields["text"].translation)
                    self.assertFalse(entry.fields["text"].variants)
                    self.assertRegex(key, r"^(?:dialogue_\d{4}|condition_[a-z_]+)$")

        self.assertEqual(total_entries, 8_523)
        self.assertEqual(total_notes, 514)

    def test_dynamic_values_have_shared_semantic_types(self) -> None:
        observed = {
            (placeholder, placeholder_type)
            for catalog in self.catalogs.values()
            for entry in catalog.entries.values()
            for placeholder, placeholder_type in entry.placeholders.items()
        }
        self.assertEqual(
            observed,
            {
                ("codename", "player_codename"),
                ("demon_name", "demon_name"),
                ("kyouji_name", "character_name"),
                ("offered_item", "item_name"),
                ("race", "demon_race"),
                ("rei_name", "character_name"),
                ("requested_item", "item_name"),
            },
        )

    def test_saturn_bindings_cover_every_occurrence_without_deduplication(
        self,
    ) -> None:
        total_edges = 0
        condition_ids: set[str] = set()
        for name, bank in BANKS.items():
            with self.subTest(personality=name):
                binding = self.bindings[name]
                physical_ids = {
                    row["id"] for row in self.physical_dialogue[name]
                }
                eve_bindings = {
                    physical_id: asset_ref
                    for physical_id, asset_ref in binding.records.items()
                    if physical_id.startswith(f"game.{bank.source}.")
                }
                condition_bindings = {
                    physical_id: asset_ref
                    for physical_id, asset_ref in binding.records.items()
                    if physical_id.startswith(
                        "game.combat_condition_messages."
                    )
                }
                self.assertEqual(set(eve_bindings), physical_ids)
                self.assertEqual(len(eve_bindings), bank.physical_count)
                self.assertEqual(
                    len(set(eve_bindings.values())), bank.authored_count
                )
                self.assertEqual(len(condition_bindings), 7)
                self.assertEqual(
                    set(condition_bindings.values()),
                    {f"{key}.text" for key in CONDITION_KEYS},
                )
                self.assertTrue(condition_ids.isdisjoint(condition_bindings))
                condition_ids.update(condition_bindings)
                self.assertEqual(
                    len(set(binding.records.values())),
                    bank.authored_count + 7,
                )
                self.assertEqual(
                    binding.field_surfaces,
                    {"text": ("battle.negotiation_dialogue",)},
                )
                total_edges += len(binding.records)

        self.assertEqual(len(condition_ids), 105)
        self.assertEqual(total_edges, 10_009)

    def test_mature_sharing_is_explicit_not_inferred_from_text(self) -> None:
        cynical = self.bindings["cynical"].records
        self.assertEqual(
            cynical["game.cyni.m0001.p00"], "dialogue_0001.text"
        )
        self.assertEqual(
            cynical["game.cyni.m0002.p00"], "dialogue_0001.text"
        )
        self.assertEqual(
            cynical["game.cyni.m0001.p01"], "dialogue_0002.text"
        )
        self.assertEqual(
            cynical["game.cyni.m0002.p01"], "dialogue_0002.text"
        )

    def test_notes_only_link_to_existing_authored_keys(self) -> None:
        for name, catalog in self.catalogs.items():
            for entry in catalog.entries.values():
                note = entry.fields["text"].note
                if note is None:
                    continue
                self.assertNotIn("ds.eve", note)
                self.assertNotIn(f"game.{BANKS[name].source}", note)
                for target in re.findall(r"dialogue_\d{4}", note):
                    self.assertIn(target, catalog.entries)

        cynical_notes = [
            entry.fields["text"].note
            for entry in self.catalogs["cynical"].entries.values()
            if entry.fields["text"].note is not None
        ]
        self.assertTrue(any("dialogue_0040" in note for note in cynical_notes))
        for note in cynical_notes:
            self.assertIsNone(re.search(r"\b(?:record|message)s? \d+\b", note))

    def test_lossless_source_glyphs_remain_readable_and_explicit(self) -> None:
        little_girl = self.catalogs["little_girl"].entries["dialogue_0493"]
        self.assertIn("□", little_girl.fields["text"].reference)
        self.assertEqual(
            dict(self.bindings["little_girl"].glyph_equivalence),
            {"00c0": "□"},
        )
        for name, binding in self.bindings.items():
            if name != "little_girl":
                self.assertFalse(binding.glyph_equivalence)

        self.assertTrue(
            any(
                "{GLYPH:010d}" in entry.fields["text"].reference
                for entry in self.catalogs["young_man"].entries.values()
            )
        )
        self.assertTrue(
            any(
                "{GLYPH:010c}" in entry.fields["text"].reference
                for entry in self.catalogs["slime"].entries.values()
            )
        )

    def test_negotiation_has_one_shared_measured_surface(self) -> None:
        surface = load_surfaces().surface("battle.negotiation_dialogue")
        self.assertEqual(
            (
                surface.ja.font,
                surface.ja.rows,
                surface.ja.width.unit,
                surface.ja.width.value,
            ),
            ("font16", 3, "glyph_cells", 20),
        )
        self.assertEqual(
            (
                surface.en.font,
                surface.en.rows,
                surface.en.width.unit,
                surface.en.width.value,
            ),
            ("font16", 3, "pixels", 300),
        )


if __name__ == "__main__":
    unittest.main()
