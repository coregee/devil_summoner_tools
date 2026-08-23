"""Build command-menu help rendering and shared retained-EVE handle lifetime."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.emitter import (
    A0, A1, A2, A3, RA, S0, S1, S2, S3, S4, SP, T0, T1, T2, T3, T6,
    T7, T9, V0, V1, ZERO, AssembledCode, PatchWrite, _Assembler, _jal_word,
    _load_pc_relative_target, _word_bytes,
)
from ..core.layout import (
    COMMAND_MENU_HELP_DRAW_WRAPPER_ADDRESS,
    COMMAND_MENU_HELP_DRAW_WRAPPER_END_ADDRESS,
    EVE_ASCII_WIDTH_TABLE_ADDRESS,
    EVE_UI_HANDLE_APPEND_ADDRESS,
    EVE_UI_HANDLE_CAVE_END_ADDRESS,
    EVE_UI_HANDLE_FRAME_WRAPPER_ADDRESS,
    EVE_UI_HANDLE_STATE_ADDRESS,
)
from ..core.patching import Patch, apply_patches


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "command_menu_help.json"
FONT_MANIFEST_PATH = ENGINE_ROOT.parent / "font" / "generated" / "game" / "psp.fonts.json"
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
DRAW_CALL_ADDRESS = 0x0003D6E8
FRAME_CALL_ADDRESS = 0x00000598
STOCK_GLYPH_DRAW_ADDRESS = 0x0000C998
EVENT_GLYPH_DRAW_ADDRESS = 0x0009EEA8
STOCK_FRAME_RESET_ADDRESS = 0x00002B08
STOCK_RELEASE_ADDRESS = 0x0009EFA0
PACKED_RUNTIME_FIRST = 0x1E20
PACKED_WIDTH_COUNT = 95
SPACE_RUNTIME_CODE = 0x1E7E
STOCK_ADVANCE = 16
HANDLE_CAPACITY = 138
HANDLE_STATE_SIZE = 139


@dataclass(frozen=True, slots=True)
class CommandMenuHelpRuntime:
    draw_wrapper: AssembledCode
    frame_wrapper: AssembledCode
    append_helper: AssembledCode
    width_table: bytes
    state: bytes
    writes: tuple[PatchWrite, ...]


@dataclass(frozen=True, slots=True)
class CommandMenuHelpBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime_used_size: int
    runtime_capacity: int


def _load_config() -> dict[str, object]:
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        document.get("version") != 1
        or document.get("surface") != "command_menu_help.runtime"
        or document.get("target")
        != {
            "name": "BOOT.BIN",
            "address_bias": ADDRESS_BIAS,
            "size": BOOT_SIZE,
            "stock_sha256": BOOT_STOCK_SHA256,
        }
        or document.get("runtime")
        != {
            "width_table_address": "0x0013ec20",
            "draw_wrapper_address": "0x0016f700",
            "draw_wrapper_limit": "0x0016f800",
            "frame_wrapper_address": "0x00172014",
            "append_helper_address": "0x001720c0",
            "state_address": "0x00172175",
            "cave_limit": "0x00172200",
        }
    ):
        raise ValueError("invalid PSP command-menu help runtime contract")
    return document


def load_eve_widths() -> bytes:
    document = json.loads(FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
    contract = document.get("eve_ascii") if isinstance(document, dict) else None
    table = contract.get("advance_table") if isinstance(contract, dict) else None
    if (
        document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(table, list)
        or len(table) != PACKED_WIDTH_COUNT
        or any(type(value) is not int or not 1 <= value <= 14 for value in table)
    ):
        raise ValueError("PSP font manifest has no valid EVE advance table")
    return bytes(table)


def _build_draw_wrapper() -> AssembledCode:
    code = _Assembler(COMMAND_MENU_HELP_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc = code.cursor
    code.addiu(V0, A3, -PACKED_RUNTIME_FIRST)
    code.sltiu(V1, V0, PACKED_WIDTH_COUNT)
    code.beq(V1, ZERO, "stock_draw")
    code.delay_nop()
    _load_pc_relative_target(code, T9, RA, pc_address=pc, target_address=EVE_ASCII_WIDTH_TABLE_ADDRESS)
    code.addu(T9, T9, V0)
    code.lbu(T6, 0, T9)
    code.addiu(T7, T6, -STOCK_ADVANCE)
    code.addu(S3, S3, T7)
    code.addiu(T7, ZERO, SPACE_RUNTIME_CODE)
    code.beq(A3, T7, "return")
    code.delay_nop()
    code.addiu(A0, A0, 72)
    code.addiu(A1, A1, 24)
    code.addu(V1, A2, ZERO)
    code.addu(A2, A3, ZERO)
    code.addu(A3, V1, ZERO)
    code.addiu(T1, ZERO, 1)
    code.addu(T2, ZERO, ZERO)
    _load_pc_relative_target(code, T9, RA, pc_address=pc, target_address=EVENT_GLYPH_DRAW_ADDRESS)
    _load_pc_relative_target(code, T7, RA, pc_address=pc, target_address=EVE_UI_HANDLE_APPEND_ADDRESS)
    code.sw(T7, 0x08, SP)
    code.jalr(T9)
    code.delay_nop()
    code.addu(A0, V0, ZERO)
    code.lw(T9, 0x08, SP)
    code.jalr(T9)
    code.delay_nop()
    code.label("return")
    code.lw(RA, 0x0C, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    code.label("stock_draw")
    _load_pc_relative_target(code, T9, RA, pc_address=pc, target_address=STOCK_GLYPH_DRAW_ADDRESS)
    code.lw(RA, 0x0C, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_frame_wrapper() -> AssembledCode:
    code = _Assembler(EVE_UI_HANDLE_FRAME_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    for register, offset in ((RA, 0x1C), (S0, 0x18), (S1, 0x14), (S2, 0x10), (S3, 0x0C), (S4, 0x08)):
        code.sw(register, offset, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc = code.cursor
    _load_pc_relative_target(code, S0, RA, pc_address=pc, target_address=EVE_UI_HANDLE_STATE_ADDRESS)
    _load_pc_relative_target(code, S2, RA, pc_address=pc, target_address=STOCK_RELEASE_ADDRESS)
    _load_pc_relative_target(code, S3, RA, pc_address=pc, target_address=STOCK_FRAME_RESET_ADDRESS)
    code.jalr(S3)
    code.delay_nop()
    code.lbu(S1, 0, S0)
    code.sb(ZERO, 0, S0)
    code.addiu(S4, S0, 1)
    code.label("release_loop")
    code.beq(S1, ZERO, "return")
    code.delay_nop()
    code.lbu(A0, 0, S4)
    code.jalr(S2)
    code.delay_nop()
    code.addiu(S4, S4, 1)
    code.addiu(S1, S1, -1)
    code.beq(ZERO, ZERO, "release_loop")
    code.delay_nop()
    code.label("return")
    for register, offset in ((S4, 0x08), (S3, 0x0C), (S2, 0x10), (S1, 0x14), (S0, 0x18), (RA, 0x1C)):
        code.lw(register, offset, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_append_helper() -> AssembledCode:
    code = _Assembler(EVE_UI_HANDLE_APPEND_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(A0, 0x08, SP)
    code.bltz(A0, "return")
    code.delay_nop()
    code.sltiu(T0, A0, 0xFE)
    code.beq(T0, ZERO, "return")
    code.delay_nop()
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc = code.cursor
    _load_pc_relative_target(code, T0, RA, pc_address=pc, target_address=EVE_UI_HANDLE_STATE_ADDRESS)
    code.lbu(T1, 0, T0)
    code.sltiu(T2, T1, HANDLE_CAPACITY)
    code.beq(T2, ZERO, "release_untracked")
    code.delay_nop()
    code.addiu(T3, T0, 1)
    code.addu(T3, T3, T1)
    code.sb(A0, 0, T3)
    code.addiu(T1, T1, 1)
    code.sb(T1, 0, T0)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()
    code.label("release_untracked")
    _load_pc_relative_target(code, T3, RA, pc_address=pc, target_address=STOCK_RELEASE_ADDRESS)
    code.jalr(T3)
    code.delay_nop()
    code.label("return")
    code.lw(A0, 0x08, SP)
    code.lw(RA, 0x0C, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def build_runtime(widths: bytes) -> CommandMenuHelpRuntime:
    if not isinstance(widths, bytes) or len(widths) != 95 or any(not 1 <= value <= 14 for value in widths):
        raise ValueError("PSP command-help EVE width table is invalid")
    draw = _build_draw_wrapper()
    frame = _build_frame_wrapper()
    append = _build_append_helper()
    state = bytes(HANDLE_STATE_SIZE)
    if draw.end_address > COMMAND_MENU_HELP_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP command-help wrapper exceeds its cave")
    if frame.end_address > EVE_UI_HANDLE_APPEND_ADDRESS or append.end_address > EVE_UI_HANDLE_STATE_ADDRESS:
        raise ValueError("PSP retained-EVE helpers exceed their cave partitions")
    if EVE_UI_HANDLE_STATE_ADDRESS + len(state) != EVE_UI_HANDLE_CAVE_END_ADDRESS:
        raise ValueError("PSP retained-EVE state does not fill its cave tail")
    writes = (
        PatchWrite("eve_ascii_width_table", EVE_ASCII_WIDTH_TABLE_ADDRESS, widths),
        PatchWrite("command_menu_help_draw_call", DRAW_CALL_ADDRESS, _word_bytes(_jal_word(DRAW_CALL_ADDRESS, draw.address))),
        PatchWrite("command_menu_help_draw_wrapper", draw.address, draw.data),
        PatchWrite("eve_ui_handle_frame_call", FRAME_CALL_ADDRESS, _word_bytes(_jal_word(FRAME_CALL_ADDRESS, frame.address))),
        PatchWrite("eve_ui_handle_frame_wrapper", frame.address, frame.data),
        PatchWrite("eve_ui_handle_append_helper", append.address, append.data),
        PatchWrite("eve_ui_handle_state", EVE_UI_HANDLE_STATE_ADDRESS, state),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP command-help writes overlap: {left.name}, {right.name}")
    return CommandMenuHelpRuntime(draw, frame, append, widths, state, writes)


def _validate_source(stock: bytes, runtime: CommandMenuHelpRuntime, plan: dict[str, object]) -> None:
    if len(stock) != BOOT_SIZE or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256:
        raise ValueError("PSP command-help BOOT source contract changed")
    hooks = plan["hooks"]
    for name, write_name in (("draw", "command_menu_help_draw_call"), ("frame", "eve_ui_handle_frame_call")):
        hook = hooks[name]
        address = int(hook["address"], 16)
        source = bytes.fromhex(hook["source"])
        delay = bytes.fromhex(hook["delay_slot"])
        start = address + ADDRESS_BIAS
        if stock[start : start + 8] != source + delay:
            raise ValueError(f"PSP command-help {name} hook preimage changed")
        relocation = struct.pack("<II", address, 4)
        offset = int(hook["relocation_offset"], 16)
        if stock[offset : offset + 8] != relocation:
            raise ValueError(f"PSP command-help {name} relocation changed")
    by_name = {write.name: write for write in runtime.writes}
    for name, write in by_name.items():
        start = write.address + ADDRESS_BIAS
        before = stock[start : start + len(write.data)]
        if name == "command_menu_help_draw_call" and before != bytes.fromhex("6632000c"):
            raise ValueError("PSP command-help draw call source changed")
        elif name == "eve_ui_handle_frame_call" and before != bytes.fromhex("c20a000c"):
            raise ValueError("PSP retained-EVE frame call source changed")
        elif name not in {"command_menu_help_draw_call", "eve_ui_handle_frame_call"} and any(before):
            raise ValueError(f"PSP command-help cave is not blank: {name}")


def build_command_menu_help(stock: bytes, intermediate: bytes) -> CommandMenuHelpBuild:
    plan = _load_config()
    runtime = build_runtime(load_eve_widths())
    _validate_source(stock, runtime, plan)
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP command-help intermediate BOOT size changed")
    patches = tuple(
        Patch(
            "command_menu_help.runtime",
            write.name,
            write.address,
            stock[write.address + ADDRESS_BIAS : write.address + ADDRESS_BIAS + len(write.data)],
            write.data,
        )
        for write in runtime.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = sum(len(write.data) for write in runtime.writes if write.name not in {"command_menu_help_draw_call", "eve_ui_handle_frame_call"})
    capacity = (
        COMMAND_MENU_HELP_DRAW_WRAPPER_END_ADDRESS - COMMAND_MENU_HELP_DRAW_WRAPPER_ADDRESS
        + 0xE0
        + EVE_UI_HANDLE_CAVE_END_ADDRESS - EVE_UI_HANDLE_FRAME_WRAPPER_ADDRESS
    )
    return CommandMenuHelpBuild(output, patches, used, capacity)


__all__ = (
    "CONFIG_PATH", "CommandMenuHelpBuild", "CommandMenuHelpRuntime",
    "build_command_menu_help", "build_runtime", "load_eve_widths",
)
