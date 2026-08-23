"""Shared variable-width runtime for PSP event-window consumers.

The EVENT VWF patch is deliberately narrower than a general text renderer. It owns
one active EVE textbox at a time, keeps one pen shared by that textbox, and
resets the pen when the stock renderer changes owner, row, or returns its byte
cursor to zero. The decoder marks exactly one following draw call as packed;
the draw wrapper consumes that mark only when its textbox owner, byte cursor,
and expected glyph all still match. Inline insertion controls preserve that
pen, while the EVENT capacity hook gives every substitution glyph the same
checked one-shot draw state. Ark glyphs use measured advances and other packed
drawables use Saturn's 16-pixel fallback. A preserved two-byte glyph commits
its extra cursor byte only after the stock renderer accepts the draw, so a
deferred or page-wrapped draw can retry the same logical word safely.
The clear hook drops persistent packed ownership only after releasing the
packed rows, so a following native Japanese page/message returns to stock
17-by-30 handle geometry while the next packed byte can establish ownership
again.
Concurrent/interleaved textboxes require per-owner pen storage and remain
outside this contract.

Packed glyphs are markerless bytes. A byte below ``0x1f``, or exactly ``0x80``,
is the first half of a preserved big-endian logical word. Every other first
byte is a packed glyph and becomes runtime code ``byte + 0x1e01``. In
particular, this hook assigns no special meaning to ``0x012b`` or ``0x012c``.

All addresses are module-relative virtual addresses from the decrypted ELF.
The pinned ELF load segment begins at file offset ``0x80``; consumers may use
``PatchWrite.file_offset`` when applying these writes to that exact container.
The public surface builder composes these writes into the checked executable;
disc publication remains owned by the PSP ROM stage.
"""

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
    S6,
    S7,
    SP,
    T0,
    T1,
    T2,
    T3,
    T4,
    T5,
    T6,
    T7,
    T8,
    T9,
    V0,
    V1,
    ZERO,
    AssembledCode,
    PatchWrite,
    _Assembler,
    _i_type,
    _j_word,
    _jal_word,
    _load_pc_relative_target,
    _r_type,
    _word_bytes,
)
from ..core.layout import (
    DATA_LOAD_SEGMENT_ADDRESS,
    EVENT_CAVE_END_ADDRESS as CAVE_END_ADDRESS,
    EVENT_CAPACITY_HELPER_ADDRESS,
    EVENT_OPTION_RESET_WRAPPER_ADDRESS,
    WIDTH_TABLE_ADDRESS,
)
from psp.font.util.eve_ascii import _validate_widths
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    GLYPH_CODE_BIAS,
    GLYPH_CODE_FIRST,
    STORED_PRINTABLE_FIRST,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_RUNTIME_BIAS = GLYPH_CODE_BIAS
PACKED_RUNTIME_FIRST = GLYPH_CODE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1
from ..core.patching import Patch, apply_patches


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "event_window.json"
ADDRESS_BIAS = 0x80
BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = (
    "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
)

FETCH_SCALE_PATCH_ADDRESS = 0x0007338C

DECODER_CALL_PATCH_ADDRESS = 0x00073394

FETCH_BYTE_PATCH_ADDRESS = 0x00073398

DRAW_CALL_PATCH_ADDRESS = 0x000736AC

EVENT_CAPACITY_PATCH_ADDRESS = 0x00073640

EVENT_CLEAR_PATCH_ADDRESS = 0x00073778

EVENT_OPTION_RESET_CALL_ADDRESS = 0x000760F8

EVENT_OPTION_NAME_DRAW_CALL_ADDRESS = 0x0007623C

EVENT_OPTION_GLYPH_DRAW_CALL_ADDRESS = 0x00076368

EVENT_OPTION_HANDLE_CAP_ADDRESS = 0x000762A4

EVENT_OPTION_HANDLE_STRIDE_ADDRESS = 0x000762EC

DECODER_ADDRESS = 0x0013E9F0

DRAW_WRAPPER_ADDRESS = 0x0013EB00

STATE_ADDRESS = 0x0013EC00

EVENT_CLEAR_HELPER_ADDRESS = 0x0013F900

EVENT_WRAP_HELPER_ADDRESS = 0x0013FA20

EVENT_PACKED_OWNER_ADDRESS = 0x0013FC00

EVENT_DVLNAME_HELPER_ADDRESS = 0x0013FB10

EVENT_OPTION_DRAW_WRAPPER_ADDRESS = 0x00140B98

EVENT_OPTION_STATE_ADDRESS = 0x00140C34

EVENT_OPTION_STATE_SIZE = 0x04

EVENT_DVLNAME_GLYPH_ADDRESS = 0x00073D28

EVENT_DVLNAME_SETUP_CALL_ADDRESS = 0x00073EBC

EVENT_DVLNAME_SETUP_COUNT_ADDRESS = 0x00073ED4

EVENT_DVLNAME_STOCK_RESOLVER_ADDRESS = 0x00074360

EVENT_DVLNAME_CURRENT_ID_RAW_ADDRESS = 0x003F62DC

EVENT_DVLNAME_CURRENT_BANK_BODY_POINTER_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + 0x003F6CF4

EVENT_DVLNAME_BODY_CAPACITY = 0xD000

EVENT_DVLNAME_HEADER_SIZE = 8

EVENT_DVLNAME_HEADER_OFFSET = EVENT_DVLNAME_BODY_CAPACITY - EVENT_DVLNAME_HEADER_SIZE

EVENT_DVLNAME_MAGIC = 0x454C5644

EVENT_DVLNAME_RECORD_COUNT = 319

EVENT_DVLNAME_STOCK_LENGTH = 8

EVENT_DVLNAME_MAX_LENGTH = 16

STATE_OWNER_OFFSET = 0x00

STATE_ARMED_OFFSET = 0x04

STATE_PEN_OFFSET = 0x08

STATE_ROW_OFFSET = 0x0C

STATE_PEN_OWNER_OFFSET = 0x10

STATE_TOKEN_CURSOR_OFFSET = 0x14

STATE_EXPECTED_GLYPH_OFFSET = 0x18

STATE_RAW_PENDING_OFFSET = 0x1C

STATE_SIZE = 0x20

