from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

import engine.surfaces.fmv_subtitles as fmv  # noqa: E402
from engine.core.patching import PatchError  # noqa: E402


class FmvSubtitleEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock, cls.movie = fmv._source_files()
        cls.runtime = fmv._build_runtime()
        cls.build = fmv.build_fmv_subtitles(cls.stock)

    def test_authored_timeline_compiles_to_checked_movie_frames(self) -> None:
        cues = fmv.load_subtitle_cues()
        self.assertEqual(len(cues), 9)
        self.assertEqual(
            [(cue.start_frame, cue.end_frame) for cue in cues],
            [
                (11, 32),
                (37, 63),
                (63, 90),
                (90, 132),
                (140, 202),
                (202, 244),
                (249, 290),
                (290, 332),
                (332, 399),
            ],
        )
        self.assertEqual(fmv.centiseconds_to_frame(0), 0)
        self.assertEqual(fmv.centiseconds_to_frame(90), 11)
        self.assertEqual(fmv.centiseconds_to_frame(100), 12)

    def test_every_line_is_centered_and_uses_generated_font16(self) -> None:
        self.assertEqual(
            [len(cue.lines) for cue in self.build.cues],
            [1, 2, 2, 2, 2, 2, 2, 2, 2],
        )
        for cue in self.build.cues:
            for line in cue.lines:
                self.assertEqual(line.x, (fmv.MOVIE_WIDTH - line.width) // 2)
                self.assertGreater(line.width, 0)
                self.assertLessEqual(line.x + line.width, fmv.MOVIE_WIDTH)
                for packed in line.packed_glyphs:
                    self.assertGreater(packed >> 12, 0)
                    self.assertLessEqual(packed >> 12, 15)
                    self.assertGreater(packed & 0x0FFF, 0)

    def test_runtime_data_and_hook_inventory_are_exact(self) -> None:
        self.assertEqual(self.runtime.primary_used, 1004)
        self.assertEqual(self.runtime.secondary_used, 214)
        self.assertEqual(self.runtime.code_used, 464)
        self.assertEqual(len(self.runtime.primary), fmv.PRIMARY_DATA_CAPACITY)
        self.assertEqual(len(self.runtime.secondary), fmv.SECONDARY_DATA_CAPACITY)
        self.assertEqual(len(self.runtime.code), fmv.RUNTIME_CAPACITY)
        self.assertFalse(any(self.runtime.primary[self.runtime.primary_used :]))
        self.assertFalse(any(self.runtime.secondary[self.runtime.secondary_used :]))
        self.assertFalse(any(self.runtime.code[self.runtime.code_used :]))
        self.assertEqual(
            [patch.name for patch in self.build.patches],
            [
                "subtitle_data_primary",
                "subtitle_runtime",
                "subtitle_data_secondary",
                "blocking_player_pointer",
                "async_init_pointer",
                "presenter_pointer",
            ],
        )
        pointers = {
            patch.name: struct.unpack(">I", patch.replacement)[0]
            for patch in self.build.patches[-3:]
        }
        self.assertEqual(
            pointers,
            {
                "blocking_player_pointer": self.runtime.labels[
                    "fmv_blocking_player_wrapper"
                ],
                "async_init_pointer": self.runtime.labels["fmv_async_init_wrapper"],
                "presenter_pointer": self.runtime.labels["fmv_present_wrapper"],
            },
        )

    def test_runtime_masks_the_advance_out_of_each_font_code(self) -> None:
        offset = self.runtime.labels["fmv_line_loop"] - fmv.RUNTIME_ADDRESS
        self.assertEqual(
            self.runtime.code[offset : offset + 32],
            bytes.fromhex(
                "6485644d244889116943491949094909"
                "60434018400840084019400940096403"
            ),
        )

    def test_cue_table_points_only_into_owned_data_arenas(self) -> None:
        count, reserved = struct.unpack_from(">HH", self.runtime.primary, 8)
        self.assertEqual((count, reserved), (9, 0))
        ranges = (
            (
                fmv.PRIMARY_DATA_ADDRESS,
                fmv.PRIMARY_DATA_ADDRESS + fmv.PRIMARY_DATA_CAPACITY,
            ),
            (
                fmv.SECONDARY_DATA_ADDRESS,
                fmv.SECONDARY_DATA_ADDRESS + fmv.SECONDARY_DATA_CAPACITY,
            ),
        )
        for index, cue in enumerate(self.build.cues):
            start, end, first, second = struct.unpack_from(
                ">HHII", self.runtime.primary, 12 + index * 12
            )
            self.assertEqual((start, end), (cue.start_frame, cue.end_frame))
            pointers = (first,) if len(cue.lines) == 1 else (first, second)
            self.assertEqual(second == 0, len(cue.lines) == 1)
            for pointer in pointers:
                self.assertTrue(any(low <= pointer < high for low, high in ranges))

    def test_source_movie_is_a_verified_input_not_an_output(self) -> None:
        self.assertEqual(len(self.movie), fmv.MOVIE_SIZE)
        self.assertEqual(fmv._sha256(self.movie), fmv.MOVIE_SHA256)
        self.assertEqual(
            dict(self.build.source_inputs),
            {
                "game:EVENT.BIN": fmv._sha256(self.stock),
                f"game:{fmv.MOVIE_TARGET}": fmv.MOVIE_SHA256,
            },
        )
        self.assertEqual(len(self.build.data), len(self.stock))

    def test_invalid_timing_and_text_fail_before_patching(self) -> None:
        document = json.loads(fmv.ASSET_PATH.read_text(encoding="utf-8"))
        document["movies"]["start2_news"]["cues"][1]["start"] = 200
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitles.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                fmv.load_subtitle_cues(path)

        base = bytearray(self.stock)
        base[0xEE70] ^= 1
        with self.assertRaises(PatchError):
            fmv.build_fmv_subtitles(bytes(base))


if __name__ == "__main__":
    unittest.main()
