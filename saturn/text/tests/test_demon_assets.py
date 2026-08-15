from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


PROFILE_FIELDS = {
    "compendium_origin",
    "compendium_summary",
    "compendium_detail",
}
PSP_ONLY_KEYS = {
    "red_cape_unprofiled_a",
    "red_cape_unprofiled_b",
    "yomi_kugutsu",
    "david",
    "enoch",
    "leviathan",
    "skoll",
}


class DemonAssetInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("demons.json")
        cls.name_binding = load_binding(BINDING_ROOT / "demons.json")
        cls.profile_binding = load_binding(
            BINDING_ROOT / "demon_compendium.json"
        )

    def test_catalog_is_complete_and_entity_shaped(self) -> None:
        self.assertEqual(len(self.catalog.entries), 312)
        self.assertEqual(
            sum(len(entry.fields) for entry in self.catalog.entries.values()),
            1_200,
        )
        self.assertEqual(
            sum(entry.status == "reserve" for entry in self.catalog.entries.values()),
            1,
        )
        self.assertEqual(
            sum(
                entry.status == "unresolved"
                for entry in self.catalog.entries.values()
            ),
            9,
        )

        profiles = 0
        for key, entry in self.catalog.entries.items():
            self.assertIn("name", entry.fields)
            present = PROFILE_FIELDS & set(entry.fields)
            self.assertIn(len(present), {0, 3}, key)
            profiles += len(present) == 3
            for field in entry.fields.values():
                self.assertTrue(field.reference)
                self.assertTrue(field.translation)
                self.assertFalse(field.reviewed)
            self.assertNotIn("saturn", key)
            self.assertNotIn("psp", key)
            self.assertIsNone(re.fullmatch(r"(?:dvl|row|r|o)_?[0-9a-f]+", key))
        self.assertEqual(profiles, 296)

    def test_profile_identity_is_not_inferred_from_duplicate_names(self) -> None:
        for key in (
            "guan_yu",
            "guan_yu_rampaging",
            "orgone_ghost_empowered",
            "orgone_ghost_weakened",
            "sid_davis",
            "sid_davis_battle",
            "inaruna_princess",
            "inaruna_vengeful_spirit",
            "shei_form_1",
            "shei_form_2",
            "shei_form_3",
            "shei_form_4",
            "shei_form_5",
        ):
            self.assertEqual(
                PROFILE_FIELDS,
                PROFILE_FIELDS & set(self.catalog.entries[key].fields),
            )

        for key in (
            "preta_unprofiled",
            "slime_unprofiled",
            "ashinaga_unprofiled",
            "tenaga_unprofiled",
            "enku_unprofiled",
            "sid_unprofiled",
            "inaruna_unprofiled",
        ):
            entry = self.catalog.entries[key]
            self.assertEqual(set(entry.fields), {"name"})
            self.assertEqual(entry.status, "unresolved")

        self.assertNotEqual(
            self.catalog.entries["sid_davis"].fields["compendium_detail"].reference,
            self.catalog.entries["sid_davis_battle"]
            .fields["compendium_detail"]
            .reference,
        )

    def test_cross_platform_source_variants_reuse_authored_translation(self) -> None:
        psp_variants = [
            field
            for entry in self.catalog.entries.values()
            for field in entry.fields.values()
            if "psp" in field.variants
        ]
        zensho_variants = [
            field
            for entry in self.catalog.entries.values()
            for field in entry.fields.values()
            if "akuma_zensho" in field.variants
        ]
        self.assertEqual(len(psp_variants), 160)
        self.assertEqual(len(zensho_variants), 5)
        self.assertEqual(
            sum(
                "psp" in entry.fields["name"].variants
                for entry in self.catalog.entries.values()
            ),
            4,
        )
        self.assertEqual(
            sum(
                "psp" in field.variants
                for entry in self.catalog.entries.values()
                for name, field in entry.fields.items()
                if name in PROFILE_FIELDS
            ),
            156,
        )

        odin = self.catalog.entries["odin"].fields["compendium_summary"]
        psp_reference, psp_translation, reviewed = odin.resolve("psp")
        self.assertNotEqual(psp_reference, odin.reference)
        self.assertEqual(psp_translation, odin.translation)
        self.assertFalse(reviewed)

        amon = self.catalog.entries["amon_ra"].fields["name"]
        self.assertEqual(amon.resolve("akuma_zensho")[0], "アメン・ラー")
        self.assertEqual(amon.resolve("akuma_zensho")[1], "Amon-Ra")

    def test_psp_repurposed_entities_do_not_alias_saturn_reserves(self) -> None:
        self.assertTrue(PSP_ONLY_KEYS <= set(self.catalog.entries))
        self.assertIsNot(
            self.catalog.entries["red_cape_unprofiled_a"],
            self.catalog.entries["red_cape_unprofiled_b"],
        )
        for key in ("david", "enoch", "leviathan", "skoll"):
            self.assertEqual(
                set(self.catalog.entries[key].fields),
                {"name", *PROFILE_FIELDS},
            )

        saturn_refs = {
            *self.name_binding.records.values(),
            *self.profile_binding.records.values(),
        }
        self.assertFalse(
            any(
                reference.split(".", 1)[0] in PSP_ONLY_KEYS
                for reference in saturn_refs
            )
        )

    def test_name_binding_covers_both_saturn_name_tables(self) -> None:
        self.assertEqual(len(self.name_binding.records), 638)
        game_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "fixed" / "dvlname.json")
            .read_text(encoding="utf-8")
        )
        zensho_rows = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "compendium"
                / "fixed"
                / "demon_names.json"
            ).read_text(encoding="utf-8")
        )
        game_ids = {row["id"] for row in game_rows}
        zensho_ids = {row["id"] for row in zensho_rows}
        self.assertEqual(set(self.name_binding.records), game_ids | zensho_ids)
        self.assertEqual(len(self.name_binding.variants), 5)
        self.assertTrue(
            all(
                physical_id.startswith("compendium.demon_names.")
                for physical_id in self.name_binding.variants
            )
        )

        game_targets = [self.name_binding.records[row["id"]] for row in game_rows]
        duplicate_targets = {
            target
            for target in game_targets
            if game_targets.count(target) > 1
        }
        self.assertEqual(duplicate_targets, {"boss_reserve.name"})
        self.assertEqual(game_targets.count("boss_reserve.name"), 15)
        self.assertEqual(
            sum(
                asset_ref == "boss_reserve.name"
                for asset_ref in self.name_binding.records.values()
            ),
            30,
        )

    def test_profile_binding_is_exact_and_keeps_saturn_orphans(self) -> None:
        profile_rows = json.loads(
            (TEXT_ROOT / "corpus" / "compendium" / "profiles.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(len(self.profile_binding.records), 876)
        self.assertEqual(
            set(self.profile_binding.records),
            {row["id"] for row in profile_rows},
        )
        self.assertEqual(
            dict(self.profile_binding.glyph_equivalence),
            {
                "0026": "e",
                "0029": "a",
                "002d": "e",
                "002f": "a",
                "026e": "木",
                "0656": "木",
            },
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_001.o078000.origin"
            ],
            "vishnu.compendium_origin",
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_104.o07808e.detail"
            ],
            "shei_form_5.compendium_detail",
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_112.o07808e.detail"
            ],
            "sid_davis.compendium_detail",
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_126.o07808e.detail"
            ],
            "sid_davis_battle.compendium_detail",
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_127.o07808e.detail"
            ],
            "inaruna_princess.compendium_detail",
        )
        self.assertEqual(
            self.profile_binding.records[
                "compendium.profiles.dvl_128.o07808e.detail"
            ],
            "inaruna_vengeful_spirit.compendium_detail",
        )


if __name__ == "__main__":
    unittest.main()
