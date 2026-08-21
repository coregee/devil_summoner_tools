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
        self.assertEqual(self.runtime.primary_used, 998)
        self.assertEqual(self.runtime.secondary_used, 384)
        self.assertEqual(self.runtime.tertiary_used, 512)
        self.assertEqual(self.runtime.code_used, 564)
        self.assertEqual(len(self.runtime.primary), fmv.PRIMARY_DATA_CAPACITY)
        self.assertEqual(len(self.runtime.secondary), fmv.SECONDARY_DATA_CAPACITY)
        self.assertEqual(len(self.runtime.tertiary), fmv.TERTIARY_DATA_CAPACITY)
        self.assertEqual(len(self.runtime.code), fmv.RUNTIME_CAPACITY)
        self.assertFalse(any(self.runtime.primary[self.runtime.primary_used :]))
        self.assertFalse(any(self.runtime.secondary[self.runtime.secondary_used :]))
        self.assertFalse(any(self.runtime.tertiary[self.runtime.tertiary_used :]))
        self.assertFalse(any(self.runtime.code[self.runtime.code_used :]))
        self.assertEqual(
            [patch.name for patch in self.build.patches],
            [
                "subtitle_data_primary",
                "subtitle_runtime",
                "subtitle_data_secondary",
                "subtitle_data_tertiary",
                "blocking_player_pointer",
                "async_init_pointer",
                "async_launcher_init_pointer",
                "stream_presenter_pointer",
                "presenter_pointer",
            ],
        )
        pointers = {
            patch.name: struct.unpack(">I", patch.replacement)[0]
            for patch in self.build.patches[4:]
        }
        self.assertEqual(
            pointers,
            {
                "blocking_player_pointer": self.runtime.labels[
                    "fmv_blocking_player_wrapper"
                ],
                "async_init_pointer": self.runtime.labels["fmv_async_init_wrapper"],
                "async_launcher_init_pointer": self.runtime.labels[
                    "fmv_async_init_wrapper"
                ],
                "stream_presenter_pointer": self.runtime.labels[
                    "fmv_stream_present_wrapper"
                ],
                "presenter_pointer": self.runtime.labels["fmv_present_wrapper"],
            },
        )

    def test_runtime_resolves_dense_embedded_glyph_tokens(self) -> None:
        offset = self.runtime.labels["fmv_line_loop"] - fmv.RUNTIME_ADDRESS
        self.assertEqual(
            self.runtime.code[offset : offset + 32],
            bytes.fromhex(
                "6484644c2448890e74ff6043d126091c"
                "699c44086043d125041e65a3b00966b3"
            ),
        )

    def test_runtime_embeds_every_required_font16_mask(self) -> None:
        codes = {
            packed & 0x0FFF
            for cue in self.runtime.cues
            for line in cue.lines
            for packed in line.packed_glyphs
        }
        self.assertEqual(len(codes), 32)
        font = fmv.FONT16_PATH.read_bytes()
        owned_data = (
            self.runtime.primary
            + self.runtime.secondary
            + self.runtime.tertiary
        )
        for code in codes:
            glyph = font[code * 32 : (code + 1) * 32]
            self.assertEqual(len(glyph), 32)
            self.assertIn(glyph, owned_data)
        self.assertNotIn(
            struct.pack(">I", 0x0021A000),
            self.runtime.code[: self.runtime.code_used],
        )

    def test_runtime_aligns_font16_rows_before_testing_shll_carry(self) -> None:
        code = self.runtime.code[: self.runtime.code_used]
        self.assertIn(bytes.fromhex("611d4128e210"), code)

    def test_stock_start2_async_call_chain_reaches_the_stream_hook(self) -> None:
        movie_name_pointer = struct.unpack_from(
            ">I",
            self.stock,
            fmv.MOVIE_NAME_TABLE
            + fmv.MOVIE_INDEX * 4
            - fmv.LOAD_ADDRESS,
        )[0]
        movie_name_offset = movie_name_pointer - fmv.LOAD_ADDRESS
        self.assertEqual(
            self.stock[movie_name_offset : movie_name_offset + 11],
            b"START2.CPK\0",
        )

        handler_pointer = struct.unpack_from(
            ">I",
            self.stock,
            fmv.SCRIPT_DISPATCH_TABLE + 13 * 4 - fmv.LOAD_ADDRESS,
        )[0]
        self.assertEqual(handler_pointer, fmv.ASYNC_MOVIE_SCRIPT_HANDLER)
        self.assertEqual(
            struct.unpack_from(
                ">I", self.stock, 0x0602DBA0 - fmv.LOAD_ADDRESS
            )[0],
            fmv.ASYNC_MOVIE_LAUNCHER,
        )
        self.assertEqual(
            self.stock[
                0x0602DB86 - fmv.LOAD_ADDRESS : 0x0602DB94 - fmv.LOAD_ADDRESS
            ],
            bytes.fromhex("6603666d688dd1046583410be400"),
        )

        self.assertEqual(
            struct.unpack_from(
                ">I", self.stock, 0x060396BC - fmv.LOAD_ADDRESS
            )[0],
            fmv.ASYNC_MOVIE_INDEX,
        )
        self.assertEqual(
            struct.unpack_from(
                ">I", self.stock, 0x060396D4 - fmv.LOAD_ADDRESS
            )[0],
            fmv.MOVIE_NAME_TABLE,
        )
        self.assertEqual(
            struct.unpack_from(
                ">I", self.stock, 0x060396F0 - fmv.LOAD_ADDRESS
            )[0],
            fmv.STOCK_ASYNC_INIT,
        )
        self.assertEqual(
            struct.unpack_from(
                ">I", self.stock, 0x06039078 - fmv.LOAD_ADDRESS
            )[0],
            fmv.STOCK_STREAM_PRESENTER,
        )

    def test_runtime_draws_to_vdp_destinations_after_stock_presenters(self) -> None:
        self.assertEqual(fmv.WHITE_PIXEL, 0x80FFFFFF)
        self.assertEqual(fmv.SHADOW_PIXEL, 0x80010101)
        self.assertEqual(fmv.SHADOW_PIXEL_16 & 0x8000, 0x8000)
        blocking_source = 0x06039390 - fmv.LOAD_ADDRESS
        self.assertEqual(
            self.stock[blocking_source : blocking_source + 4],
            struct.pack(">I", fmv.DECODED_FRAMEBUFFER),
        )
        stream_source = 0x06039074 - fmv.LOAD_ADDRESS
        self.assertEqual(
            self.stock[stream_source : stream_source + 4],
            struct.pack(">I", fmv.DECODED_FRAMEBUFFER),
        )
        dma_setup = 0x0602A760 - fmv.LOAD_ADDRESS
        self.assertEqual(
            self.stock[dma_setup : dma_setup + 6],
            bytes.fromhex("135013411362"),
        )
        self.assertEqual(fmv.MOVIE_FRAMEBUFFER_STRIDE, fmv.MOVIE_WIDTH)
        code = self.runtime.code[: self.runtime.code_used]
        self.assertNotIn(struct.pack(">I", fmv.DECODED_FRAMEBUFFER), code)
        self.assertIn(
            struct.pack(">I", fmv.BLOCKING_DMA_DESTINATION_POINTER), code
        )
        self.assertIn(
            struct.pack(">I", fmv.STREAM_DMA_DESTINATION_POINTER), code
        )
        self.assertIn(struct.pack(">I", fmv.BLOCKING_DISPLAY_ROW_STRIDE), code)
        self.assertIn(struct.pack(">I", fmv.STREAM_DISPLAY_ROW_STRIDE), code)
        self.assertIn(struct.pack(">I", fmv.SHADOW_PIXEL_16), code)

        source = fmv.ASSEMBLY_PATH.read_text(encoding="utf-8")
        blocking = source.split("fmv_present_wrapper:", 1)[1].split(
            "fmv_stream_present_wrapper:", 1
        )[0]
        streaming = source.split("fmv_stream_present_wrapper:", 1)[1].split(
            "fmv_present_active_frame:", 1
        )[0]
        self.assertLess(
            blocking.index("=STOCK_PRESENTER"),
            blocking.index("bsr     fmv_present_active_frame"),
        )
        self.assertLess(
            streaming.index("=STOCK_STREAM_PRESENTER"),
            streaming.index("bsr     fmv_present_active_frame"),
        )
        self.assertIn("=BLOCKING_DMA_DESTINATION_POINTER", blocking)
        self.assertIn("=STREAM_DMA_DESTINATION_POINTER", streaming)

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
            (
                fmv.TERTIARY_DATA_ADDRESS,
                fmv.TERTIARY_DATA_ADDRESS + fmv.TERTIARY_DATA_CAPACITY,
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
