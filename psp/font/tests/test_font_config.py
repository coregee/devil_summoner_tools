from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from psp.font.util.definitions import CONFIG_ROOT, load_definition, load_definitions


class PspFontDefinitionTests(unittest.TestCase):
    def test_catalogues_every_original_project_resource_role(self) -> None:
        definitions = load_definitions()
        self.assertEqual(len(definitions), 12)
        self.assertEqual(sum(len(value.targets) for value in definitions), 20)
        self.assertEqual(
            {
                value.resource_id
                for value in definitions
                if value.confidence == "runtime_proven"
            },
            {"eve_kanji_dialogue", "datapack_font16_pages"},
        )
        self.assertTrue(all(value.platform == "psp" for value in definitions))

    def test_eve_ascii_bank_is_the_only_initial_editable_domain(self) -> None:
        definitions = load_definitions()
        eve = next(value for value in definitions if value.resource_id == "eve_kanji_dialogue")
        self.assertEqual(len(eve.replacements), 95)
        self.assertEqual(set(eve.replacements), set(range(0x1E20, 0x1E7F)))
        self.assertEqual(
            "".join(eve.replacements[code] for code in sorted(eve.replacements)),
            "0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
            "abcdefghijklmnopqrstuvwxyz{|}~!\"#$%&'()*+,-./ ",
        )
        self.assertTrue(
            all(
                not value.replacements
                for value in definitions
                if value.resource_id != eve.resource_id
            )
        )

    def test_paged_font16_retains_all_seven_physical_targets(self) -> None:
        definition = next(
            value
            for value in load_definitions()
            if value.resource_id == "datapack_font16_pages"
        )
        self.assertEqual(definition.glyph_count, 7 * 256)
        self.assertEqual(definition.logical_target_indices, tuple(range(7)))
        self.assertEqual(
            [target.member_index for target in definition.targets],
            list(range(9, 16)),
        )

    def test_source_override_round_trips_without_claiming_raster_ownership(self) -> None:
        source = CONFIG_ROOT / "game" / "datapack_font8_gim.json"
        document = json.loads(source.read_text(encoding="utf-8"))
        document["source_overrides"] = {"17": "reviewed glyph"}
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / source.name
            path.write_text(json.dumps(document), encoding="utf-8")
            definition = load_definition(path)
        self.assertEqual(definition.glyphs[17], "reviewed glyph")
        self.assertEqual(definition.replacements, {})


if __name__ == "__main__":
    unittest.main()
