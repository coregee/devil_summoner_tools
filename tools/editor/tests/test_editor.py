from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.editor.application import EditorApplication
from tools.editor.catalog import CorpusCatalog
from tools.editor.models import EntryKey


class EntryKeyTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        value = "events/police_station.json#police_station_takeover_000.text"
        self.assertEqual(EntryKey.parse(value).id, value)

    def test_rejects_unsafe_asset_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid editor entry id"):
            EntryKey.parse("../outside.json#entry.text")


class ActualCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = EditorApplication()
        cls.entry_id = (
            "events/police_station.json#police_station_takeover_000.text"
        )

    def test_event_dialogue_has_exact_font_preview(self) -> None:
        entry = self.application.catalog.entry(self.entry_id)
        result = self.application.evaluate(self.entry_id, entry["translation"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["surfaces"][0]["name"], "event.dialogue")
        self.assertTrue(result["surfaces"][0]["exact"])
        self.assertTrue(result["preview"]["data_url"].startswith("data:image/png"))

    def test_overlong_unbroken_dialogue_is_rejected(self) -> None:
        result = self.application.evaluate(self.entry_id, "W" * 90)
        self.assertFalse(result["valid"])
        self.assertIn(
            "line_width", {row["code"] for row in result["diagnostics"]}
        )

    def test_functional_token_drift_is_rejected(self) -> None:
        rows = self.application.catalog.list_entries("{item}", 200)["entries"]
        token_row = next(
            (row for row in rows if "{item}" in row["reference"]), None
        )
        if token_row is None:
            self.skipTest("corpus contains no indexed {item} reference")
        result = self.application.evaluate(token_row["id"], "Token removed")
        self.assertFalse(result["valid"])
        self.assertEqual(result["diagnostics"][0]["code"], "asset_contract")


class SavingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.asset_root = root / "assets"
        self.binding_root = root / "bindings"
        self.asset_root.mkdir()
        self.binding_root.mkdir()
        self.asset_path = self.asset_root / "sample.json"
        self.asset_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "kind": "entity_catalog",
                    "entries": {
                        "greeting": {
                            "text": {
                                "reference": "こんにちは",
                                "translation": "Hello",
                            }
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.binding_root / "sample.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "asset": "sample.json",
                    "records": {"game.sample.p00": "greeting.text"},
                    "field_surfaces": {"text": ["event.dialogue"]},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        catalog = CorpusCatalog(
            asset_root=self.asset_root, binding_root=self.binding_root
        )
        self.application = EditorApplication(catalog)
        self.entry_id = "sample.json#greeting.text"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_save_is_atomic_and_refreshes_hash(self) -> None:
        before = self.application.catalog.entry(self.entry_id)
        result = self.application.save(self.entry_id, "Welcome", before["file_hash"])
        self.assertEqual(result["entry"]["translation"], "Welcome")
        document = json.loads(self.asset_path.read_text(encoding="utf-8"))
        self.assertEqual(
            document["entries"]["greeting"]["text"]["translation"], "Welcome"
        )
        self.assertEqual(
            result["entry"]["file_hash"],
            hashlib.sha256(self.asset_path.read_bytes()).hexdigest(),
        )

    def test_stale_hash_does_not_overwrite_external_edit(self) -> None:
        before = self.application.catalog.entry(self.entry_id)
        self.asset_path.write_text(
            self.asset_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "changed on disk"):
            self.application.save(self.entry_id, "Welcome", before["file_hash"])


if __name__ == "__main__":
    unittest.main()
