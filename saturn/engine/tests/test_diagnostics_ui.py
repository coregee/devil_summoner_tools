from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.diagnostics_ui as diagnostics  # noqa: E402


class DiagnosticsUiEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = diagnostics.build_diagnostics_ui()

    def test_stock_identical_defaults_and_exact_recipe_inventory(self) -> None:
        self.assertEqual(len(self.build.patches), 11)
        self.assertEqual(
            {
                target: hashlib.sha256(data).hexdigest()
                for target, data in self.build.outputs.items()
            },
            {
                "SNDTEST.BIN": "1448c315929218bbf9ee8dd2cc3192fe3f5ae50cc225b40c8bfe0fc3ed4491ac",
                "TEST3D.BIN": "858acdeacc39c18f2309cd653f18290d73d46005b169841803b4c3982a8e0427",
            },
        )
        self.assertEqual(
            [patch.name for patch in self.build.patches],
            [
                "title",
                "request_number",
                "sound_effect_request_number",
                "exit_message",
                "title",
                "control",
                "map_number",
                "direction",
                "x_position",
                "y_position",
                "launch",
            ],
        )

    def test_authored_edits_are_ascii_nul_terminated_and_capacity_checked(self) -> None:
        real_loader = diagnostics.load_asset

        def edited_asset(name: str):
            catalog = real_loader(name)
            entries = {}
            for key, entry in catalog.entries.items():
                field = entry.fields["text"]
                translation = field.translation
                if name == "diagnostics/sound_test.json" and key == "title":
                    translation = "Audio Test"
                entries[key] = SimpleNamespace(
                    fields={
                        "text": SimpleNamespace(
                            reference=field.reference,
                            translation=translation,
                        )
                    }
                )
            return SimpleNamespace(entries=entries)

        with patch.object(diagnostics, "load_asset", side_effect=edited_asset):
            edited = diagnostics.build_diagnostics_ui()
        self.assertEqual(
            edited.outputs["SNDTEST.BIN"][0x6FAC:0x6FC0],
            b"Audio Test\0".ljust(20, b"\0"),
        )
        self.assertEqual(
            edited.outputs["TEST3D.BIN"], self.build.outputs["TEST3D.BIN"]
        )

        def overflowing_asset(name: str):
            catalog = edited_asset(name)
            if name == "diagnostics/sound_test.json":
                catalog.entries["request_number"].fields["text"].translation = "TOO LONG"
            return catalog

        with patch.object(
            diagnostics, "load_asset", side_effect=overflowing_asset
        ), self.assertRaisesRegex(ValueError, "request_number uses 9/8 bytes"):
            diagnostics.build_diagnostics_ui()

    def test_manifest_inputs_are_explicit_and_no_assembly_is_claimed(self) -> None:
        self.assertEqual(self.build.assembly_files, ())
        self.assertEqual(
            {path.name for path in self.build.asset_files},
            {"sound_test.json", "test_3d.json"},
        )
        self.assertEqual(
            set(self.build.source_inputs),
            {"game:SNDTEST.BIN", "game:TEST3D.BIN"},
        )
        self.assertIn(diagnostics.SOUND_BINDING_PATH, self.build.runtime_input_files)
        self.assertIn(diagnostics.TEST3D_CORPUS_PATH, self.build.runtime_input_files)


if __name__ == "__main__":
    unittest.main()
