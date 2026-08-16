from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from event_inventory import build_inventory  # noqa: E402


class GeneralEventInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = build_inventory()
        cls.messages = cls.inventory["messages"]

    def test_inventory_partitions_every_general_event_page(self) -> None:
        self.assertEqual(
            self.inventory["summary"],
            {
                "sources": 4,
                "messages": 1103,
                "pages": 2028,
                "bound_pages": 1368,
                "unbound_pages": 660,
                "curated_scenes": 59,
                "curated_messages": 792,
                "unclassified_messages": 311,
            },
        )
        pages = [
            page["physical_id"]
            for message in self.messages
            for page in message["pages"]
        ]
        self.assertEqual(len(pages), len(set(pages)))

        expected: set[str] = set()
        for source in ("mesfile", "evfile_0", "evfile_1", "evfile_2"):
            rows = json.loads(
                (TEXT_ROOT / "corpus" / "game" / "eve" / f"{source}.json")
                .read_text(encoding="utf-8")
            )
            expected.update(row["id"] for row in rows)
        self.assertEqual(set(pages), expected)

    def test_message_boundaries_and_literal_evidence_are_preserved(self) -> None:
        by_id = {message["physical_group"]: message for message in self.messages}
        mesfile = by_id["game.mesfile.m0000"]
        self.assertEqual(
            [page["physical_id"] for page in mesfile["pages"]],
            ["game.mesfile.m0000.p00"],
        )
        self.assertEqual(mesfile["evidence"]["literal_speaker_cues"], ["女性"])
        self.assertEqual(mesfile["evidence"]["named_tokens"], ["n"])

        opening = by_id["game.evfile_0.m0000"]
        self.assertEqual(len(opening["pages"]), 2)
        self.assertEqual(opening["evidence"]["raw_tokens"], ["GLYPH:010d"])
        self.assertEqual(opening["curation"]["scene"], "dds_net_profile_renewal")
        self.assertEqual(opening["curation"]["consumer"], "ui.profile_entry")
        self.assertEqual(
            opening["curation"]["story_state"], "initial_profile_renewal"
        )
        self.assertEqual(
            opening["curation"]["choice_structure"], "profile_entry_workflow"
        )
        self.assertEqual(opening["curation"]["call_sites"], [])
        self.assertEqual(
            opening["pages"][0]["asset_uses"],
            ["ui/profile_entry.json#dds_net_welcome.text"],
        )

        redman = by_id["game.evfile_0.m0016"]
        self.assertEqual(
            redman["curation"]["scene"], "dds_net_redman_correspondence"
        )
        self.assertEqual(redman["curation"]["consumer"], "events.dds_net")
        self.assertEqual(redman["binding_state"], "bound")
        self.assertEqual(
            redman["pages"][0]["asset_uses"],
            ["events/dds_net.json#dds_net_redman_correspondence_000.text"],
        )

    def test_leading_item_substitutions_remain_visible(self) -> None:
        item_pages = {
            page["physical_id"]
            for message in self.messages
            if "item_name" in message["evidence"]["named_tokens"]
            for page in message["pages"]
            if "{item_name}" in page["reference"]
        }
        self.assertEqual(
            item_pages,
            {
                "game.evfile_1.m0063.p00",
                "game.evfile_1.m0064.p00",
                "game.evfile_1.m0079.p00",
                "game.evfile_2.m0072.p00",
            },
        )

    def test_malformed_page_sequence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            template = {
                "source_encoding": "test",
                "output_encoding": "",
                "reference": "text",
                "translation": "",
                "note": "",
            }
            for source in ("mesfile", "evfile_0", "evfile_1", "evfile_2"):
                page = dict(template)
                page["id"] = f"game.{source}.m0000.p00"
                if source == "mesfile":
                    page["id"] = "game.mesfile.m0000.p01"
                (corpus_root / f"{source}.json").write_text(
                    json.dumps([page]), encoding="utf-8"
                )
            with self.assertRaisesRegex(ValueError, "not contiguous from p00"):
                build_inventory(
                    corpus_root=corpus_root,
                    binding_root=corpus_root / "empty_bindings",
                    scenes_path=None,
                )

    def test_unknown_scene_group_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            scenes_path = temporary_root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scenes": {
                            "unknown": {
                                "consumer": "event.unknown",
                                "physical_groups": ["game.evfile_0.m9999"],
                                "location": None,
                                "story_state": None,
                                "choice_structure": None,
                                "call_sites": [],
                                "note": "Synthetic invalid scene.",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown physical groups"):
                build_inventory(
                    binding_root=temporary_root / "empty_bindings",
                    scenes_path=scenes_path,
                )


if __name__ == "__main__":
    unittest.main()