INITIAL_ROW = 0xFFFFFFFF

STOCK_ALLOCATOR_FROM_CALLER_RA = 0x0002B7F4

EVENT_WORD_BYTESWAP_ADDRESS = 0x000791C0

STOCK_EVENT_GLYPH_DRAW_ADDRESS = 0x0009EEA8

STOCK_GLYPH_RELEASE_ADDRESS = 0x0009EFA0

EVENT_PACKED_LINE_CAP = 120

EVENT_PACKED_ROW_CAP = 3

EVENT_DIALOGUE_WIDTH = 300

EVENT_FALLBACK_ADVANCE = 16

EVENT_OPTION_STOCK_ADVANCE = 15

EVENT_OPTION_HANDLE_POOL = 84


@dataclass(frozen=True)
class FirstVwfPatch:
    """All isolated writes needed by the first single-textbox VWF hook."""

    decoder: AssembledCode
    draw_wrapper: AssembledCode
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex patch write: {name}") from error


def _build_decoder() -> AssembledCode:
    code = _Assembler(DECODER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    code.addiu(T9, RA, STATE_ADDRESS - code.cursor)
    code.sw(ZERO, STATE_RAW_PENDING_OFFSET, T9)

    code.sltiu(T0, A0, PACKED_FIRST)
    code.bne(T0, ZERO, "raw_word")
    code.delay_nop()
    code.addiu(T0, ZERO, 0x80)
    code.beq(A0, T0, "raw_word")
    code.delay_nop()

    code.addiu(V0, A0, PACKED_RUNTIME_BIAS)
    code.sw(S0, STATE_OWNER_OFFSET, T9)
    code.addiu(T0, ZERO, 1)
    code.sw(T0, STATE_ARMED_OFFSET, T9)
    code.lw(T0, 0x28, S0)
    code.bne(T0, ZERO, "packed_ready")
    code.delay_nop()
    code.sw(ZERO, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.sw(ZERO, STATE_PEN_OFFSET, T9)
    code.sw(ZERO, STATE_PEN_OWNER_OFFSET, T9)
    code.addiu(T1, ZERO, -1)
    code.sw(T1, STATE_ROW_OFFSET, T9)
    code.label("packed_ready")
    code.sw(T0, STATE_TOKEN_CURSOR_OFFSET, T9)
    code.sw(V0, STATE_EXPECTED_GLYPH_OFFSET, T9)
    code.addu(RA, T8, ZERO)
    code.jr(RA)
    code.delay_nop()

    code.label("raw_word")
    code.lbu(T0, 1, V0)
    code.sll(V1, A0, 8)
    # The byte after a leading two-byte control is an unambiguous packed
    # storage marker for every translated insert-first message.  Capture it
    # before V0 stops being the stream pointer.
    code.lbu(A0, 2, V0)
    code.or_(V0, V1, T0)
    code.lw(A1, 0x28, S0)
    code.sw(A1, STATE_TOKEN_CURSOR_OFFSET, T9)
    code.sw(V0, STATE_EXPECTED_GLYPH_OFFSET, T9)
    code.sw(S0, STATE_OWNER_OFFSET, T9)
    code.sw(ZERO, STATE_ARMED_OFFSET, T9)
    code.bne(A1, ZERO, "raw_bootstrap")
    code.delay_nop()
    code.sw(ZERO, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.sw(ZERO, STATE_PEN_OFFSET, T9)
    code.sw(ZERO, STATE_PEN_OWNER_OFFSET, T9)
    code.addiu(T1, ZERO, -1)
    code.sw(T1, STATE_ROW_OFFSET, T9)
    # A translated continuation page keeps the message cursor nonzero. Its
    # leading insert therefore needs the same checked packed-byte lookahead as
    # an insert at the start of a message after the clear hook drops page
    # ownership. Native pages cannot satisfy this discriminator: their next
    # logical word begins with a raw high byte outside the packed range.
    code.label("raw_bootstrap")
    code.beq(T0, ZERO, "raw_classify")
    code.delay_nop()
    code.addiu(A0, A0, -PACKED_FIRST)
    code.sltiu(A0, A0, PACKED_WIDTH_COUNT)
    code.beq(A0, ZERO, "raw_classify")
    code.delay_nop()
    code.sw(S0, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.label("raw_classify")
    code.ori(T1, ZERO, 0x8000)
    code.sltu(T1, V0, T1)
    code.bne(T1, ZERO, "raw_glyph")
    code.delay_nop()
    code.addiu(A1, A1, 1)
    code.sw(A1, 0x28, S0)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()

    code.label("raw_glyph")
    code.addiu(T1, ZERO, 1)
    code.sw(T1, STATE_RAW_PENDING_OFFSET, T9)

    code.label("return")
    code.addu(RA, T8, ZERO)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_draw_wrapper() -> AssembledCode:
    code = _Assembler(DRAW_WRAPPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    code.addiu(T9, RA, STATE_ADDRESS - code.cursor)

    code.sll(T6, T3, 2)
    code.subu(T5, S0, T6)
    code.lw(T7, STATE_RAW_PENDING_OFFSET, T9)
    code.sw(ZERO, STATE_RAW_PENDING_OFFSET, T9)
    code.srl(V1, T7, 8)
    code.andi(T7, T7, 1)
    code.beq(T7, ZERO, "packed_draw")
    code.delay_nop()
    code.lw(T7, STATE_OWNER_OFFSET, T9)
    code.bne(T5, T7, "tail_allocator")
    code.delay_nop()
    code.lw(T6, 0x28, T5)
    code.lw(T7, STATE_TOKEN_CURSOR_OFFSET, T9)
    code.bne(T6, T7, "tail_allocator")
    code.delay_nop()
    code.addiu(T6, T6, 1)
    code.sw(T6, 0x28, T5)
    code.lw(T7, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.bne(T5, T7, "tail_allocator")
    code.delay_nop()
    code.beq(ZERO, ZERO, "place_glyph")
    code.delay_nop()

    code.label("packed_draw")
    code.lw(T7, STATE_ARMED_OFFSET, T9)
    code.sw(ZERO, STATE_ARMED_OFFSET, T9)
    code.beq(T7, ZERO, "tail_allocator")
    code.delay_nop()

    code.lw(T7, STATE_OWNER_OFFSET, T9)
    code.bne(T5, T7, "tail_allocator")
    code.delay_nop()

    code.lw(T6, 0x28, T5)
    code.lw(T7, STATE_TOKEN_CURSOR_OFFSET, T9)
    code.bne(T6, T7, "tail_allocator")
    code.delay_nop()

    code.lw(T6, STATE_EXPECTED_GLYPH_OFFSET, T9)
    code.bne(A2, T6, "tail_allocator")
    code.delay_nop()

    code.label("place_glyph")
    code.lw(T7, STATE_PEN_OWNER_OFFSET, T9)
    code.bne(T7, T5, "reset_pen")
    code.delay_nop()
    code.lw(T7, STATE_ROW_OFFSET, T9)
    code.beq(T7, T3, "use_pen")
    code.delay_nop()

    code.label("reset_pen")
    code.sw(T5, STATE_PEN_OWNER_OFFSET, T9)
    code.sw(T3, STATE_ROW_OFFSET, T9)
    code.sw(A0, STATE_PEN_OFFSET, T9)
    code.beq(ZERO, ZERO, "advance_pen")
    code.delay_nop()

    code.label("use_pen")
    code.lw(A0, STATE_PEN_OFFSET, T9)

    code.label("advance_pen")
    code.addu(T5, A0, V1)
    code.sw(T5, STATE_PEN_OFFSET, T9)

    code.label("tail_allocator")
    code.lui(T9, STOCK_ALLOCATOR_FROM_CALLER_RA >> 16)
    code.ori(T9, T9, STOCK_ALLOCATOR_FROM_CALLER_RA & 0xFFFF)
    code.addu(T9, T9, T8)
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_event_capacity_helper() -> AssembledCode:
    """Select stock or expanded handle geometry for one EVENT glyph.

    The stock object owns 510 handle slots as 17 rows of 30.  Translated EVENT
    pages use only the Saturn-compatible three visible rows, so their handles
    are instead addressed as three rows of 120.  Raw readers retain the exact
    stock 30-handle geometry.
    """

    code = _Assembler(EVENT_CAPACITY_HELPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    state_pc = code.cursor
    code.addiu(T9, RA, STATE_ADDRESS - state_pc)
    code.lw(V0, STATE_ARMED_OFFSET, T9)
    code.bne(V0, ZERO, "packed")
    code.delay_nop()
    # Only the EVE byte-stream reader leaves textbox+0x98 clear.  Native-u16
    # readers share this allocator but must never inherit a stale packed owner
    # merely because they happen to reuse the same textbox object.
    code.lw(V0, 0x98, T0)
    code.bne(V0, ZERO, "raw_clear")
    code.delay_nop()
    code.lw(V0, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.bne(V0, T0, "raw")
    code.delay_nop()
    code.lw(V0, STATE_RAW_PENDING_OFFSET, T9)
    code.bne(V0, ZERO, "packed")
    code.delay_nop()
    code.lw(V0, 0x28, T0)
    code.sw(V0, STATE_TOKEN_CURSOR_OFFSET, T9)
    code.sw(A2, STATE_EXPECTED_GLYPH_OFFSET, T9)
    code.addiu(V0, ZERO, 1)
    code.sw(V0, STATE_ARMED_OFFSET, T9)

    code.label("packed")
    code.sw(T0, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.bal_address(EVENT_WRAP_HELPER_ADDRESS)
    code.delay_nop()
    code.beq(V0, ZERO, "return")
    code.delay_nop()
    code.sltiu(V0, T3, EVENT_PACKED_ROW_CAP)
    code.beq(V0, ZERO, "return")
    code.delay_nop()
    code.sltiu(V0, T4, EVENT_PACKED_LINE_CAP)
    code.sll(V1, T3, 7)  # row * 128
    code.sll(T9, T3, 3)  # row * 8
    code.subu(V1, V1, T9)  # row * 120
    code.addu(V1, V1, T4)
    code.sll(V1, V1, 2)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()

    code.label("raw")
    code.bne(T3, ZERO, "raw_index")
    code.delay_nop()
    code.bne(T4, ZERO, "raw_index")
    code.delay_nop()
    code.label("raw_clear")
    code.sw(ZERO, EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS, T9)
    code.label("raw_index")
    code.sll(V1, T3, 4)
    code.subu(V1, V1, T3)
    code.sll(V1, V1, 1)
    code.addu(V1, V1, T4)
    code.sll(V1, V1, 2)
    code.sltiu(V0, T4, 30)

    code.label("return")
    code.addiu(A3, ZERO, 6)
    code.addiu(T1, ZERO, 1)
    code.addu(RA, T8, ZERO)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_event_clear_helper() -> AssembledCode:
    """Release one raw row or all expanded rows for the active packed owner."""

    code = _Assembler(EVENT_CLEAR_HELPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.sw(S3, 0x0C, SP)
    code.sw(S7, 0x08, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addiu(S2, RA, EVENT_PACKED_OWNER_ADDRESS - pc_address)
    release_delta = (STOCK_GLYPH_RELEASE_ADDRESS - pc_address) & 0xFFFFFFFF
    code.lui(S3, release_delta >> 16)
    code.ori(S3, S3, release_delta & 0xFFFF)
    code.addu(S3, S3, RA)
    code.lw(T8, 0, S2)
    code.bne(T8, S4, "raw_row")
    code.delay_nop()

    code.addiu(S0, ZERO, 0)
    code.label("packed_row")
    code.sll(T0, S0, 2)
    code.addu(T0, T0, S4)
    code.lw(S1, 0x38, T0)
    code.sll(V0, S0, 4)
    code.subu(V0, V0, S0)
    code.sll(V0, V0, 5)  # row * 480 bytes
    code.addu(S7, V0, S4)
    code.addiu(S7, S7, 0xA4)
    code.beq(S1, ZERO, "packed_row_done")
    code.delay_nop()
    code.label("packed_release")
    code.lw(A0, 0, S7)
    code.jalr(S3)
    code.delay_nop()
    code.addiu(S7, S7, 4)
    code.addiu(S1, S1, -1)
    code.bne(S1, ZERO, "packed_release")
    code.delay_nop()
    code.label("packed_row_done")
    code.sll(T0, S0, 2)
    code.addu(T0, T0, S4)
    code.sw(ZERO, 0x38, T0)
    code.lw(V1, 0x20, S4)
    code.addiu(S0, S0, 1)
    code.sltu(V0, V1, S0)
    code.beq(V0, ZERO, "packed_row")
    code.delay_nop()
    code.beq(ZERO, ZERO, "done")
    code.delay_nop()

    code.label("raw_row")
    # Stock 0x7376c loaded this raw row's nonzero handle count into V0 before
    # the dispatch at 0x73778.  Preserve that exact outer-loop contract.
    code.addu(S1, V0, ZERO)
    code.sll(S0, S6, 4)
    code.subu(S0, S0, S6)
    code.sll(S0, S0, 3)  # row * 120 bytes
    code.addu(S7, S0, S4)
    code.addiu(S7, S7, 0xA4)
    code.label("raw_release")
    code.lw(A0, 0, S7)
    code.jalr(S3)
    code.delay_nop()
    code.addiu(S7, S7, 4)
    code.addiu(S1, S1, -1)
    code.bne(S1, ZERO, "raw_release")
    code.delay_nop()
    code.lw(V1, 0x20, S4)

    code.label("done")
    # Release geometry must be selected with the old owner above.  Once that
    # work is complete, do not let the next native page/message inherit the
    # packed three-by-120 layout merely because it reuses the same textbox.
    code.sw(ZERO, 0, S2)
    code.sw(
        ZERO,
        STATE_PEN_OWNER_OFFSET - (EVENT_PACKED_OWNER_ADDRESS - STATE_ADDRESS),
        S2,
    )
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.lw(S3, 0x0C, SP)
    code.lw(S7, 0x08, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_event_wrap_helper() -> AssembledCode:
    """Apply Saturn's pre-blit pixel overflow rule to one packed glyph.

    ``T0`` is the live textbox, ``T3``/``T4`` are its row and column, and
    ``S0`` points at that row's count field.  A successful in-page wrap updates
    those exact continuation registers before the stock coordinate and handle
    math runs.  A bottom-row overflow raises the slot-appropriate PSP wait and
    clear state and rejects the draw, leaving both script and insertion cursors
    untouched so the same glyph is retried after the clear.

    The encoded width stored in ``STATE_RAW_PENDING`` uses bit zero for the
    existing raw-word cursor commit and bits 8-15 for the draw advance.  This
    lets the draw wrapper keep one continuous pen across Ark glyphs and the
    Saturn-compatible 16-pixel fallback without borrowing a stock allocator
    register.
    """

    code = _Assembler(EVENT_WRAP_HELPER_ADDRESS)

    code.lw(V0, STATE_PEN_OWNER_OFFSET, T9)
    code.bne(V0, T0, "stock_start")
    code.delay_nop()
    code.lw(V0, STATE_ROW_OFFSET, T9)
    code.bne(V0, T3, "stock_start")
    code.delay_nop()
    code.lw(T5, STATE_PEN_OFFSET, T9)
    code.beq(ZERO, ZERO, "start_ready")
    code.delay_nop()

    code.label("stock_start")
    code.lw(T5, 0x08, T0)
    code.lw(V0, 0x10, T0)
    code.mult(T4, V0)
    code.mflo(V1)
    code.addu(T5, T5, V1)

    code.label("start_ready")
    code.addiu(T6, A2, -PACKED_RUNTIME_FIRST)
    code.sltiu(V0, T6, PACKED_WIDTH_COUNT)
    code.beq(V0, ZERO, "fallback_width")
    code.delay_nop()
    code.addu(V0, T9, T6)
    code.lbu(T6, WIDTH_TABLE_ADDRESS - STATE_ADDRESS, V0)
    code.beq(ZERO, ZERO, "width_ready")
    code.delay_nop()

    code.label("fallback_width")
    code.addiu(T6, ZERO, EVENT_FALLBACK_ADVANCE)

    code.label("width_ready")
    code.addu(A0, T5, T6)
    code.sll(V0, T6, 8)
    code.lw(T7, STATE_RAW_PENDING_OFFSET, T9)
    code.andi(T7, T7, 1)
    code.or_(V0, V0, T7)
    code.sw(V0, STATE_RAW_PENDING_OFFSET, T9)
    code.lw(A1, 0x08, T0)
    code.addiu(A1, A1, EVENT_DIALOGUE_WIDTH)
    code.sltu(V0, A1, A0)
    code.beq(V0, ZERO, "accepted")
    code.delay_nop()

    code.addiu(V0, T3, 1)
    code.sltiu(V1, V0, EVENT_PACKED_ROW_CAP)
    code.beq(V1, ZERO, "page_overflow")
    code.delay_nop()
    code.addu(T3, V0, ZERO)
    code.sw(T3, 0x20, T0)
    code.sll(V0, T3, 2)
    code.addu(S0, T0, V0)
    code.lw(T4, 0x38, S0)
    code.sw(ZERO, STATE_PEN_OWNER_OFFSET, T9)

    code.label("accepted")
    code.addiu(V0, ZERO, 1)
    code.jr(RA)
    code.delay_nop()

    code.label("page_overflow")
    code.beq(S3, ZERO, "alternate_slot")
    code.delay_nop()
    code.ori(V0, ZERO, 0x8005)
    code.beq(ZERO, ZERO, "reject")
    code.delay_nop()

    code.label("alternate_slot")
    code.ori(V0, ZERO, 0x8002)

    code.label("reject")
    code.sw(V0, 0x2C, T0)
    code.addu(V0, ZERO, ZERO)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_event_option_draw_wrapper() -> AssembledCode:
    """Apply Ark advances only after an option's first real Ark glyph.

    Reset stores the negated stock base x.  That negative sentinel survives an
    empty name insertion, unlike the renderer's handle index.  The first real
    Ark glyph negates it back into the initial pen; a native first glyph stores
    zero and leaves the whole option on the stock fixed-width path.  Positive
    state is the next VWF pen, including across non-Ark name-insert glyphs.
    """

    code = _Assembler(EVENT_OPTION_DRAW_WRAPPER_ADDRESS)
    code.addu(T7, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)
    code.addu(RA, T7, ZERO)
    code.addiu(T3, A2, -PACKED_RUNTIME_FIRST)
    code.sltiu(T4, T3, PACKED_WIDTH_COUNT)
    _load_pc_relative_target(
        code,
        T5,
        T8,
        pc_address=pc_address,
        target_address=EVENT_OPTION_STATE_ADDRESS,
    )
    code.lw(V1, 0, T5)
    code.bltz(V1, "first_glyph")
    code.delay_nop()
    code.beq(V1, ZERO, "tail_draw")
    code.delay_nop()
    code.addu(A0, V1, ZERO)
    code.beq(ZERO, ZERO, "width")
    code.delay_nop()

    code.label("first_glyph")
    code.beq(T4, ZERO, "disable")
    code.delay_nop()
    code.subu(A0, ZERO, V1)

    code.label("width")
    code.addiu(T6, ZERO, EVENT_OPTION_STOCK_ADVANCE)
    code.beq(T4, ZERO, "have_width")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=WIDTH_TABLE_ADDRESS,
    )
    code.addu(T9, T9, T3)
    code.lbu(T6, 0, T9)

    code.label("have_width")
    code.addu(V1, A0, T6)
    code.sw(V1, 0, T5)
    code.beq(ZERO, ZERO, "tail_draw")
    code.delay_nop()

    code.label("disable")
    code.sw(ZERO, 0, T5)

    code.label("tail_draw")
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=STOCK_EVENT_GLYPH_DRAW_ADDRESS,
    )
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_event_option_reset_wrapper() -> AssembledCode:
    """Seed the option pen, then tail-call the displaced u16 byteswap."""

    code = _Assembler(EVENT_OPTION_RESET_WRAPPER_ADDRESS)
    return_address = EVENT_OPTION_RESET_CALL_ADDRESS + 8
    _load_pc_relative_target(
        code,
        T8,
        RA,
        pc_address=return_address,
        target_address=EVENT_OPTION_STATE_ADDRESS,
    )
    code.lw(T3, 0x60, SP)
    code.lhu(T4, 0x20, T3)
    code.subu(T4, ZERO, T4)
    code.sw(T4, 0, T8)
    code.addiu(T9, RA, EVENT_WORD_BYTESWAP_ADDRESS - return_address)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _event_option_handle_cap() -> bytes:
    """Let one label use the checked shared pool instead of a fixed 21 slots."""

    return _word_bytes(_i_type(0x0A, S6, V0, EVENT_OPTION_HANDLE_POOL))


def _event_option_handle_stride() -> bytes:
    """Advance the next label by the handles actually used by this label."""

    return _word_bytes(_r_type(A2, S6, A2, 0, 0x21))


def _build_event_dvlname_helper() -> AssembledCode:
    """Resolve one full English DVLNAME row from the active EVENT bank.

    Rebuilt standard banks carry a checked table at a fixed body-tail header.
    Other banks fall back to the stock eight-byte DVLNAME resolver so this
    hook does not broaden translation ownership into untouched script banks.
    """

    code = _Assembler(EVENT_DVLNAME_HELPER_ADDRESS)
    code.label("resolve")
    code.addu(T7, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)
    code.addu(RA, T7, ZERO)
    _load_pc_relative_target(
        code,
        T0,
        T8,
        pc_address=pc_address,
        target_address=EVENT_DVLNAME_CURRENT_BANK_BODY_POINTER_ADDRESS,
    )
    code.lw(T0, 0, T0)
    code.ori(T1, ZERO, EVENT_DVLNAME_HEADER_OFFSET)
    code.addu(T1, T0, T1)
    code.lw(T2, 0, T1)
    code.lui(T3, EVENT_DVLNAME_MAGIC >> 16)
    code.ori(T3, T3, EVENT_DVLNAME_MAGIC & 0xFFFF)
    code.bne(T2, T3, "fallback")
    code.delay_nop()
    code.beq(A0, ZERO, "fallback")
    code.delay_nop()
    code.sltiu(T4, A0, EVENT_DVLNAME_RECORD_COUNT + 1)
    code.beq(T4, ZERO, "fallback")
    code.delay_nop()
    code.lw(T2, 4, T1)
    code.addu(T2, T0, T2)
    code.addiu(T3, A0, -1)
    code.sll(T3, T3, 1)
    code.addu(T3, T2, T3)
    code.lhu(V0, 0, T3)
    code.addu(V0, T2, V0)
    code.addiu(V1, ZERO, EVENT_DVLNAME_MAX_LENGTH - EVENT_DVLNAME_STOCK_LENGTH)
    code.jr(RA)
    code.delay_nop()

    code.label("fallback")
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=EVENT_DVLNAME_STOCK_RESOLVER_ADDRESS,
    )
    code.jalr(T9)
    code.delay_nop()
    code.addu(V1, ZERO, ZERO)
    code.jr(T7)
    code.delay_nop()

    code.label("glyph")
    code.addu(T6, RA, ZERO)
    code.bal("resolve")
    code.delay_nop()
    code.addu(RA, T6, ZERO)
    code.lw(A1, 0x8C, S0)
    code.addu(V0, V0, A1)
    code.lbu(V0, 0, V0)
    code.beq(V1, ZERO, "glyph_return")
    code.delay_nop()
    code.addiu(V0, V0, PACKED_RUNTIME_BIAS)
    code.label("glyph_return")
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _event_capacity_dispatch() -> bytes:
    call_pc = EVENT_CAPACITY_PATCH_ADDRESS + 8
    delta = (EVENT_CAPACITY_HELPER_ADDRESS - call_pc) & 0xFFFFFFFF
    branch_site = EVENT_CAPACITY_PATCH_ADDRESS + 7 * 4
    branch_words = (0x00073684 - (branch_site + 4)) // 4
    return _word_bytes(
        _i_type(0x01, ZERO, 0x11, 1),
        0,
        _i_type(0x0F, ZERO, T9, delta >> 16),
        _i_type(0x0D, T9, T9, delta & 0xFFFF),
        _r_type(RA, T9, T9, 0, 0x21),
        _r_type(T9, ZERO, RA, 0, 0x09),
        0,
        _i_type(0x05, V0, ZERO, branch_words),
        _r_type(V1, T0, S1, 0, 0x21),
        0,
    )


def _event_clear_dispatch() -> bytes:
    call_pc = EVENT_CLEAR_PATCH_ADDRESS + 8
    delta = (EVENT_CLEAR_HELPER_ADDRESS - call_pc) & 0xFFFFFFFF
    branch_site = EVENT_CLEAR_PATCH_ADDRESS + 7 * 4
    branch_words = (0x000737AC - (branch_site + 4)) // 4
    return _word_bytes(
        _i_type(0x01, ZERO, 0x11, 1),
        0,
        _i_type(0x0F, ZERO, T9, delta >> 16),
        _i_type(0x0D, T9, T9, delta & 0xFFFF),
        _r_type(RA, T9, T9, 0, 0x21),
        _r_type(T9, ZERO, RA, 0, 0x09),
        0,
        _i_type(0x04, ZERO, ZERO, branch_words),
        0,
        0,
        0,
        0,
        0,
    )


def build_first_vwf_patch(widths: Iterable[int]) -> FirstVwfPatch:
    """Assemble the pinned first-VWF hook with an explicit advance table.

    ``widths`` must contain 95 positive byte advances ordered by packed storage
    code ``0x1f..0x7d``.  This ordering is deliberately independent of ASCII
    code-point order because the source codec assigns punctuation and space to
    the high end of the packed range.
    """

    width_table = _validate_widths(widths)
    decoder = _build_decoder()
    draw_wrapper = _build_draw_wrapper()
    capacity_helper = _build_event_capacity_helper()
    clear_helper = _build_event_clear_helper()
    wrap_helper = _build_event_wrap_helper()
    option_reset_wrapper = _build_event_option_reset_wrapper()
    option_draw_wrapper = _build_event_option_draw_wrapper()
    dvlname_helper = _build_event_dvlname_helper()

    if decoder.end_address > DRAW_WRAPPER_ADDRESS:
        raise ValueError("PSP packed decoder exceeds its pinned cave partition")
    if draw_wrapper.end_address > STATE_ADDRESS:
        raise ValueError("PSP VWF draw wrapper exceeds its pinned cave partition")
    if WIDTH_TABLE_ADDRESS + len(width_table) > CAVE_END_ADDRESS:
        raise ValueError("PSP VWF width table exceeds the checked code cave")
    if capacity_helper.end_address > EVENT_CLEAR_HELPER_ADDRESS:
        raise ValueError("PSP EVENT capacity helper exceeds its cave partition")
    if clear_helper.end_address > EVENT_WRAP_HELPER_ADDRESS:
        raise ValueError("PSP EVENT clear helper exceeds its cave partition")
    if wrap_helper.end_address > EVENT_DVLNAME_HELPER_ADDRESS:
        raise ValueError("PSP EVENT wrap helper exceeds its cave partition")
    if dvlname_helper.end_address > EVENT_PACKED_OWNER_ADDRESS:
        raise ValueError("PSP EVENT DVLNAME helper exceeds its cave partition")
    if option_reset_wrapper.end_address > EVENT_OPTION_DRAW_WRAPPER_ADDRESS:
        raise ValueError("PSP EVENT option reset exceeds its cave partition")
    if option_draw_wrapper.end_address > EVENT_OPTION_STATE_ADDRESS:
        raise ValueError("PSP EVENT option draw exceeds its cave partition")
    if EVENT_OPTION_STATE_ADDRESS + EVENT_OPTION_STATE_SIZE != CAVE_END_ADDRESS:
        raise ValueError("PSP EVENT option state must end at the checked cave boundary")

    state = struct.pack(
        "<8I",
        0,
        0,
        0,
        INITIAL_ROW,
        0,
        0,
        0,
        0,
    )
    writes = (
        PatchWrite(
            "fetch_byte_cursor",
            FETCH_SCALE_PATCH_ADDRESS,
            _word_bytes(0),
        ),
        PatchWrite(
            "packed_decoder_call",
            DECODER_CALL_PATCH_ADDRESS,
            _word_bytes(
                _jal_word(DECODER_CALL_PATCH_ADDRESS, DECODER_ADDRESS),
                _i_type(0x24, V0, A0, 0),
            ),
        ),
        PatchWrite(
            "vwf_draw_call",
            DRAW_CALL_PATCH_ADDRESS,
            _word_bytes(_jal_word(DRAW_CALL_PATCH_ADDRESS, DRAW_WRAPPER_ADDRESS)),
        ),
        PatchWrite(
            "event_capacity_dispatch",
            EVENT_CAPACITY_PATCH_ADDRESS,
            _event_capacity_dispatch(),
        ),
        PatchWrite(
            "event_clear_dispatch",
            EVENT_CLEAR_PATCH_ADDRESS,
            _event_clear_dispatch(),
        ),
        PatchWrite(
            "event_option_reset_call",
            EVENT_OPTION_RESET_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    EVENT_OPTION_RESET_CALL_ADDRESS,
                    EVENT_OPTION_RESET_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "event_option_name_draw_call",
            EVENT_OPTION_NAME_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    EVENT_OPTION_NAME_DRAW_CALL_ADDRESS,
                    EVENT_OPTION_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "event_option_glyph_draw_call",
            EVENT_OPTION_GLYPH_DRAW_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    EVENT_OPTION_GLYPH_DRAW_CALL_ADDRESS,
                    EVENT_OPTION_DRAW_WRAPPER_ADDRESS,
                )
            ),
        ),
        PatchWrite(
            "event_option_handle_cap",
            EVENT_OPTION_HANDLE_CAP_ADDRESS,
            _event_option_handle_cap(),
        ),
        PatchWrite(
            "event_option_handle_stride",
            EVENT_OPTION_HANDLE_STRIDE_ADDRESS,
            _event_option_handle_stride(),
        ),
        PatchWrite(
            "event_dvlname_glyph",
            EVENT_DVLNAME_GLYPH_ADDRESS,
            _word_bytes(
                _i_type(0x0F, ZERO, V0, 0x003F),
                _jal_word(
                    EVENT_DVLNAME_GLYPH_ADDRESS + 4,
                    dvlname_helper.label_address("glyph"),
                ),
                _i_type(0x25, V0, A0, EVENT_DVLNAME_CURRENT_ID_RAW_ADDRESS & 0xFFFF),
                _r_type(V0, ZERO, A1, 0, 0x21),
                _i_type(0x09, ZERO, A2, 1),
                0,
                _j_word(EVENT_DVLNAME_GLYPH_ADDRESS + 0x18, 0x00073C90),
                0,
            ),
        ),
        PatchWrite(
            "event_dvlname_setup_call",
            EVENT_DVLNAME_SETUP_CALL_ADDRESS,
            _word_bytes(
                _jal_word(
                    EVENT_DVLNAME_SETUP_CALL_ADDRESS,
                    dvlname_helper.label_address("resolve"),
                )
            ),
        ),
        PatchWrite(
            "event_dvlname_setup_count",
            EVENT_DVLNAME_SETUP_COUNT_ADDRESS,
            _word_bytes(_i_type(0x09, V1, A3, EVENT_DVLNAME_STOCK_LENGTH)),
        ),
        PatchWrite("packed_decoder", decoder.address, decoder.data),
        PatchWrite("vwf_draw_wrapper", draw_wrapper.address, draw_wrapper.data),
        PatchWrite("vwf_state", STATE_ADDRESS, state),
        PatchWrite("vwf_widths", WIDTH_TABLE_ADDRESS, width_table),
        PatchWrite(
            "event_capacity_helper",
            capacity_helper.address,
            capacity_helper.data,
        ),
        PatchWrite(
            "event_clear_helper",
            clear_helper.address,
            clear_helper.data,
        ),
        PatchWrite(
            "event_wrap_helper",
            wrap_helper.address,
            wrap_helper.data,
        ),
        PatchWrite(
            "event_dvlname_helper",
            dvlname_helper.address,
            dvlname_helper.data,
        ),
        PatchWrite("event_packed_owner", EVENT_PACKED_OWNER_ADDRESS, bytes(4)),
        PatchWrite(
            "event_option_reset_wrapper",
            option_reset_wrapper.address,
            option_reset_wrapper.data,
        ),
        PatchWrite(
            "event_option_draw_wrapper",
            option_draw_wrapper.address,
            option_draw_wrapper.data,
        ),
        PatchWrite(
            "event_option_state",
            EVENT_OPTION_STATE_ADDRESS,
            bytes(EVENT_OPTION_STATE_SIZE),
        ),
    )
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(
                f"PSP Allegrex writes overlap: {left.name} and {right.name}"
            )
    return FirstVwfPatch(decoder, draw_wrapper, writes)


# Exact retail preimages for the non-cave writes. The generated width table is
# installed once by the neutral EVE consumer already composed ahead of this
# foundation, so it is deliberately omitted from this surface's patch list.
HOOK_SOURCE_BYTES = {
    "fetch_byte_cursor": bytes.fromhex("40 10 02 00"),
    "packed_decoder_call": bytes.fromhex("70 e4 01 0c 00 00 44 94"),
    "vwf_draw_call": bytes.fromhex("aa 7b 02 0c"),
    "event_capacity_dispatch": bytes.fromhex(
        "00 19 0b 00 23 18 6b 00 40 18 03 00 21 18 6c 00 "
        "80 18 03 00 1e 00 82 2d 06 00 07 24 01 00 09 24 "
        "08 00 40 14 21 88 68 00"
    ),
    "event_clear_dispatch": bytes.fromhex(
        "c0 10 17 00 21 10 54 00 a4 00 50 24 21 90 a0 02 "
        "00 00 04 8e 01 00 31 26 e8 7b 02 0c 04 00 10 26 "
        "38 00 42 8e 2b 10 22 02 fa ff 40 54 00 00 04 8e "
        "20 00 83 8e"
    ),
    "event_option_reset_call": bytes.fromhex("70 e4 01 0c"),
    "event_option_name_draw_call": bytes.fromhex("aa 7b 02 0c"),
    "event_option_glyph_draw_call": bytes.fromhex("aa 7b 02 0c"),
    "event_option_handle_cap": bytes.fromhex("15 00 c2 2a"),
    "event_option_handle_stride": bytes.fromhex("15 00 c6 24"),
    "event_dvlname_glyph": bytes.fromhex(
        "3f 00 02 3c d8 d0 01 0c dc 62 44 94 8c 00 03 8e "
        "01 00 06 24 21 10 43 00 24 cf 01 08 00 00 45 90"
    ),
    "event_dvlname_setup_call": bytes.fromhex("d8 d0 01 0c"),
    "event_dvlname_setup_count": bytes.fromhex("08 00 07 24"),
}

CAVE_WRITE_NAMES = frozenset(
    {
        "packed_decoder",
        "vwf_draw_wrapper",
        "vwf_state",
        "event_capacity_helper",
        "event_clear_helper",
        "event_wrap_helper",
        "event_dvlname_helper",
        "event_packed_owner",
        "event_option_reset_wrapper",
        "event_option_draw_wrapper",
        "event_option_state",
    }
)

RELOCATION_CONTRACTS = (
    (0x00212720, 0x00073394),
    (0x002127D8, 0x000736AC),
    (0x002129F0, 0x00073D2C),
    (0x00212A08, 0x00073D40),
    (0x00212B10, 0x00073EBC),
    (0x00213E20, EVENT_OPTION_RESET_CALL_ADDRESS),
    (0x00213E80, EVENT_OPTION_NAME_DRAW_CALL_ADDRESS),
    (0x00213ED8, EVENT_OPTION_GLYPH_DRAW_CALL_ADDRESS),
)

OPTION_CALL_SEQUENCES = (
    (
        EVENT_OPTION_RESET_CALL_ADDRESS,
        bytes.fromhex("70 e4 01 0c 48 00 a2 af"),
    ),
    (
        EVENT_OPTION_NAME_DRAW_CALL_ADDRESS,
        bytes.fromhex("aa 7b 02 0c 21 50 00 00"),
    ),
    (
        EVENT_OPTION_GLYPH_DRAW_CALL_ADDRESS,
        bytes.fromhex("aa 7b 02 0c 21 20 82 00"),
    ),
)


@dataclass(frozen=True, slots=True)
class EventWindowBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime_used_size: int
    runtime_capacity: int


def _load_surface_config() -> dict[str, object]:
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        document.get("version") != 1
        or document.get("surface") != "event_window.runtime_foundation"
        or document.get("target")
        != {
            "name": "BOOT.BIN",
            "address_bias": ADDRESS_BIAS,
            "size": BOOT_SIZE,
            "stock_sha256": BOOT_STOCK_SHA256,
        }
        or document.get("shared_inputs")
        != {
            "eve_ascii_width_count": PACKED_WIDTH_COUNT,
            "eve_ascii_width_address": "0x0013ec20",
            "owner": "command_menu_help.runtime",
        }
        or document.get("write_count") != 24
    ):
        raise ValueError("invalid PSP event-window runtime contract")
    return document


def _validate_surface_source(stock: bytes, runtime: FirstVwfPatch) -> None:
    if (
        not isinstance(stock, bytes)
        or len(stock) != BOOT_SIZE
        or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256
    ):
        raise ValueError("PSP event-window BOOT source contract changed")
    for offset, address in RELOCATION_CONTRACTS:
        expected = struct.pack("<II", address, 4)
        if stock[offset : offset + 8] != expected:
            raise ValueError(f"PSP event-window relocation changed at {address:#x}")
    for address, expected in OPTION_CALL_SEQUENCES:
        start = address + ADDRESS_BIAS
        if stock[start : start + len(expected)] != expected:
            raise ValueError(f"PSP event option call sequence changed at {address:#x}")
    expected_names = frozenset(HOOK_SOURCE_BYTES) | CAVE_WRITE_NAMES | {"vwf_widths"}
    if frozenset(write.name for write in runtime.writes) != expected_names:
        raise ValueError("PSP event-window generated write inventory changed")
    for write in runtime.writes:
        start = write.address + ADDRESS_BIAS
        before = stock[start : start + len(write.data)]
        if write.name in HOOK_SOURCE_BYTES:
            if before != HOOK_SOURCE_BYTES[write.name]:
                raise ValueError(f"PSP event hook source changed: {write.name}")
        elif write.name == "vwf_widths":
            if any(before):
                raise ValueError("PSP shared EVE width-table source is not blank")
        elif write.name in CAVE_WRITE_NAMES:
            if any(before):
                raise ValueError(f"PSP event cave source changed: {write.name}")
        else:
            raise ValueError(f"unknown PSP event-window write: {write.name}")


def build_event_window(
    stock: bytes,
    intermediate: bytes,
    widths: Iterable[int],
) -> EventWindowBuild:
    """Compose the stock-safe EVENT VWF foundation after the shared EVE table."""

    _load_surface_config()
    width_table = _validate_widths(widths)
    runtime = build_first_vwf_patch(width_table)
    _validate_surface_source(stock, runtime)
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP event-window intermediate BOOT size changed")
    width_start = WIDTH_TABLE_ADDRESS + ADDRESS_BIAS
    if intermediate[width_start : width_start + len(width_table)] != width_table:
        raise ValueError("PSP event-window shared EVE width table is not installed")
    writes = tuple(write for write in runtime.writes if write.name != "vwf_widths")
    if len(writes) != 24:
        raise ValueError("PSP event-window composed write inventory changed")
    patches = tuple(
        Patch(
            "event_window.runtime_foundation",
            write.name,
            write.address,
            stock[
                write.address + ADDRESS_BIAS :
                write.address + ADDRESS_BIAS + len(write.data)
            ],
            write.data,
        )
        for write in writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    used = sum(
        len(write.data)
        for write in writes
        if write.name in CAVE_WRITE_NAMES
    )
    capacity = (
        DRAW_WRAPPER_ADDRESS - DECODER_ADDRESS
        + STATE_ADDRESS - DRAW_WRAPPER_ADDRESS
        + WIDTH_TABLE_ADDRESS - STATE_ADDRESS
        + EVENT_CLEAR_HELPER_ADDRESS - EVENT_CAPACITY_HELPER_ADDRESS
        + EVENT_WRAP_HELPER_ADDRESS - EVENT_CLEAR_HELPER_ADDRESS
        + EVENT_DVLNAME_HELPER_ADDRESS - EVENT_WRAP_HELPER_ADDRESS
        + EVENT_PACKED_OWNER_ADDRESS - EVENT_DVLNAME_HELPER_ADDRESS
        + 4
        + EVENT_OPTION_DRAW_WRAPPER_ADDRESS - EVENT_OPTION_RESET_WRAPPER_ADDRESS
        + EVENT_OPTION_STATE_ADDRESS - EVENT_OPTION_DRAW_WRAPPER_ADDRESS
        + EVENT_OPTION_STATE_SIZE
    )
    return EventWindowBuild(output, patches, used, capacity)


__all__ = [
    "DECODER_ADDRESS",
    "DECODER_CALL_PATCH_ADDRESS",
    "DRAW_CALL_PATCH_ADDRESS",
    "DRAW_WRAPPER_ADDRESS",
    "EVENT_CAPACITY_PATCH_ADDRESS",
    "EVENT_CLEAR_HELPER_ADDRESS",
    "EVENT_CLEAR_PATCH_ADDRESS",
    "EVENT_DIALOGUE_WIDTH",
    "EVENT_FALLBACK_ADVANCE",
    "EVENT_PACKED_LINE_CAP",
    "EVENT_PACKED_OWNER_ADDRESS",
    "EVENT_PACKED_ROW_CAP",
    "EVENT_WRAP_HELPER_ADDRESS",
    "FETCH_BYTE_PATCH_ADDRESS",
    "FETCH_SCALE_PATCH_ADDRESS",
    "INITIAL_ROW",
    "STATE_ADDRESS",
    "STATE_ARMED_OFFSET",
    "STATE_EXPECTED_GLYPH_OFFSET",
    "STATE_OWNER_OFFSET",
    "STATE_PEN_OFFSET",
    "STATE_PEN_OWNER_OFFSET",
    "STATE_RAW_PENDING_OFFSET",
    "STATE_ROW_OFFSET",
    "STATE_SIZE",
    "STATE_TOKEN_CURSOR_OFFSET",
    "STOCK_ALLOCATOR_FROM_CALLER_RA",
    "FirstVwfPatch",
    "EventWindowBuild",
    "CONFIG_PATH",
    "build_event_window",
    "build_first_vwf_patch",
]
