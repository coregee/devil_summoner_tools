from __future__ import annotations

import hashlib
import struct
import unittest
from unittest.mock import patch

from engine.shared.compendium_codec import (
    CompactCodec,
    PROFILE_DETAIL_LAYOUT_OFFSET,
    PROFILE_SUMMARY_LAYOUT_OFFSET,
    build_dictionary,
)
from engine.surfaces import compendium_text as surface


class CompendiumTextSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources, _inputs = surface._source_files(None)
        (
            cls.translations,
            cls.profile_ids,
            cls.demon_ids,
            cls.ability_ids,
            cls.race_ids,
            cls.race_description_ids,
            cls.fusion_help_ids,
            cls.status_base_label_ids,
            cls.status_derived_label_ids,
        ) = surface._translations()
        cls.codec = CompactCodec(build_dictionary(cls.translations.values()))
        cls.build = surface.build_compendium_text(cls.sources)

    def test_exact_target_and_patch_inventory(self) -> None:
        self.assertEqual(len(self.build.outputs), 293)
        self.assertEqual(set(self.build.outputs), set(self.sources))
        self.assertEqual(len(self.build.patches[surface.TARGET]), 25)
        self.assertTrue(
            all(
                len(patches) == 1
                for target, patches in self.build.patches.items()
                if target != surface.TARGET
            )
        )
        self.assertEqual(
            sum(len(patches) for patches in self.build.patches.values()), 317
        )
        self.assertEqual(self.build.unresolved_ids, surface.UNRESOLVED_IDS)
        self.assertEqual(self.build.assembly_files, (surface.ASSEMBLY_PATH,))

    def test_default_hashes_and_runtime_capacity_are_deterministic(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.build.outputs[surface.TARGET]).hexdigest(),
            "e333bcee225c5f64bbee88ca907b72bc4201330018cee958c70bddc5ef526232",
        )
        catalogue = hashlib.sha256()
        for path, data in sorted(self.build.outputs.items()):
            catalogue.update(path.encode("ascii"))
            catalogue.update(b"\0")
            catalogue.update(hashlib.sha256(data).digest())
        self.assertEqual(
            catalogue.hexdigest(),
            "ad7774e7e9bf68a87c4255eb350eac1c6f11ba1cd0d67bf15ef2dbe6ed3a6c3b",
        )
        self.assertEqual(self.build.runtime_used_size, 2960)
        self.assertEqual(self.build.runtime_capacity, 30722)
        runtime = self.build.outputs[surface.TARGET][
            surface.RUNTIME_ADDRESS
            - surface.LOAD_ADDRESS : surface.RUNTIME_ADDRESS
            - surface.LOAD_ADDRESS
            + self.build.runtime_used_size
        ]
        self.assertEqual(
            hashlib.sha256(runtime).hexdigest(),
            "0810e27ab3667e0a7184f8d547f4c1c73db22f9935ac22dd0759a08c59a2539e",
        )
        scratch = (
            surface.RUNTIME_ADDRESS
            + self.build.runtime_used_size
            - surface.RUNTIME_SCRATCH_BYTES
        )
        self.assertIn(struct.pack(">I", scratch), runtime)
        self.assertEqual(
            runtime[-surface.RUNTIME_SCRATCH_BYTES :],
            bytes(surface.RUNTIME_SCRATCH_BYTES),
        )
        self.assertNotIn(struct.pack(">I", 0x002881DC), runtime)

    def test_profile_outputs_change_only_the_proved_tail(self) -> None:
        for target, output in self.build.outputs.items():
            source = self.sources[target]
            self.assertEqual(len(output), len(source), target)
            if target == surface.TARGET:
                continue
            self.assertEqual(
                output[: surface.PROFILE_TAIL_OFFSET],
                source[: surface.PROFILE_TAIL_OFFSET],
            )
            self.assertEqual(
                output[surface.PROFILE_TAIL_OFFSET + surface.PROFILE_TAIL_BYTES :],
                source[surface.PROFILE_TAIL_OFFSET + surface.PROFILE_TAIL_BYTES :],
            )

    def test_every_profile_tail_decodes_to_complete_authored_fields(self) -> None:
        by_profile: dict[str, dict[str, str]] = {}
        for record in self.profile_ids:
            parts = record.split(".")
            by_profile.setdefault(parts[2], {})[parts[4]] = self.translations[record]
        for profile, fields in by_profile.items():
            tail = self.build.outputs[f"{profile.upper()}.DAT"][
                surface.PROFILE_TAIL_OFFSET :
                surface.PROFILE_TAIL_OFFSET + surface.PROFILE_TAIL_BYTES
            ]
            self.assertEqual(self.codec.decode_row(tail[:18]), fields["origin"])
            summary = [
                self.codec.decode_row(tail[offset : offset + 28])
                for offset in range(
                    PROFILE_SUMMARY_LAYOUT_OFFSET,
                    PROFILE_DETAIL_LAYOUT_OFFSET,
                    28,
                )
            ]
            detail = [
                self.codec.decode_row(tail[offset : offset + 28])
                for offset in range(
                    PROFILE_DETAIL_LAYOUT_OFFSET,
                    surface.PROFILE_TAIL_BYTES,
                    28,
                )
            ]
            self.assertEqual(
                " ".join(value for value in summary if value), fields["summary"]
            )
            self.assertEqual(
                " ".join(value for value in detail if value), fields["detail"]
            )

    def test_all_catalogue_rows_decode_and_unresolved_rows_remain_stock(self) -> None:
        output = self.build.outputs[surface.TARGET]
        for index, record in enumerate(self.demon_ids):
            row = output[
                surface.DEMON_TABLE_OFFSET + index * 16 :
                surface.DEMON_TABLE_OFFSET + (index + 1) * 16
            ]
            self.assertEqual(self.codec.decode_row(row), self.translations[record])
        for index, record in enumerate(self.ability_ids):
            row = output[
                surface.ABILITY_TABLE_OFFSET + index * 16 :
                surface.ABILITY_TABLE_OFFSET + (index + 1) * 16
            ]
            self.assertEqual(self.codec.decode_row(row), self.translations[record])
        source = self.sources[surface.TARGET]
        for index, record in enumerate(self.race_ids):
            start = surface.RACE_TABLE_OFFSET + index * 6
            row = output[start : start + 6]
            if record in surface.UNRESOLVED_IDS:
                self.assertEqual(row, source[start : start + 6])
            else:
                self.assertEqual(self.codec.decode_row(row), self.translations[record])

        for index in range(surface.RACE_DESCRIPTION_COUNT):
            start = (
                surface.RACE_DESCRIPTION_OFFSET
                + index * surface.RACE_DESCRIPTION_STRIDE
            )
            heading_id = self.race_description_ids[index * 2]
            description_id = self.race_description_ids[index * 2 + 1]
            self.assertEqual(
                self.codec.decode_row(output[start : start + 28]),
                self.translations[heading_id],
            )
            rows = [
                self.codec.decode_row(
                    output[start + offset : start + offset + 28]
                )
                for offset in range(28, surface.RACE_DESCRIPTION_STRIDE, 28)
            ]
            self.assertEqual(
                " ".join(value for value in rows if value),
                self.translations.get(description_id, ""),
            )

        for index, record in enumerate(self.fusion_help_ids):
            start = surface.FUSION_HELP_OFFSET + index * surface.FUSION_HELP_STRIDE
            rows = [
                self.codec.decode_row(output[start + offset : start + offset + 40])
                for offset in (0, 40)
            ]
            self.assertEqual(
                " ".join(value for value in rows if value),
                self.translations[record],
            )

    def test_every_drawer_pointer_links_to_the_readable_wrapper(self) -> None:
        output = self.build.outputs[surface.TARGET]
        pointer = surface.RUNTIME_ADDRESS.to_bytes(4, "big")
        for offset in surface.POINTER_OFFSETS:
            self.assertEqual(output[offset : offset + 4], pointer)
        stat_pointer = output[
            surface.STATUS_GLYPH_POINTER_OFFSET : surface.STATUS_GLYPH_POINTER_OFFSET
            + 4
        ]
        self.assertNotEqual(stat_pointer, struct.pack(">I", surface.ORIGINAL_GLYPH_DRAW))
        source = surface.ASSEMBLY_PATH.read_text(encoding="utf-8")
        self.assertIn("compact_draw:", source)
        self.assertIn("compact_stat_draw:", source)
        self.assertIn("ORIGINAL_DRAW", source)
        self.assertNotIn(".byte", source)
        self.assertNotIn(".word", source)

    def test_stock_blitter_pointer_scan_is_exhaustive(self) -> None:
        source = self.sources[surface.TARGET]
        row_pointer = struct.pack(">I", surface.ORIGINAL_DRAW)
        glyph_pointer = struct.pack(">I", surface.ORIGINAL_GLYPH_DRAW)
        self.assertEqual(
            tuple(
                offset
                for offset in range(len(source))
                if source.startswith(row_pointer, offset)
            ),
            surface.POINTER_OFFSETS,
        )
        self.assertEqual(
            tuple(
                offset
                for offset in range(len(source))
                if source.startswith(glyph_pointer, offset)
            ),
            surface.GLYPH_POINTER_OFFSETS,
        )

    def test_status_labels_use_both_proved_blitter_adapters(self) -> None:
        output = self.build.outputs[surface.TARGET]
        for index, record in enumerate(self.status_derived_label_ids):
            start = surface.STATUS_DERIVED_LABEL_OFFSET + index * 8
            self.assertEqual(
                self.codec.decode_row(output[start : start + 8]),
                self.translations[record],
            )
        font, _metrics, codes, advances = surface._font()
        embedded = surface.build_embedded_font(font, codes, advances)
        labels = tuple(
            self.translations[record] for record in self.status_base_label_ids
        )
        bitmaps = surface._compose_stat_bitmaps(labels, embedded)
        self.assertEqual(len(bitmaps), surface.STATUS_BASE_LABEL_COUNT * 32)
        for glyph in range(surface.STATUS_BASE_LABEL_COUNT):
            cell = bitmaps[glyph * 32 : (glyph + 1) * 32]
            self.assertNotEqual(cell, bytes(32))
            for row in range(0, 32, 4):
                self.assertEqual(cell[row : row + 2], cell[row + 2 : row + 4])

    def test_authored_edit_propagates_to_its_profile_tail(self) -> None:
        changed = dict(self.translations)
        record = "compendium.profiles.dvl_001.o078000.origin"
        changed[record] = "India!"
        mocked = (
            changed,
            self.profile_ids,
            self.demon_ids,
            self.ability_ids,
            self.race_ids,
            self.race_description_ids,
            self.fusion_help_ids,
            self.status_base_label_ids,
            self.status_derived_label_ids,
        )
        with patch.object(surface, "_translations", return_value=mocked):
            edited = surface.build_compendium_text(self.sources)
        self.assertNotEqual(
            edited.outputs["DVL_001.DAT"], self.build.outputs["DVL_001.DAT"]
        )
        edited_codec = CompactCodec(build_dictionary(changed.values()))
        tail = edited.outputs["DVL_001.DAT"][
            surface.PROFILE_TAIL_OFFSET :
            surface.PROFILE_TAIL_OFFSET + surface.PROFILE_TAIL_BYTES
        ]
        self.assertEqual(edited_codec.decode_row(tail[:18]), "India!")

    def test_race_description_and_fusion_help_edits_propagate(self) -> None:
        changed = dict(self.translations)
        description = "compendium.race_descriptions.o06abf0.description"
        help_row = "compendium.fusion_help.o06d828.text"
        changed[description] = "Edited race description."
        changed[help_row] = "Edited fusion help."
        mocked = (
            changed,
            self.profile_ids,
            self.demon_ids,
            self.ability_ids,
            self.race_ids,
            self.race_description_ids,
            self.fusion_help_ids,
            self.status_base_label_ids,
            self.status_derived_label_ids,
        )
        with patch.object(surface, "_translations", return_value=mocked):
            edited = surface.build_compendium_text(self.sources)
        codec = CompactCodec(build_dictionary(changed.values()))
        output = edited.outputs[surface.TARGET]
        self.assertEqual(
            codec.decode_row(
                output[
                    surface.RACE_DESCRIPTION_OFFSET
                    + 28 : surface.RACE_DESCRIPTION_OFFSET
                    + 56
                ]
            ),
            "Edited race description.",
        )
        self.assertEqual(
            codec.decode_row(
                output[
                    surface.FUSION_HELP_OFFSET : surface.FUSION_HELP_OFFSET + 40
                ]
            ),
            "Edited fusion help.",
        )

    def test_tampered_source_and_config_drift_fail_closed(self) -> None:
        changed = dict(self.sources)
        damaged = bytearray(changed[surface.TARGET])
        damaged[-1] ^= 1
        changed[surface.TARGET] = bytes(damaged)
        with self.assertRaisesRegex(ValueError, "verified retail"):
            surface.build_compendium_text(changed)

        config = surface._configuration()
        recipes = list(config.patches[surface.TARGET])
        recipes[0] = recipes[0].__class__(
            recipes[0].group,
            recipes[0].name,
            recipes[0].address + 2,
            recipes[0].expected,
            recipes[0].replacement,
            recipes[0].expected_sha256,
            recipes[0].expected_size,
        )
        drifted = config.__class__(
            config.surface,
            config.targets,
            config.inputs,
            {surface.TARGET: tuple(recipes)},
        )
        with patch.object(
            surface,
            "load_patch_recipe_configuration",
            return_value=drifted,
        ):
            with self.assertRaisesRegex(ValueError, "inventory drifted"):
                surface._configuration()


if __name__ == "__main__":
    unittest.main()
