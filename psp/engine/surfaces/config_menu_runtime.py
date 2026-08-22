"""Allegrex emitter for the PSP configuration-menu surface."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

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
    S6,
    S7,
    SP,
    T0,
    T1,
    T2,
    T3,
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
    _jal_word,
    _load_pc_relative_target,
    _word_bytes,
)
from ..core.layout import (
    BATTLE_NAME_DRAW_WRAPPER_ADDRESS,
    CONFIG_CAVE_END_ADDRESS,
    CONFIG_RECORD_COUNT,
    CONFIG_RECORD_STRIDE,
    CONFIG_RECORD_TABLE_ADDRESS,
    DATA_LOAD_SEGMENT_ADDRESS,
    SHARED_ARK16_WIDTH_TABLE_ADDRESS,
)

CONFIG_CAVE_SOURCE_START_ADDRESS = 0x0016F312


CONFIG_MAIN_DRAW_WRAPPER_ADDRESS = 0x0016F314


CONFIG_MAIN_DRAW_WRAPPER_END_ADDRESS = BATTLE_NAME_DRAW_WRAPPER_ADDRESS


CONFIG_DESCRIPTOR_TABLE_ADDRESS = 0x0016F800


CONFIG_WIDTH_TABLE_ADDRESS = SHARED_ARK16_WIDTH_TABLE_ADDRESS


CONFIG_RECORD_MAX_GLYPHS = (CONFIG_RECORD_STRIDE - 4) // 4


CONFIG_STOCK_GLYPH_DRAW_ADDRESS = 0x0000C998


CONFIG_FONT16_GLYPH_LIMIT_ADDRESS = 0x0000C99C


CONFIG_SETTINGS_RAW_ADDRESS = 0x003EAC30


CONFIG_SETTINGS_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS + CONFIG_SETTINGS_RAW_ADDRESS


CONFIG_STOCK_ADVANCE = 16


CONFIG_TRIANGLE = "\u25b3"


CONFIG_TRIANGLE_CODE = 0x0671


CONFIG_TRIANGLE_ADVANCE = 16


CONFIG_STATIC_SELECTOR = 0xFF


CONFIG_ARK16_RECORD_COUNT = 27


CONFIG_MODE_RECORD_FIRST = CONFIG_ARK16_RECORD_COUNT


CONFIG_MODE_STOCK_WIDTHS = (11 * 8, 9 * 8)


CONFIG_MODE_START_X = (240, 256)


CONFIG_MODE_RIGHT_EDGE = 328


CONFIG_MODE_Y_ADJUSTMENTS = (-5, -4)


CONFIG_SPEED_RECORD_FIRST = 17


CONFIG_SPEED_STOCK_START_X = (0xAE, 0xDA, 0x106)


CONFIG_SPEED_STOCK_GLYPH_COUNT = 2


CONFIG_SPEED_GROUP_RIGHT_EDGE = (
    CONFIG_SPEED_STOCK_START_X[-1]
    + CONFIG_SPEED_STOCK_GLYPH_COUNT * CONFIG_STOCK_ADVANCE
)


_CONFIG_LABEL_CALLS = (
    ("config_label_triangle", 0x00035C30, 0),
    ("config_label_start", 0x00035C6C, 1),
    ("config_label_l", 0x00035CA8, 2),
    ("config_label_r", 0x00035CE4, 3),
    ("config_label_auto_mapping", 0x00035D20, 4),
    ("config_label_battle_messages", 0x00035D5C, 5),
    ("config_label_message", 0x00035D98, 6),
    ("config_label_screen_size", 0x00035DD4, 7),
    ("config_label_frame", 0x00035E10, 8),
)


_CONFIG_ACTION_CALLS = (
    ("config_action_triangle", 0x00035E58, 0),
    ("config_action_start", 0x00035EA8, 1),
    ("config_action_l", 0x00035EF8, 6),
    ("config_action_r", 0x00035F48, 7),
)


_CONFIG_ORIENTATION_CALLS = (
    ("config_orientation_first_normal", 0x00035F90, 15),
    ("config_orientation_second_normal", 0x00035FB0, 16),
    ("config_orientation_first_selected", 0x00036578, 15),
    ("config_orientation_second_selected", 0x00036598, 16),
)


_CONFIG_SPEED_CALLS = (
    ("config_battle_speed_fast_normal", 0x00036000, 17),
    ("config_battle_speed_normal_normal", 0x0003601C, 18),
    ("config_battle_speed_slow_normal", 0x0003603C, 19),
    ("config_message_speed_fast_normal", 0x0003608C, 17),
    ("config_message_speed_normal_normal", 0x000360A8, 18),
    ("config_message_speed_slow_normal", 0x000360C8, 19),
    ("config_message_speed_fast_selected_slow", 0x00036370, 17),
    ("config_message_speed_normal_selected_slow", 0x0003638C, 18),
    ("config_message_speed_slow_selected", 0x000363AC, 19),
    ("config_message_speed_fast_selected_normal", 0x000363F0, 17),
    ("config_message_speed_normal_selected", 0x0003640C, 18),
    ("config_message_speed_slow_selected_normal", 0x0003642C, 19),
    ("config_battle_speed_fast_selected_slow", 0x00036478, 17),
    ("config_battle_speed_normal_selected_slow", 0x00036494, 18),
    ("config_battle_speed_slow_selected", 0x000364B4, 19),
    ("config_battle_speed_fast_selected_normal", 0x000364F8, 17),
    ("config_battle_speed_normal_selected", 0x00036514, 18),
    ("config_battle_speed_slow_selected_normal", 0x00036534, 19),
)


CONFIG_MAIN_DRAW_SPECS = tuple(
    sorted(
        (
            *(
                (name, address, record, CONFIG_STATIC_SELECTOR, 0)
                for name, address, record in _CONFIG_LABEL_CALLS
            ),
            *(
                (name, address, 9, selector_offset, 6)
                for name, address, selector_offset in _CONFIG_ACTION_CALLS
            ),
            *(
                (name, address, record, CONFIG_STATIC_SELECTOR, 0)
                for name, address, record in _CONFIG_ORIENTATION_CALLS
            ),
            *(
                (name, address, record, CONFIG_STATIC_SELECTOR, 0)
                for name, address, record in _CONFIG_SPEED_CALLS[:6]
            ),
            ("config_screen_size", 0x00036120, 20, 8, 3),
            ("config_frame", 0x00036178, 23, 9, 3),
            ("config_mode_normal", 0x00036264, 27, CONFIG_STATIC_SELECTOR, 0),
            ("config_secondary_help", 0x000362C4, 26, CONFIG_STATIC_SELECTOR, 0),
            ("config_mode_hard", 0x00036324, 28, CONFIG_STATIC_SELECTOR, 0),
            *(
                (name, address, record, CONFIG_STATIC_SELECTOR, 0)
                for name, address, record in _CONFIG_SPEED_CALLS[6:]
            ),
        ),
        key=lambda item: item[1],
    )
)


CONFIG_MAIN_DRAW_CALL_SITES = tuple(
    (name, address)
    for name, address, _record, _selector, _count in CONFIG_MAIN_DRAW_SPECS
)


@dataclass(frozen=True)
class ConfigMenuPatchSource:
    """Authored CONFIG rows before Ark16 code/advance compilation.

    Contextual help is intentionally absent: IDs 45..53 remain owned by
    ``regdata.bin``.  This source contains the 27 Ark16 rows plus the two Ark12
    mode labels that the executable renderer replaces from BOOT.BIN loops.
    """

    labels: tuple[str, ...]
    actions: tuple[str, ...]
    orientations: tuple[str, ...]
    speeds: tuple[str, ...]
    sizes: tuple[str, ...]
    frames: tuple[str, ...]
    secondary_help: str
    modes: tuple[str, ...]

    @property
    def ark16_records(self) -> tuple[str, ...]:
        return (
            *self.labels,
            *self.actions,
            *self.orientations,
            *self.speeds,
            *self.sizes,
            *self.frames,
            self.secondary_help,
        )

    @property
    def records(self) -> tuple[str, ...]:
        return (*self.ark16_records, *self.modes)


@dataclass(frozen=True)
class ConfigMenuPatch:
    """All CONFIG-only FONT16 hooks, helpers, and compiled row data."""

    main_draw_wrapper: AssembledCode
    descriptor_table: bytes
    width_table: bytes
    record_table: bytes
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex CONFIG write: {name}") from error


def _build_config_main_draw_wrapper() -> AssembledCode:
    """Replace one proven CONFIG row on its first stock loop iteration.

    Every hooked loop uses ``s2`` as its glyph index.  The first call renders
    the selected compiled row with the live x/y/font/color arguments; later
    iterations return without drawing.  The return-address descriptor selects
    the exact fixed row or a checked byte from the live settings object.  Any
    unknown caller or invalid selector tail-calls the stock FONT16 drawer with
    the original arguments.
    """

    code = _Assembler(CONFIG_MAIN_DRAW_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x40)
    code.sw(RA, 0x3C, SP)
    code.sw(S0, 0x38, SP)
    code.sw(S1, 0x34, SP)
    code.sw(S2, 0x30, SP)
    code.sw(S3, 0x2C, SP)
    code.sw(S4, 0x28, SP)
    code.sw(S5, 0x24, SP)
    code.sw(S6, 0x20, SP)
    code.sw(S7, 0x1C, SP)
    code.sw(A3, 0x18, SP)
    code.addu(S0, A0, ZERO)
    code.addu(S1, A1, ZERO)
    code.addu(S3, A2, ZERO)
    code.addu(S4, T0, ZERO)

    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(T8, RA, ZERO)
    code.addiu(T9, RA, CONFIG_DESCRIPTOR_TABLE_ADDRESS - pc_address)
    code.lw(T5, 0x3C, SP)
    code.subu(T5, T5, T8)
    code.addiu(T7, ZERO, len(CONFIG_MAIN_DRAW_SPECS))

    code.label("find_descriptor")
    code.lw(T6, 0, T9)
    code.beq(T6, T5, "descriptor_found")
    code.delay_nop()
    code.addiu(T9, T9, 8)
    code.addiu(T7, T7, -1)
    code.bne(T7, ZERO, "find_descriptor")
    code.delay_nop()
    code.beq(ZERO, ZERO, "fallback")
    code.delay_nop()

    code.label("descriptor_found")
    code.lhu(V0, 4, T9)
    code.lbu(V1, 6, T9)
    code.lbu(T1, 7, T9)
    code.addiu(T2, ZERO, CONFIG_STATIC_SELECTOR)
    code.beq(V1, T2, "record_ready")
    code.delay_nop()

    _load_pc_relative_target(
        code,
        T2,
        T8,
        pc_address=pc_address,
        target_address=CONFIG_SETTINGS_ADDRESS,
    )
    code.addu(T2, T2, V1)
    code.lbu(T2, 0, T2)
    code.sltu(T3, T2, T1)
    code.beq(T3, ZERO, "fallback")
    code.delay_nop()
    code.addu(V0, V0, T2)

    code.label("record_ready")
    code.bne(S2, ZERO, "suppress")
    code.delay_nop()
    code.sll(V0, V0, 8)
    code.addiu(T9, T8, CONFIG_RECORD_TABLE_ADDRESS - pc_address)
    code.addu(S5, T9, V0)
    code.lbu(S6, 0, S5)
    code.lb(T1, 1, S5)
    code.addu(S0, S0, T1)
    code.lb(T1, 2, S5)
    code.addu(S1, S1, T1)
    code.addiu(S5, S5, 4)
    code.beq(S6, ZERO, "suppress")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        S7,
        T8,
        pc_address=pc_address,
        target_address=CONFIG_STOCK_GLYPH_DRAW_ADDRESS,
    )

    code.label("render_glyph")
    code.lhu(A3, 0, S5)
    code.lbu(T1, 2, S5)
    code.addiu(S5, S5, 4)
    code.addiu(S6, S6, -1)
    code.addu(A0, S0, ZERO)
    code.addu(A1, S1, ZERO)
    code.addu(A2, S3, ZERO)
    code.addu(T0, S4, ZERO)
    code.addu(S0, S0, T1)
    code.beq(A3, ZERO, "glyph_done")
    code.delay_nop()
    code.jalr(S7)
    code.delay_nop()

    code.label("glyph_done")
    code.bne(S6, ZERO, "render_glyph")
    code.delay_nop()

    code.label("suppress")
    code.addu(V0, ZERO, ZERO)
    code.lw(S7, 0x1C, SP)
    code.lw(S6, 0x20, SP)
    code.lw(S5, 0x24, SP)
    code.lw(S4, 0x28, SP)
    code.lw(S3, 0x2C, SP)
    code.lw(S2, 0x30, SP)
    code.lw(S1, 0x34, SP)
    code.lw(S0, 0x38, SP)
    code.lw(RA, 0x3C, SP)
    code.addiu(SP, SP, 0x40)
    code.jr(RA)
    code.delay_nop()

    code.label("fallback")
    code.addu(A0, S0, ZERO)
    code.addu(A1, S1, ZERO)
    code.addu(A2, S3, ZERO)
    code.addu(T0, S4, ZERO)
    code.lw(A3, 0x18, SP)
    _load_pc_relative_target(
        code,
        T9,
        T8,
        pc_address=pc_address,
        target_address=CONFIG_STOCK_GLYPH_DRAW_ADDRESS,
    )
    code.lw(S7, 0x1C, SP)
    code.lw(S6, 0x20, SP)
    code.lw(S5, 0x24, SP)
    code.lw(S4, 0x28, SP)
    code.lw(S3, 0x2C, SP)
    code.lw(S2, 0x30, SP)
    code.lw(S1, 0x34, SP)
    code.lw(S0, 0x38, SP)
    code.lw(RA, 0x3C, SP)
    code.addiu(SP, SP, 0x40)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


_CONFIG_SOURCE_GROUP_LENGTHS = (
    ("labels", 9),
    ("actions", 6),
    ("orientations", 2),
    ("speeds", 3),
    ("sizes", 3),
    ("frames", 3),
    ("modes", 2),
)


def _validate_config_menu_source(source: ConfigMenuPatchSource) -> None:
    if not isinstance(source, ConfigMenuPatchSource):
        raise TypeError("PSP CONFIG source must be ConfigMenuPatchSource")
    for group_name, expected_count in _CONFIG_SOURCE_GROUP_LENGTHS:
        group = getattr(source, group_name)
        if not isinstance(group, tuple) or len(group) != expected_count:
            raise ValueError(
                f"PSP CONFIG {group_name} must contain exactly {expected_count} strings"
            )
        if any(not isinstance(text, str) or not text for text in group):
            raise ValueError(f"PSP CONFIG {group_name} must contain nonempty strings")
    if not isinstance(source.secondary_help, str) or not source.secondary_help:
        raise ValueError("PSP CONFIG secondary help must be a nonempty string")
    if len(source.records) != CONFIG_RECORD_COUNT:
        raise ValueError("PSP CONFIG runtime record inventory changed")
    if any(len(text) > CONFIG_RECORD_MAX_GLYPHS for text in source.records):
        raise ValueError(
            f"PSP CONFIG rows may contain at most {CONFIG_RECORD_MAX_GLYPHS} glyphs"
        )


def _validate_config_menu_font(
    source: ConfigMenuPatchSource,
    ark16_glyph_codes: Mapping[str, int],
    ark16_glyph_advances: Mapping[str, int],
    ark12_glyph_codes: Mapping[str, int],
    ark12_glyph_advances: Mapping[str, int],
    *,
    ark16_advance_first_code: int,
    draw_code_limit: int,
) -> tuple[
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, int],
    bytes,
]:
    if (
        not isinstance(ark16_advance_first_code, int)
        or isinstance(ark16_advance_first_code, bool)
        or not 1 <= ark16_advance_first_code <= 0x7FFF
    ):
        raise ValueError("PSP CONFIG Ark16 first code is invalid")
    if (
        not isinstance(draw_code_limit, int)
        or isinstance(draw_code_limit, bool)
        or not ark16_advance_first_code < draw_code_limit <= 0x7FFF
    ):
        raise ValueError("PSP CONFIG FONT16 draw limit is invalid")

    face_inputs = (
        ("Ark16", ark16_glyph_codes, ark16_glyph_advances),
        ("Ark12", ark12_glyph_codes, ark12_glyph_advances),
    )
    normalized: list[tuple[dict[str, int], dict[str, int]]] = []
    for face, glyph_codes, glyph_advances in face_inputs:
        if not isinstance(glyph_codes, Mapping) or not isinstance(
            glyph_advances, Mapping
        ):
            raise TypeError(f"PSP CONFIG {face} codes and advances must be mappings")
        codes = dict(glyph_codes)
        advances = dict(glyph_advances)
        for mapping_name, mapping in (("codes", codes), ("advances", advances)):
            if any(
                not isinstance(character, str) or len(character) != 1
                for character in mapping
            ):
                raise ValueError(
                    f"PSP CONFIG {face} {mapping_name} must use one-character keys"
                )
        if any(
            not isinstance(code, int)
            or isinstance(code, bool)
            or not 0 <= code <= 0xFFFF
            for code in codes.values()
        ):
            raise ValueError(f"PSP CONFIG {face} codes must be u16 integers")
        if any(
            not isinstance(advance, int)
            or isinstance(advance, bool)
            or not 1 <= advance <= 0xFF
            for advance in advances.values()
        ):
            raise ValueError(f"PSP CONFIG {face} advances must be integer bytes")
        normalized.append((codes, advances))

    (ark16_codes, ark16_advances), (ark12_codes, ark12_advances) = normalized
    ark16_required = frozenset("".join(source.ark16_records)) | {
        " ",
        CONFIG_TRIANGLE,
    }
    ark12_required = frozenset("".join(source.modes)) | {" "}
    for face, required, codes, advances in (
        ("Ark16", ark16_required, ark16_codes, ark16_advances),
        ("Ark12", ark12_required, ark12_codes, ark12_advances),
    ):
        missing_codes = sorted(required - codes.keys())
        missing_advances = sorted(required - advances.keys())
        if missing_codes or missing_advances:
            missing = missing_codes or missing_advances
            raise ValueError(f"PSP CONFIG {face} mapping is missing {missing[0]!r}")
    if ark16_codes[" "] != 0:
        raise ValueError("PSP CONFIG Ark16 space must use logical code 0")
    if ark12_codes[" "] != 0:
        raise ValueError("PSP CONFIG Ark12 space must use logical code 0")
    if (
        ark16_codes[CONFIG_TRIANGLE],
        ark16_advances[CONFIG_TRIANGLE],
    ) != (
        CONFIG_TRIANGLE_CODE,
        CONFIG_TRIANGLE_ADVANCE,
    ):
        raise ValueError("PSP CONFIG triangle must preserve stock FONT16 code 0x671")

    advances_by_code: dict[int, int] = {}
    for character, code_value in ark16_codes.items():
        if character not in ark16_advances:
            continue
        if code_value in advances_by_code:
            raise ValueError(f"PSP CONFIG Ark16 code {code_value:#x} is duplicated")
        advances_by_code[code_value] = ark16_advances[character]
    width_table = bytearray()
    for code_value in range(ark16_advance_first_code, draw_code_limit):
        try:
            width_table.append(advances_by_code[code_value])
        except KeyError as error:
            raise ValueError(
                f"PSP CONFIG Ark16 width table is missing code {code_value:#x}"
            ) from error
    if len(width_table) > CONFIG_RECORD_TABLE_ADDRESS - CONFIG_WIDTH_TABLE_ADDRESS:
        raise ValueError("PSP CONFIG Ark16 widths exceed their cave partition")

    for text in source.ark16_records:
        for character in text:
            code_value = ark16_codes[character]
            if code_value in (0, CONFIG_TRIANGLE_CODE):
                continue
            if not ark16_advance_first_code <= code_value < draw_code_limit:
                raise ValueError(
                    f"PSP CONFIG character {character!r} escaped Ark16 range"
                )
    for text in source.modes:
        for character in text:
            code_value = ark12_codes[character]
            if code_value and not 0 < code_value < 0x100:
                raise ValueError(
                    f"PSP CONFIG mode character {character!r} escaped Ark12 page"
                )
    return (
        ark16_codes,
        ark16_advances,
        ark12_codes,
        ark12_advances,
        bytes(width_table),
    )


def _build_config_record_table(
    source: ConfigMenuPatchSource,
    ark16_codes: Mapping[str, int],
    ark16_advances: Mapping[str, int],
    ark12_codes: Mapping[str, int],
    ark12_advances: Mapping[str, int],
) -> bytes:
    speed_widths = tuple(
        sum(ark16_advances[character] for character in text) for text in source.speeds
    )
    speed_gap_pixels = (
        CONFIG_SPEED_GROUP_RIGHT_EDGE
        - CONFIG_SPEED_STOCK_START_X[0]
        - sum(speed_widths)
    )
    if speed_gap_pixels < 0 or speed_gap_pixels % (len(speed_widths) - 1):
        raise ValueError(
            "PSP CONFIG speed labels cannot be evenly spaced in the stock group"
        )
    speed_gap = speed_gap_pixels // (len(speed_widths) - 1)
    speed_starts = [CONFIG_SPEED_STOCK_START_X[0]]
    for width in speed_widths[:-1]:
        speed_starts.append(speed_starts[-1] + width + speed_gap)
    speed_adjustments = tuple(
        start - stock_start
        for start, stock_start in zip(
            speed_starts,
            CONFIG_SPEED_STOCK_START_X,
            strict=True,
        )
    )
    if speed_starts[-1] + speed_widths[-1] != CONFIG_SPEED_GROUP_RIGHT_EDGE:
        raise ValueError("PSP CONFIG speed layout no longer preserves its group bounds")
    if any(not -0x80 <= adjustment <= 0x7F for adjustment in speed_adjustments):
        raise ValueError("PSP CONFIG speed x adjustment escaped s8")

    table = bytearray(CONFIG_RECORD_COUNT * CONFIG_RECORD_STRIDE)
    for record_index, text in enumerate(source.records):
        start = record_index * CONFIG_RECORD_STRIDE
        if record_index < CONFIG_ARK16_RECORD_COUNT:
            codes = ark16_codes
            advances = ark16_advances
            speed_index = record_index - CONFIG_SPEED_RECORD_FIRST
            x_adjust = (
                speed_adjustments[speed_index]
                if 0 <= speed_index < len(speed_adjustments)
                else 0
            )
            y_adjust = 0
        else:
            codes = ark12_codes
            advances = ark12_advances
            mode_index = record_index - CONFIG_MODE_RECORD_FIRST
            measured_width = sum(advances[character] for character in text)
            x_adjust = CONFIG_MODE_STOCK_WIDTHS[mode_index] - measured_width
            y_adjust = CONFIG_MODE_Y_ADJUSTMENTS[mode_index]
            if not -0x80 <= x_adjust <= 0x7F:
                raise ValueError(
                    f"PSP CONFIG mode {mode_index} x adjustment escaped s8"
                )
        struct.pack_into("<BbbB", table, start, len(text), x_adjust, y_adjust, 0)
        cursor = start + 4
        for character in text:
            struct.pack_into(
                "<HBB",
                table,
                cursor,
                codes[character],
                advances[character],
                0,
            )
            cursor += 4
    return bytes(table)


def _build_config_descriptor_table(*, pc_anchor: int) -> bytes:
    table = bytearray()
    for (
        _name,
        address,
        record,
        selector_offset,
        selector_count,
    ) in CONFIG_MAIN_DRAW_SPECS:
        table.extend(
            struct.pack(
                "<IHBB",
                (address + 8 - pc_anchor) & 0xFFFFFFFF,
                record,
                selector_offset,
                selector_count,
            )
        )
    return bytes(table)


def build_config_menu_patch(
    source: ConfigMenuPatchSource,
    ark16_glyph_codes: Mapping[str, int],
    ark16_glyph_advances: Mapping[str, int],
    ark12_glyph_codes: Mapping[str, int],
    ark12_glyph_advances: Mapping[str, int],
    *,
    ark16_advance_first_code: int,
    draw_code_limit: int,
    font16_draw_code_limit: int | None = None,
    include_draw_limit: bool = True,
) -> ConfigMenuPatch:
    """Build the complete PSP CONFIG dual-face renderer contract.

    The executable owns 27 Ark16 rows plus two right-aligned Ark12 mode labels.
    The shared ``regdata.bin`` help loop is composed independently by the
    command-menu help feature so CONFIG does not claim a cross-surface hook.
    """

    if not isinstance(include_draw_limit, bool):
        raise TypeError("PSP CONFIG draw-limit ownership must be boolean")
    if font16_draw_code_limit is None:
        font16_draw_code_limit = draw_code_limit
    if (
        not isinstance(font16_draw_code_limit, int)
        or isinstance(font16_draw_code_limit, bool)
        or not draw_code_limit <= font16_draw_code_limit <= 0x7FFF
    ):
        raise ValueError("PSP shared FONT16 draw limit is invalid")
    _validate_config_menu_source(source)
    (
        ark16_codes,
        ark16_advances,
        ark12_codes,
        ark12_advances,
        width_table,
    ) = _validate_config_menu_font(
        source,
        ark16_glyph_codes,
        ark16_glyph_advances,
        ark12_glyph_codes,
        ark12_glyph_advances,
        ark16_advance_first_code=ark16_advance_first_code,
        draw_code_limit=draw_code_limit,
    )
    main_draw_wrapper = _build_config_main_draw_wrapper()
    descriptor_table = _build_config_descriptor_table(
        pc_anchor=main_draw_wrapper.label_address("pc")
    )
    record_table = _build_config_record_table(
        source,
        ark16_codes,
        ark16_advances,
        ark12_codes,
        ark12_advances,
    )
    if main_draw_wrapper.end_address > CONFIG_MAIN_DRAW_WRAPPER_END_ADDRESS:
        raise ValueError("PSP CONFIG main wrapper exceeds its cave partition")
    if CONFIG_DESCRIPTOR_TABLE_ADDRESS + len(descriptor_table) > (
        CONFIG_WIDTH_TABLE_ADDRESS
    ):
        raise ValueError("PSP CONFIG descriptors exceed their cave partition")
    if CONFIG_WIDTH_TABLE_ADDRESS + len(width_table) > CONFIG_RECORD_TABLE_ADDRESS:
        raise ValueError("PSP CONFIG widths exceed their cave partition")
    if len(record_table) != CONFIG_RECORD_COUNT * CONFIG_RECORD_STRIDE:
        raise ValueError("PSP CONFIG record table size changed")
    if CONFIG_RECORD_TABLE_ADDRESS + len(record_table) > CONFIG_CAVE_END_ADDRESS:
        raise ValueError("PSP CONFIG records exceed the checked source-zero run")

    hook_writes = tuple(
        PatchWrite(
            name,
            address,
            _word_bytes(_jal_word(address, CONFIG_MAIN_DRAW_WRAPPER_ADDRESS)),
        )
        for name, address in CONFIG_MAIN_DRAW_CALL_SITES
    )
    draw_limit_writes = (
        (
            PatchWrite(
                "config_font16_glyph_limit",
                CONFIG_FONT16_GLYPH_LIMIT_ADDRESS,
                _word_bytes(_i_type(0x0A, A3, V0, font16_draw_code_limit)),
            ),
        )
        if include_draw_limit
        else ()
    )
    writes = (
        hook_writes
        + draw_limit_writes
        + (
            PatchWrite(
                "config_main_draw_wrapper",
                main_draw_wrapper.address,
                main_draw_wrapper.data,
            ),
            PatchWrite(
                "config_main_descriptors",
                CONFIG_DESCRIPTOR_TABLE_ADDRESS,
                descriptor_table,
            ),
            PatchWrite(
                "config_ark16_widths",
                CONFIG_WIDTH_TABLE_ADDRESS,
                width_table,
            ),
            PatchWrite(
                "config_main_records",
                CONFIG_RECORD_TABLE_ADDRESS,
                record_table,
            ),
        )
    )
    if len({write.name for write in writes}) != len(writes):
        raise ValueError("PSP CONFIG patch contains duplicate write names")
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left, right in zip(ordered, ordered[1:]):
        if left.end_address > right.address:
            raise ValueError(f"PSP CONFIG writes overlap: {left.name} and {right.name}")
    return ConfigMenuPatch(
        main_draw_wrapper,
        descriptor_table,
        width_table,
        record_table,
        writes,
    )


__all__ = [
    "CONFIG_ARK16_RECORD_COUNT",
    "CONFIG_CAVE_SOURCE_START_ADDRESS",
    "CONFIG_DESCRIPTOR_TABLE_ADDRESS",
    "CONFIG_FONT16_GLYPH_LIMIT_ADDRESS",
    "CONFIG_MAIN_DRAW_CALL_SITES",
    "CONFIG_MAIN_DRAW_SPECS",
    "CONFIG_MAIN_DRAW_WRAPPER_ADDRESS",
    "CONFIG_MAIN_DRAW_WRAPPER_END_ADDRESS",
    "CONFIG_MODE_RECORD_FIRST",
    "CONFIG_MODE_RIGHT_EDGE",
    "CONFIG_MODE_START_X",
    "CONFIG_MODE_STOCK_WIDTHS",
    "CONFIG_MODE_Y_ADJUSTMENTS",
    "CONFIG_RECORD_MAX_GLYPHS",
    "CONFIG_SETTINGS_ADDRESS",
    "CONFIG_SETTINGS_RAW_ADDRESS",
    "CONFIG_SPEED_GROUP_RIGHT_EDGE",
    "CONFIG_SPEED_RECORD_FIRST",
    "CONFIG_SPEED_STOCK_GLYPH_COUNT",
    "CONFIG_SPEED_STOCK_START_X",
    "CONFIG_STATIC_SELECTOR",
    "CONFIG_STOCK_ADVANCE",
    "CONFIG_STOCK_GLYPH_DRAW_ADDRESS",
    "CONFIG_TRIANGLE",
    "CONFIG_TRIANGLE_ADVANCE",
    "CONFIG_TRIANGLE_CODE",
    "CONFIG_WIDTH_TABLE_ADDRESS",
    "ConfigMenuPatch",
    "ConfigMenuPatchSource",
    "build_config_menu_patch",
]


