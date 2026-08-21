from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


RECORD_SIZE = 0x60
RESERVE_INDEXES = {
    77,
    78,
    124,
    126,
    128,
    140,
    *range(143, 159),
    221,
    224,
    *range(227, 255),
}
FIELD_ONLY_INDEXES = {73, 74, 75, 76}


class AbilityAssetInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic = load_asset("magic.json")
        cls.skills = load_asset("skills.json")
        cls.magic_binding = load_binding(BINDING_ROOT / "magic.json")
        cls.skill_binding = load_binding(BINDING_ROOT / "skills.json")

    def test_catalog_split_preserves_every_saturn_slot(self) -> None:
        self.assertEqual(len(self.magic.entries), 79)
        self.assertEqual(len(self.skills.entries), 178)
        self.assertEqual(
            sum(len(entry.fields) for entry in self.magic.entries.values()),
            231,
        )
        self.assertEqual(
            sum(len(entry.fields) for entry in self.skills.entries.values()),
            480,
        )

        self.assertEqual(
            sum(entry.status == "reserve" for entry in self.magic.entries.values()),
            2,
        )
        self.assertEqual(
            sum(entry.status == "reserve" for entry in self.skills.entries.values()),
            50,
        )
        reserve_keys = {
            key
            for catalog in (self.magic, self.skills)
            for key, entry in catalog.entries.items()
            if entry.status == "reserve"
        }
        self.assertEqual(len(reserve_keys), 52)
        self.assertEqual(len(set(reserve_keys)), 52)
        for catalog in (self.magic, self.skills):
            for key, entry in catalog.entries.items():
                self.assertNotIn("saturn", key)
                self.assertNotIn("psp", key)
                if key.startswith("reserved_"):
                    self.assertEqual(entry.status, "reserve")

    def test_magname_metadata_proves_the_human_facing_split(self) -> None:
        source = (
            TEXT_ROOT.parent / "rom" / "extracted" / "game" / "MAGNAME.DAT"
        ).read_bytes()
        categories = [
            source[index * RECORD_SIZE : index * RECORD_SIZE + 4].hex()
            for index in range(255)
        ]
        self.assertEqual(
            Counter(categories),
            Counter(
                {
                    "00000010": 45,
                    "00000011": 27,
                    "00000012": 5,
                    "00000013": 149,
                    "00000014": 27,
                    "00000000": 2,
                }
            ),
        )
        self.assertEqual(
            [index for index, value in enumerate(categories) if value == "00000000"],
            [77, 78],
        )
        self.assertLessEqual(set(categories[:79]), {"00000000", "00000010", "00000011", "00000012"})
        self.assertLessEqual(set(categories[79:]), {"00000013", "00000014"})

    def test_saturn_bindings_cover_every_name_and_description_once(self) -> None:
        magname_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "fixed" / "magname.json").read_text(
                encoding="utf-8"
            )
        )
        all_records = {
            **self.magic_binding.records,
            **self.skill_binding.records,
        }
        bound_magname = {
            physical_id
            for physical_id in all_records
            if physical_id.startswith("game.magname.")
        }
        self.assertEqual(bound_magname, {row["id"] for row in magname_rows})
        self.assertEqual(len(self.magic_binding.records), 310)
        self.assertEqual(len(self.skill_binding.records), 654)
        self.assertEqual(len(all_records), 964)

        zensho_rows = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "compendium"
                / "fixed"
                / "ability_names.json"
            ).read_text(encoding="utf-8")
        )
        bound_zensho = {
            physical_id
            for physical_id in all_records
            if physical_id.startswith("compendium.ability_names.")
        }
        self.assertEqual(bound_zensho, {row["id"] for row in zensho_rows})
        self.assertEqual(
            len(self.magic_binding.variants) + len(self.skill_binding.variants),
            0,
        )
        self.assertFalse(self.skill_binding.glyph_equivalence)

    def test_console_forms_exist_only_for_proven_battle_actions(self) -> None:
        bindings = {
            **self.magic_binding.records,
            **self.skill_binding.records,
        }
        bound_console = {
            physical_id
            for physical_id in bindings
            if physical_id.startswith("game.btl_mes.")
        }
        excluded = RESERVE_INDEXES | FIELD_ONLY_INDEXES
        expected = {
            f"game.btl_mes.p{49 + index:04d}"
            for index in range(227)
            if index not in excluded
        }
        self.assertEqual(bound_console, expected)
        self.assertEqual(len(bound_console), 199)
        for key in ("traesto", "estoma", "mapper", "liftoma"):
            self.assertNotIn("console_text", self.magic.entries[key].fields)

    def test_duplicate_visible_names_do_not_infer_semantic_sharing(self) -> None:
        first = self.skills.entries["demons_lure_a"]
        second = self.skills.entries["demons_lure_b"]
        self.assertEqual(first.fields["name"].reference, second.fields["name"].reference)
        self.assertEqual(
            first.fields["description"].reference,
            second.fields["description"].reference,
        )
        self.assertEqual(first.status, "unresolved")
        self.assertEqual(second.status, "unresolved")
        self.assertIsNot(first, second)

    def test_psp_reuses_shared_fields_and_exposes_real_revision_debt(self) -> None:
        fields = [
            field
            for catalog in (self.magic, self.skills)
            for entry in catalog.entries.values()
            for field in entry.fields.values()
        ]
        variants = [field.variants["psp"] for field in fields if "psp" in field.variants]
        self.assertEqual(len(variants), 179)
        self.assertEqual(sum(variant.translation is None for variant in variants), 77)
        self.assertEqual(sum(variant.translation == "" for variant in variants), 102)

        agi = self.magic.entries["agi"].fields["description"]
        self.assertEqual(agi.resolve("psp")[1], "")
        maragi = self.magic.entries["maragi"].fields["name"]
        self.assertNotIn("psp", maragi.variants)
        self.assertEqual(maragi.translation, "Maragi")

        for key, reference in (
            ("jigoku_nagashi", "地獄流し"),
            ("kyuuchaku", "吸着"),
        ):
            entry = self.skills.entries[key]
            self.assertEqual(entry.status, "unresolved")
            self.assertEqual(entry.fields["name"].reference, reference)
            self.assertEqual(entry.fields["name"].translation, "")
            self.assertFalse(
                any(
                    asset_ref.startswith(f"{key}.")
                    for asset_ref in self.skill_binding.records.values()
                )
            )

    def test_psp_dormant_replacements_do_not_attach_to_saturn_reserves(self) -> None:
        evil_gaze = self.skills.entries["evil_gaze"].fields["name"]
        death_ring = self.skills.entries["death_ring"].fields["name"]
        cauterizing = self.skills.entries["cauterizing_fist"].fields["name"]
        self.assertNotIn("psp", evil_gaze.variants)
        self.assertNotIn("psp", death_ring.variants)
        self.assertEqual(evil_gaze.translation, "Evil Gaze")
        self.assertEqual(death_ring.translation, "Death Ring")
        self.assertEqual(cauterizing.resolve("psp")[1], "Cauterizing Fist")

        for key in (
            "reserved_skill_125",
            "reserved_skill_129",
            "reserved_skill_141",
            "reserved_skill_222",
            "reserved_skill_225",
        ):
            entry = self.skills.entries[key]
            self.assertEqual(entry.status, "reserve")
            self.assertEqual(entry.fields["name"].translation, "Reserve")

    def test_every_authored_form_declares_its_consumer_surfaces(self) -> None:
        expected = {
            "name": (
                "battle.skill_name",
                "comp.ability_name",
                "compendium.ability_name",
                "status.skill_name",
                "level_up.ability_name",
            ),
            "description": ("battle.help", "comp.help"),
            "console_text": ("battle.console",),
        }
        self.assertEqual(self.magic_binding.field_surfaces, expected)
        self.assertEqual(self.skill_binding.field_surfaces, expected)


if __name__ == "__main__":
    unittest.main()
