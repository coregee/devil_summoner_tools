from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path, PurePosixPath

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import (  # noqa: E402
    BINDING_ROOT,
    CORPUS_ROOT,
    load_asset,
    load_binding,
)


class CompendiumCatalogueAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.description_asset = load_asset(
            PurePosixPath("compendium/race_descriptions.json")
        )
        cls.ui_asset = load_asset(PurePosixPath("compendium/ui.json"))
        cls.bindings = tuple(
            load_binding(BINDING_ROOT / name)
            for name in (
                "compendium_race_description_headings.json",
                "compendium_race_descriptions.json",
                "compendium_ui.json",
            )
        )
        cls.description_rows = json.loads(
            (
                CORPUS_ROOT
                / "compendium"
                / "fixed"
                / "race_descriptions.json"
            ).read_text(encoding="utf-8")
        )
        cls.fusion_rows = json.loads(
            (
                CORPUS_ROOT / "compendium" / "fixed" / "fusion_help.json"
            ).read_text(encoding="utf-8")
        )

    def test_all_107_physical_fields_have_one_explicit_owner(self) -> None:
        physical_ids = {
            row["id"] for row in (*self.description_rows, *self.fusion_rows)
        }
        owners: dict[str, int] = {}
        unresolved: set[str] = set()
        for binding in self.bindings:
            for physical_id in binding.records:
                owners[physical_id] = owners.get(physical_id, 0) + 1
            unresolved.update(binding.unresolved)
        self.assertEqual(len(physical_ids), 107)
        self.assertEqual(set(owners), physical_ids)
        self.assertTrue(all(count == 1 for count in owners.values()))
        self.assertEqual(
            unresolved,
            {
                "compendium.race_descriptions.o06c2e8.description",
                "compendium.race_descriptions.o06c518.description",
                "compendium.race_descriptions.o06c5a4.description",
            },
        )

    def test_race_descriptions_and_fusion_help_are_complete_authored_text(self) -> None:
        self.assertEqual(len(self.description_asset.entries), 44)
        self.assertTrue(
            all(
                entry.fields["text"].translation
                for entry in self.description_asset.entries.values()
            )
        )
        help_entries = {
            key: entry
            for key, entry in self.ui_asset.entries.items()
            if key not in {"no_data_heading", "blank_description"}
        }
        self.assertEqual(len(help_entries), 11)
        self.assertTrue(
            all(entry.fields["text"].translation for entry in help_entries.values())
        )
        self.assertEqual(
            self.ui_asset.entries["no_data_heading"].fields["text"].translation,
            "NO DATA",
        )

    def test_bonus_races_do_not_collapse_placeholders(self) -> None:
        races = load_asset(PurePosixPath("races.json"))
        self.assertEqual(
            races.entries["vengeful_spirit"].fields["name"].translation,
            "Vengeful Spirit",
        )
        self.assertEqual(
            races.entries["fiend"].fields["name"].translation,
            "Fiend",
        )
        race_binding = load_binding(BINDING_ROOT / "races.json")
        self.assertEqual(len(race_binding.unresolved), 2)
        self.assertEqual(
            race_binding.variants[
                "compendium.race_names.supplement.r0001"
            ],
            "compendium_table",
        )


if __name__ == "__main__":
    unittest.main()
