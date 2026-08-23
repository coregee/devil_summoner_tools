"""Build the checked START2 runtime subtitle overlay for PSP BOOT.BIN."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..core.emitter import (
    A0,
    A1,
    A2,
    A3,
    RA,
    S0,
    S1,
    S2,
    S3,
    S4,
    S5,
    SP,
    T0,
    T1,
    T2,
    T9,
    V0,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.patching import Patch, apply_patches


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "fmv_subtitles.json"
FMV_MANIFEST_PATH = (
    ENGINE_ROOT.parent / "fmv" / "generated" / "game" / "psp.fmv.json"
)
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = (
    "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
)
FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS = 0x0013EE10
FMV_SUBTITLE_TABLE_ADDRESS = 0x0013F000
FMV_SUBTITLE_TABLE_LIMIT = 0x0013F800
FMV_SUBTITLE_MOVIE_UPDATE_ADDRESS = 0x0000B8A8
FMV_SUBTITLE_GLYPH_DRAW_ADDRESS = 0x0000C998
FMV_SUBTITLE_START2_NAME_ADDRESS = 0x0010C5B0
FMV_SUBTITLE_FRAME_COUNTER_ADDRESS = 0x004703A0
FMV_SUBTITLE_GLYPH_FIRST = 0x0672
FMV_SUBTITLE_GLYPH_LIMIT = 0x0691
FMV_SUBTITLE_STOCK_CALL_BYTES = bytes.fromhex("2a2e000c")


@dataclass(frozen=True, slots=True)
class MovieCallContract:
    name: str
    address: int
    relocation_offset: int
    delay_slot: bytes


@dataclass(frozen=True, slots=True)
class FmvSubtitleConfig:
    calls: tuple[MovieCallContract, ...]


@dataclass(frozen=True, slots=True)
class FmvSubtitleGlyph:
    x: int
    y: int
    code: int


@dataclass(frozen=True, slots=True)
class FmvSubtitleCue:
    start_frame: int
    end_frame_exclusive: int
    glyphs: tuple[FmvSubtitleGlyph, ...]


@dataclass(frozen=True, slots=True)
class FmvSubtitleRuntime:
    draw_wrapper: AssembledCode
    cue_table: bytes
    writes: tuple[PatchWrite, ...]


@dataclass(frozen=True, slots=True)
class FmvSubtitleBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime_used_size: int
    runtime_capacity: int
    cue_count: int


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be hexadecimal text")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"{context} is not hexadecimal") from error


def load_config(path: Path = CONFIG_PATH) -> FmvSubtitleConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP FMV engine config: {path}") from error
    if (
        not isinstance(document, dict)
        or set(document)
        != {"version", "surface", "target", "runtime", "movie_calls", "stock_call"}
        or document["version"] != 1
        or document["surface"] != "fmv_subtitles.runtime"
        or document["stock_call"] != FMV_SUBTITLE_STOCK_CALL_BYTES.hex()
    ):
        raise ValueError(f"{path}: unsupported PSP FMV engine contract")
    target = document["target"]
    runtime = document["runtime"]
    if (
        target
        != {
            "name": "BOOT.BIN",
            "address_bias": ADDRESS_BIAS,
            "size": BOOT_SIZE,
            "stock_sha256": BOOT_STOCK_SHA256,
        }
        or not isinstance(runtime, dict)
        or set(runtime)
        != {
            "draw_wrapper_address",
            "cue_table_address",
            "cue_table_limit",
            "movie_update_address",
            "glyph_draw_address",
            "start2_name_address",
            "frame_counter_address",
            "glyph_first",
            "glyph_limit",
        }
    ):
        raise ValueError(f"{path}: malformed PSP FMV engine contract")
    actual_runtime = tuple(
        _hex(runtime[name], f"runtime.{name}")
        for name in (
            "draw_wrapper_address",
            "cue_table_address",
            "cue_table_limit",
            "movie_update_address",
            "glyph_draw_address",
            "start2_name_address",
            "frame_counter_address",
            "glyph_first",
            "glyph_limit",
        )
    )
    expected_runtime = (
        FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS,
        FMV_SUBTITLE_TABLE_ADDRESS,
        FMV_SUBTITLE_TABLE_LIMIT,
        FMV_SUBTITLE_MOVIE_UPDATE_ADDRESS,
        FMV_SUBTITLE_GLYPH_DRAW_ADDRESS,
        FMV_SUBTITLE_START2_NAME_ADDRESS,
        FMV_SUBTITLE_FRAME_COUNTER_ADDRESS,
        FMV_SUBTITLE_GLYPH_FIRST,
        FMV_SUBTITLE_GLYPH_LIMIT,
    )
    if actual_runtime != expected_runtime:
        raise ValueError(f"{path}: PSP FMV runtime layout changed")
    rows = document["movie_calls"]
    if not isinstance(rows, list) or len(rows) != 10:
        raise ValueError(f"{path}: PSP FMV movie-call inventory changed")
    calls = []
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"name", "address", "relocation_offset", "delay_slot"}
            or not isinstance(row["name"], str)
            or not row["name"]
        ):
            raise ValueError(f"{path}: invalid PSP FMV movie call {index}")
        try:
            delay_slot = bytes.fromhex(row["delay_slot"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"{path}: invalid PSP FMV delay slot {index}") from error
        if len(delay_slot) != 4:
            raise ValueError(f"{path}: invalid PSP FMV delay slot {index}")
        calls.append(
            MovieCallContract(
                row["name"],
                _hex(row["address"], "FMV call address"),
                _hex(row["relocation_offset"], "FMV relocation offset"),
                delay_slot,
            )
        )
    if len({call.name for call in calls}) != len(calls):
        raise ValueError(f"{path}: duplicate PSP FMV movie call")
    return FmvSubtitleConfig(tuple(calls))


def load_runtime_cues(path: Path = FMV_MANIFEST_PATH) -> tuple[FmvSubtitleCue, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP FMV manifest: {path}") from error
    movie = document.get("movie") if isinstance(document, dict) else None
    runtime = document.get("runtime") if isinstance(document, dict) else None
    rows = runtime.get("cues") if isinstance(runtime, dict) else None
    if (
        not isinstance(document, dict)
        or set(document)
        != {"version", "surface", "components", "inputs", "movie", "runtime"}
        or document.get("version") != 1
        or document.get("surface") != "psp.fmv"
        or document.get("components") != ["start2_news.runtime_overlay"]
        or not isinstance(movie, dict)
        or movie
        != {
            "extent_offset": 257_064_960,
            "path": "PSP_GAME/USRDIR/MOVIE/START2_320x224.pmf",
            "sha256": (
                "6dc543ac681b3fc8def88b23d00415306720454e82438e3f73cf485ed9eccb90"
            ),
            "size": 4_511_744,
            "unchanged": True,
        }
        or not isinstance(runtime, dict)
        or set(runtime)
        != {
            "cue_count",
            "visible_glyph_count",
            "maximum_cue_glyph_count",
            "compiled_sha256",
            "cues",
        }
        or runtime.get("cue_count") != 9
        or runtime.get("visible_glyph_count") != 437
        or runtime.get("maximum_cue_glyph_count") != 61
        or runtime.get("compiled_sha256")
        != "9370e124671cccb3d01279764a72a5cb4a51b4a5af50891f5f56b215068dcffe"
        or not isinstance(rows, list)
        or len(rows) != 9
    ):
        raise ValueError("PSP FMV manifest has no valid START2 runtime contract")
    compiled = json.dumps(
        rows,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if hashlib.sha256(compiled).hexdigest() != runtime["compiled_sha256"]:
        raise ValueError("PSP FMV manifest cue payload violates its digest")
    cues = []
    for cue_index, row in enumerate(rows):
        glyph_rows = row.get("glyphs") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or set(row) != {"start_frame", "end_frame_exclusive", "glyphs"}
            or type(row["start_frame"]) is not int
            or type(row["end_frame_exclusive"]) is not int
            or not isinstance(glyph_rows, list)
        ):
            raise ValueError(f"invalid PSP FMV manifest cue {cue_index}")
        glyphs = []
        for glyph_index, glyph in enumerate(glyph_rows):
            if (
                not isinstance(glyph, dict)
                or set(glyph) != {"x", "y", "code"}
                or any(type(glyph[name]) is not int for name in ("x", "y", "code"))
            ):
                raise ValueError(
                    f"invalid PSP FMV cue {cue_index} glyph {glyph_index}"
                )
            glyphs.append(FmvSubtitleGlyph(glyph["x"], glyph["y"], glyph["code"]))
        cues.append(
            FmvSubtitleCue(
                row["start_frame"],
                row["end_frame_exclusive"],
                tuple(glyphs),
            )
        )
    return tuple(cues)


def _build_draw_wrapper() -> AssembledCode:
    code = _Assembler(FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x00, SP)
    code.sw(S1, 0x04, SP)
    code.sw(S2, 0x08, SP)
    code.sw(S3, 0x0C, SP)
    code.sw(S4, 0x10, SP)
    code.sw(S5, 0x14, SP)
    code.addu(S0, A0, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S1, RA, ZERO)
    _load_pc_relative_target(
        code,
        T9,
        S1,
        pc_address=pc_address,
        target_address=FMV_SUBTITLE_MOVIE_UPDATE_ADDRESS,
    )
    code.addu(A0, S0, ZERO)
    code.jalr(T9)
    code.delay_nop()
    code.addu(S4, V0, ZERO)
    _load_pc_relative_target(
        code,
        T9,
        S1,
        pc_address=pc_address,
        target_address=FMV_SUBTITLE_START2_NAME_ADDRESS,
    )
    code.bne(S0, T9, "return")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T9,
        S1,
        pc_address=pc_address,
        target_address=FMV_SUBTITLE_FRAME_COUNTER_ADDRESS,
    )
    code.lw(S2, 0, T9)
    code.label("normalize_frame_index")
    code.beq(S2, ZERO, "frame_index_ready")
    code.delay_nop()
    code.addiu(S2, S2, -1)
    code.label("frame_index_ready")
    code.addiu(S5, S1, FMV_SUBTITLE_TABLE_ADDRESS - pc_address)
    code.lhu(T2, 0, S5)
    code.addiu(S3, S5, 4)
    code.label("cue_loop")
    code.beq(T2, ZERO, "return")
    code.delay_nop()
    code.lhu(T0, 0, S3)
    code.sltu(T1, S2, T0)
    code.bne(T1, ZERO, "return")
    code.delay_nop()
    code.lhu(T0, 2, S3)
    code.sltu(T1, S2, T0)
    code.bne(T1, ZERO, "cue_found")
    code.delay_nop()
    code.addiu(S3, S3, 8)
    code.addiu(T2, T2, -1)
    code.beq(ZERO, ZERO, "cue_loop")
    code.delay_nop()
    code.label("cue_found")
    code.lhu(T0, 4, S3)
    code.lhu(S2, 6, S3)
    code.addu(S3, S5, T0)
    _load_pc_relative_target(
        code,
        S5,
        S1,
        pc_address=pc_address,
        target_address=FMV_SUBTITLE_GLYPH_DRAW_ADDRESS,
    )
    code.label("glyph_loop")
    code.beq(S2, ZERO, "return")
    code.delay_nop()
    code.lhu(A0, 0, S3)
    code.lbu(A1, 2, S3)
    code.lbu(A3, 3, S3)
    code.addiu(A0, A0, 1)
    code.addiu(A1, A1, 1)
    code.addiu(A2, ZERO, 5)
    code.addiu(A3, A3, 0x600)
    code.lui(T0, 0xFF00)
    code.jalr(S5)
    code.delay_nop()
    code.lhu(A0, 0, S3)
    code.lbu(A1, 2, S3)
    code.lbu(A3, 3, S3)
    code.addiu(A2, ZERO, 5)
    code.addiu(A3, A3, 0x600)
    code.lui(T0, 0xFFFF)
    code.ori(T0, T0, 0xFFFF)
    code.jalr(S5)
    code.delay_nop()
    code.addiu(S3, S3, 4)
    code.addiu(S2, S2, -1)
    code.beq(ZERO, ZERO, "glyph_loop")
    code.delay_nop()
    code.label("return")
    code.addu(V0, S4, ZERO)
    code.lw(S5, 0x14, SP)
    code.lw(S4, 0x10, SP)
    code.lw(S3, 0x0C, SP)
    code.lw(S2, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.lw(S0, 0x00, SP)
    code.lw(RA, 0x1C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_cue_table(cues: Iterable[FmvSubtitleCue]) -> bytes:
    try:
        values = tuple(cues)
    except TypeError as error:
        raise TypeError("PSP FMV subtitle cues must be iterable") from error
    if not values or len(values) > 0xFFFF:
        raise ValueError("PSP FMV subtitle table must contain 1..65535 cues")
    descriptors = bytearray()
    payload = bytearray()
    previous_end = 0
    payload_base = 4 + len(values) * 8
    for cue_index, cue in enumerate(values):
        if (
            not isinstance(cue, FmvSubtitleCue)
            or type(cue.start_frame) is not int
            or type(cue.end_frame_exclusive) is not int
            or not 0 <= cue.start_frame < cue.end_frame_exclusive <= 0xFFFF
            or cue.start_frame < previous_end
            or not cue.glyphs
            or len(cue.glyphs) > 0xFFFF
        ):
            raise ValueError(f"PSP FMV subtitle cue {cue_index} is invalid")
        previous_end = cue.end_frame_exclusive
        payload_offset = payload_base + len(payload)
        if payload_offset > 0xFFFF:
            raise ValueError("PSP FMV subtitle payload offset exceeds 16 bits")
        descriptors.extend(
            struct.pack(
                "<4H",
                cue.start_frame,
                cue.end_frame_exclusive,
                payload_offset,
                len(cue.glyphs),
            )
        )
        for glyph_index, glyph in enumerate(cue.glyphs):
            if (
                not isinstance(glyph, FmvSubtitleGlyph)
                or type(glyph.x) is not int
                or not 0 <= glyph.x <= 0xFFFE
                or type(glyph.y) is not int
                or not 0 <= glyph.y <= 0xFE
                or type(glyph.code) is not int
                or not FMV_SUBTITLE_GLYPH_FIRST
                <= glyph.code
                < FMV_SUBTITLE_GLYPH_LIMIT
            ):
                raise ValueError(
                    f"PSP FMV cue {cue_index} glyph {glyph_index} is invalid"
                )
            payload.extend(struct.pack("<HBB", glyph.x, glyph.y, glyph.code & 0xFF))
    table = struct.pack("<HH", len(values), 0) + bytes(descriptors) + bytes(payload)
    if FMV_SUBTITLE_TABLE_ADDRESS + len(table) > FMV_SUBTITLE_TABLE_LIMIT:
        raise ValueError("PSP FMV subtitle table exceeds its checked cave partition")
    return table


def build_runtime(
    cues: Iterable[FmvSubtitleCue],
    config: FmvSubtitleConfig | None = None,
) -> FmvSubtitleRuntime:
    plan = config or load_config()
    wrapper = _build_draw_wrapper()
    table = _build_cue_table(cues)
    if wrapper.end_address > FMV_SUBTITLE_TABLE_ADDRESS:
        raise ValueError("PSP FMV subtitle wrapper exceeds its cave partition")
    writes = tuple(
        PatchWrite(
            call.name,
            call.address,
            _word_bytes(_jal_word(call.address, FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS)),
        )
        for call in plan.calls
    ) + (
        PatchWrite("fmv_subtitle_draw_wrapper", wrapper.address, wrapper.data),
        PatchWrite("fmv_subtitle_cue_table", FMV_SUBTITLE_TABLE_ADDRESS, table),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP FMV writes overlap: {left.name} and {right.name}")
    return FmvSubtitleRuntime(wrapper, table, writes)


def _validate_source(
    stock: bytes,
    runtime: FmvSubtitleRuntime,
    config: FmvSubtitleConfig,
) -> None:
    if (
        len(stock) != BOOT_SIZE
        or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256
    ):
        raise ValueError("PSP FMV BOOT.BIN source contract changed")
    by_name = {write.name: write for write in runtime.writes}
    for call in config.calls:
        write = by_name[call.name]
        start = call.address + ADDRESS_BIAS
        if stock[start:start + 8] != FMV_SUBTITLE_STOCK_CALL_BYTES + call.delay_slot:
            raise ValueError(f"PSP FMV call or delay slot changed at {call.address:#x}")
        expected_relocation = struct.pack("<II", call.address, 4)
        if stock[
            call.relocation_offset:call.relocation_offset + 8
        ] != expected_relocation:
            raise ValueError(f"PSP FMV relocation changed at {call.address:#x}")
        if stock[start:start + len(write.data)] != FMV_SUBTITLE_STOCK_CALL_BYTES:
            raise ValueError(f"PSP FMV call preimage changed at {call.address:#x}")
    for name in ("fmv_subtitle_draw_wrapper", "fmv_subtitle_cue_table"):
        write = by_name[name]
        start = write.address + ADDRESS_BIAS
        if any(stock[start:start + len(write.data)]):
            raise ValueError(f"PSP FMV code-cave preimage changed at {name}")


def build_fmv_subtitles(stock: bytes, intermediate: bytes) -> FmvSubtitleBuild:
    config = load_config()
    cues = load_runtime_cues()
    runtime = build_runtime(cues, config)
    _validate_source(stock, runtime, config)
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP FMV intermediate BOOT.BIN size changed")
    patches = tuple(
        Patch(
            "fmv_subtitles.runtime",
            write.name,
            write.address,
            stock[
                write.address + ADDRESS_BIAS:
                write.address + ADDRESS_BIAS + len(write.data)
            ],
            write.data,
        )
        for write in runtime.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    return FmvSubtitleBuild(
        output,
        patches,
        len(runtime.draw_wrapper.data) + len(runtime.cue_table),
        FMV_SUBTITLE_TABLE_LIMIT - FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS,
        len(cues),
    )


__all__ = [
    "CONFIG_PATH",
    "FMV_MANIFEST_PATH",
    "FMV_SUBTITLE_DRAW_WRAPPER_ADDRESS",
    "FMV_SUBTITLE_GLYPH_FIRST",
    "FMV_SUBTITLE_GLYPH_LIMIT",
    "FMV_SUBTITLE_TABLE_ADDRESS",
    "FMV_SUBTITLE_TABLE_LIMIT",
    "FmvSubtitleBuild",
    "FmvSubtitleCue",
    "FmvSubtitleGlyph",
    "FmvSubtitleRuntime",
    "build_fmv_subtitles",
    "build_runtime",
    "load_config",
    "load_runtime_cues",
]
