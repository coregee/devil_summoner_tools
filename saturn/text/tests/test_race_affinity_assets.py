from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import BINDING_ROOT, load_asset, load_binding  # noqa: E402


class RaceAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("races.json")
        cls.binding = load_binding(BINDING_ROOT / "races.json")
        cls.formats = load_asset("battle/analyze_formats.json")

    def test_catalog_has_semantic_and_surface_specific_forms(self) -> None:
        self.assertEqual(len(self.catalog.entries), 48)
        self.assertEqual(
            sum(len(entry.fields) for entry in self.catalog.entries.values()),
            136,
        )
        self.assertEqual(
            self.catalog.entries["deity"].fields["name"].translation,
            "Deity",
        )
        human = self.catalog.entries["human"]
        self.assertEqual(human.fields["name"].translation, "Human")
        self.assertEqual(human.fields["fusion_name"].translation, "Time")
        self.assertEqual(
            human.fields["name"].resolve("psp")[:2],
            ("", ""),
        )

        previews = tuple(
            entry.fields["fusion_preview_label"].translation
            for entry in list(self.catalog.entries.values())[:43]
        )
        self.assertEqual(previews[:5], ("DE", "MG", "HR", "AV", "TR"))
        self.assertEqual(previews[-2:], ("ZO", "HU"))
        self.assertEqual(
            self.catalog.entries["megami"].fields[
                "fusion_chart_label"
            ].translation,
            "Mega",
        )
        self.assertEqual(
            (
                self.catalog.entries["time"].fields["name"].reference,
                self.catalog.entries["time"]
                .fields["fusion_group_label"]
                .translation,
            ),
            ("時間", "Time"),
        )

    def test_game_and_compendium_occurrences_bind_explicitly(self) -> None:
        self.assertEqual(len(self.binding.records), 181)
        self.assertEqual(len(self.binding.additional_uses), 43)
        self.assertEqual(
            sum(len(uses) for uses in self.binding.additional_uses.values()),
            87,
        )
        self.assertEqual(
            self.binding.records["game.normcom_tables.races.r0000"],
            "deity.name",
        )
        self.assertEqual(
            self.binding.records["compendium.race_names.standard.r0000"],
            "deity.name",
        )
        self.assertEqual(
            self.binding.records["compendium.race_names.human.r0000"],
            "human.name",
        )
        self.assertEqual(
            self.binding.records["compendium.race_names.supplement.r0000"],
            "zoma.name",
        )
        self.assertEqual(len(self.binding.unresolved), 4)
        self.assertEqual(
            self.binding.records["game.shopsmp.m0161.p00"],
            "deity.name",
        )
        self.assertEqual(
            self.binding.records["game.shopsmp.m0222.p00"],
            "herald.fusion_chart_label",
        )
        self.assertEqual(
            self.binding.records["game.shopsmp.m0203.p00"],
            "time.name",
        )
        self.assertEqual(
            self.binding.records["game.shopsmp.m0218.p00"],
            "time.fusion_group_label",
        )

        physical = json.loads(
            (
                TEXT_ROOT
                / "corpus"
                / "compendium"
                / "addressed"
                / "race_names.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(physical), 48)
        self.assertEqual(
            {row["id"] for row in physical},
            {
                physical_id
                for physical_id in self.binding.records
                if physical_id.startswith("compendium.race_names.")
            },
        )

    def test_unproved_bonus_disc_labels_remain_visible(self) -> None:
        self.assertEqual(
            self.catalog.entries["vengeful_spirit"].fields["name"].reference,
            "怨霊",
        )
        self.assertEqual(
            self.catalog.entries["fiend"].fields["name"].translation,
            "",
        )
        placeholders = (
            self.catalog.entries["compendium_race_placeholder_a"],
            self.catalog.entries["compendium_race_placeholder_b"],
        )
        self.assertTrue(all(entry.status == "reserve" for entry in placeholders))
        self.assertEqual(
            placeholders[0].fields["name"].reference,
            placeholders[1].fields["name"].reference,
        )

    def test_analyze_heading_punctuation_is_authored(self) -> None:
        entry = self.formats.entries["race_heading"]
        self.assertEqual(dict(entry.placeholders), {"race": "demon_race"})
        self.assertEqual(
            (
                entry.fields["text"].reference,
                entry.fields["text"].translation,
            ),
            ("{race}:", "{race}:"),
        )


class AffinityAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_asset("affinities.json")
        cls.binding = load_binding(BINDING_ROOT / "affinities.json")

    def test_all_detailed_and_compact_fields_are_authored(self) -> None:
        self.assertEqual(len(self.catalog.entries), 96)
        self.assertEqual(
            sum(len(entry.fields) for entry in self.catalog.entries.values()),
            162,
        )
        self.assertEqual(len(self.binding.records), 162)
        self.assertEqual(
            sum(entry.status == "reserve" for entry in self.catalog.entries.values()),
            30,
        )
        self.assertEqual(
            sum(
                "battle_summary" in entry.fields
                for entry in self.catalog.entries.values()
            ),
            66,
        )
        self.assertEqual(
            self.binding.field_surfaces,
            {
                "description": ("status.affinity",),
                "battle_summary": ("battle.analyze_affinity",),
            },
        )

    def test_equal_compact_text_does_not_collapse_semantic_slots(self) -> None:
        weak_fire = [
            key
            for key, entry in self.catalog.entries.items()
            if "battle_summary" in entry.fields
            and entry.fields["battle_summary"].reference == "火炎に弱い"
        ]
        self.assertEqual(len(weak_fire), 6)
        self.assertEqual(len(set(weak_fire)), 6)
        physical_assets = {
            asset_ref
            for physical_id, asset_ref in self.binding.records.items()
            if physical_id.startswith("game.combat_analysis_affinities.")
            and self.catalog.field(asset_ref).reference == "火炎に弱い"
        }
        self.assertEqual(
            physical_assets,
            {f"{key}.battle_summary" for key in weak_fire},
        )

    def test_psp_reuses_exact_text_and_surfaces_only_real_variants(self) -> None:
        psp_variants = [
            entry.fields["description"].variants["psp"]
            for entry in self.catalog.entries.values()
            if "psp" in entry.fields["description"].variants
        ]
        self.assertEqual(len(psp_variants), 31)
        self.assertEqual(sum(variant.translation == "" for variant in psp_variants), 29)
        self.assertEqual(sum(variant.translation is None for variant in psp_variants), 2)
        self.assertEqual(
            self.catalog.entries["reserved_affinity_068"]
            .fields["description"]
            .variants["psp"]
            .reference,
            "破魔・呪殺無効{n}火・氷・{GLYPH:060d}吸収",
        )

    def test_binding_is_positionally_complete(self) -> None:
        detailed = [
            physical_id
            for physical_id in self.binding.records
            if physical_id.startswith("game.normcom_tables.affinities.")
        ]
        compact = [
            physical_id
            for physical_id in self.binding.records
            if physical_id.startswith("game.combat_analysis_affinities.")
        ]
        self.assertEqual(
            detailed,
            [f"game.normcom_tables.affinities.r{index:04d}" for index in range(96)],
        )
        self.assertEqual(
            compact,
            [
                f"game.combat_analysis_affinities.affinities.r{index:04d}"
                for index in range(66)
            ],
        )


if __name__ == "__main__":
    unittest.main()
