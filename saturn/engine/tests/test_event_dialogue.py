from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.build import EVENT_DIALOGUE_OUTPUT_PATH, build_event_dialogue  # noqa: E402
from engine.core.patching import Patch, PatchError, apply_patches  # noqa: E402
from engine.surfaces.event_dialogue import (  # noqa: E402
    ASSEMBLY_ROOT,
    BUILD_PATH,
    CONFIG_PATH,
)


class EventDialogueEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_event_dialogue()
        cls.manifest = json.loads(cls.outputs[BUILD_PATH])

    def test_proven_event_only_patch_is_reproduced(self) -> None:
        event = self.outputs[EVENT_DIALOGUE_OUTPUT_PATH]
        self.assertEqual(len(event), 354072)
        self.assertEqual(
            hashlib.sha256(event).hexdigest(),
            "b9f988d6a3a2dffa9ef345383bc7c57a4571899b1f62c310e746e3524c795195",
        )

    def test_patch_recipe_has_no_opaque_replacements(self) -> None:
        source = CONFIG_PATH.read_text(encoding="utf-8")
        document = json.loads(source)
        self.assertEqual(document["version"], 2)
        self.assertNotIn('"replacement"', source)
        self.assertEqual(
            set(self.manifest["assembly_inputs"]),
            {
                "shared/event_window/absolute_jump.s",
                "shared/event_window/advance.s",
                "event_dialogue/font12_word_glyph.s",
                "shared/event_window/menu_glyph.s",
                "shared/event_window/packed_fetch.s",
                "event_dialogue/space_advance.s",
                "event_dialogue/tracked_font_loader.s",
                "shared/event_window/two_glyph_pacing.s",
                "font16_subpixel_blitter.s",
                "font16_surface_blitter.s",
            },
        )
        self.assertTrue(
            all(
                (ASSEMBLY_ROOT / relative).is_file()
                for relative in self.manifest["assembly_inputs"]
            )
        )

    def test_patch_application_rejects_overlap_before_writing(self) -> None:
        patches = (
            Patch("one", "first", 0x1000, b"ab", b"AB"),
            Patch("two", "second", 0x1001, b"bc", b"BC"),
        )
        with self.assertRaisesRegex(PatchError, "overlap"):
            apply_patches(b"abcd", 0x1000, patches)

    def test_patch_application_rejects_wrong_source_bytes(self) -> None:
        patch = Patch("one", "site", 0x1000, b"ab", b"AB")
        with self.assertRaisesRegex(PatchError, "did not match"):
            apply_patches(b"xbcd", 0x1000, (patch,))


if __name__ == "__main__":
    unittest.main()
