"""Dependency-free Allegrex name-entry surface runtime."""

from __future__ import annotations

import struct
from collections.abc import Iterable
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
    S6,
    SP,
    T0,
    T1,
    T2,
    T3,
    T4,
    T5,
    T6,
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
    _word_bytes,
)
from ..core.layout import (
    DATA_LOAD_SEGMENT_ADDRESS,
    EVENT_OPTION_RESET_WRAPPER_ADDRESS,
    NAME_DATA_SEGMENT_ADDRESS,
    NAME_FIELD_MAX,
    NAME_PROFILE_ADDRESS,
    NAME_PROFILE_CODENAME_MIRROR_OFFSET,
    NAME_PROFILE_FIELD_OFFSETS,
)
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    GLYPH_CODE_BIAS,
    GLYPH_CODE_FIRST,
    STORED_PRINTABLE_FIRST,
    STORED_PRINTABLE_LAST,
    encode_ascii_character,
)

PACKED_FIRST = STORED_PRINTABLE_FIRST
PACKED_LAST = STORED_PRINTABLE_LAST
PACKED_RUNTIME_BIAS = GLYPH_CODE_BIAS
PACKED_RUNTIME_FIRST = GLYPH_CODE_FIRST
PACKED_WIDTH_COUNT = ASCII_LAST - ASCII_FIRST + 1


def _packed_storage_index(character: str) -> int:
    return encode_ascii_character(character) - PACKED_FIRST


def _validate_widths(widths: Iterable[int]) -> bytes:
    try:
        values = tuple(widths)
    except TypeError as error:
        raise TypeError("PSP VWF widths must be an iterable of integers") from error
    if len(values) != PACKED_WIDTH_COUNT:
        raise ValueError(
            f"PSP VWF width table has {len(values)} entries; "
            f"expected {PACKED_WIDTH_COUNT}"
        )
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= 0xFF
        for value in values
    ):
        raise ValueError("PSP VWF widths must be integer bytes from 1 through 255")
    return bytes(values)

NAME_LABEL_DRAW_WRAPPER_ADDRESS = 0x0013FC10
NAME_GLYPH_TO_BYTE_ADDRESS = 0x0013FD40
NAME_BYTE_TO_GLYPH_ADDRESS = 0x0013FDC0
NAME_WIDTH_TABLE_ADDRESS = 0x0013FE40
NAME_X_START_TABLE_ADDRESS = 0x0013FEA0

# The Saturn-compatible NAME controller helpers follow the VWF data.  Every
# entry has a fixed partition so a growing helper fails at build time instead
# of silently consuming another helper or the end of the checked cave.
NAME_INIT_WRAPPER_ADDRESS = 0x0013FED8
NAME_PROMPT_WRAPPER_ADDRESS = 0x0013FFC0
NAME_ECHO_WRAPPER_ADDRESS = 0x001400A8
NAME_DONE_HANDLER_ADDRESS = 0x00140108
NAME_SELECT_WRAPPER_ADDRESS = 0x00140250
NAME_BUTTON_HELPER_ADDRESS = 0x00140350
NAME_DONE_SOUND_WRAPPER_ADDRESS = 0x00140440
NAME_CONFIRM_WRAPPER_ADDRESS = 0x00140500
NAME_COMMIT_WRAPPER_ADDRESS = 0x001406C0
NAME_CACHE_REBUILD_ADDRESS = 0x001407F0
NAME_LOAD_WRAPPER_ADDRESS = 0x00140900
NAME_NEW_PROFILE_WRAPPER_ADDRESS = 0x00140960
NAME_RESET_WRAPPER_ADDRESS = 0x001409E0
NAME_RENAME_SYNC_ADDRESS = 0x00140A80

NAME_LABEL_DRAW_CALL_ADDRESS = 0x0009E260
NAME_GLYPH_TO_BYTE_CALL_ADDRESSES = (0x0009DEB8, 0x0009ECAC)
NAME_BYTE_TO_GLYPH_CALL_ADDRESS = 0x0009CE58
NAME_DESCRIPTOR_TABLE_ADDRESS = 0x001C6BD4
NAME_DESCRIPTOR_COUNT = 27
NAME_DESCRIPTOR_PRESERVE_INDICES = frozenset({0})
NAME_DESCRIPTOR_LITERAL_LABELS: tuple[tuple[int, str], ...] = ()
NAME_DESCRIPTOR_SUPPRESS_INDICES: frozenset[int] = frozenset()
NAME_GRID0_COUNT_ADDRESS = 0x001C8AF8
NAME_GRID_PRIMARY_ADDRESS = 0x001C6CAC
NAME_GRID_LOWER_ADDRESS = 0x001C8764
NAME_GRID_SYMBOL_ADDRESS = 0x001C8894
NAME_GRID_SECONDARY_UPPER_ADDRESS = 0x001C89C4
NAME_LABEL_BLOB_ADDRESS = 0x001C6DDC
NAME_LABEL_BLOB_MAX_SIZE = 0x400
NAME_LABEL_BLOB_STATIC_MAX_SIZE = 0x380

# The stock echo coordinate pointer table gives First and Codename only six
# valid positions.  Last and the address rows already target this contiguous
# eight-position table.  Reusing its raw relocation addend keeps all five
# Saturn fields on one eight-cell placement contract.
NAME_ECHO_X_POINTER_TABLE_ADDRESS = 0x001C8B84
NAME_ECHO_EIGHT_X_RAW_ADDRESS = 0x0004E56C
NAME_ECHO_EIGHT_X_ADDRESS = NAME_DATA_SEGMENT_ADDRESS + NAME_ECHO_EIGHT_X_RAW_ADDRESS

# The retired tail of the old Kanji label pool is writable static storage.  It
# outlives the NAME screen's heap object and is therefore the decoded source
# used by EVENT/menu readers after a profile load.  Last precedes First so the
# stock full-name renderer can retain its contiguous Last+First walk.
NAME_RUNTIME_CACHE_ADDRESS = NAME_LABEL_BLOB_ADDRESS + 0x380
NAME_RUNTIME_CACHE_ROW_SIZE = 0x10
NAME_RUNTIME_CACHE_ROWS = ("last", "first", "codename", "city", "ward")
NAME_RUNTIME_CACHE_ADDRESSES = {
    key: NAME_RUNTIME_CACHE_ADDRESS + index * NAME_RUNTIME_CACHE_ROW_SIZE
    for index, key in enumerate(NAME_RUNTIME_CACHE_ROWS)
}
NAME_RUNTIME_CACHE_RELOCATION_ADDENDS = {
    key: address - NAME_DATA_SEGMENT_ADDRESS
    for key, address in NAME_RUNTIME_CACHE_ADDRESSES.items()
}
NAME_GRID_PUNCTUATION_TABLE_ADDRESS = NAME_LABEL_BLOB_ADDRESS + 0x3D0

NAME_GRID_ROWS = 8
NAME_GRID_COLUMNS = 19
NAME_GRID_WORD_COUNT = NAME_GRID_ROWS * NAME_GRID_COLUMNS
NAME_GRID_SENTINEL = 0x0061
# PSP uses a different display code for its native Done graphic, but the cell
# occupies the same Saturn position and is the only authored control cell.
NAME_GRID_DONE = 0x83C0

# The native grid renderer owns these low Member-5 glyph IDs.  Selected cells
# are translated to the high packed-runtime page before they enter a staged
# name buffer, matching Saturn's separate display and commit tables.
NAME_GRID_LOW_PUNCTUATION = {
    ":": 0x0006,
    "?": 0x0008,
    "!": 0x0009,
    " ": 0x0011,
    "-": 0x001D,
    "/": 0x001E,
    "'": 0x0026,
    "&": 0x0054,
    ",": 0x0003,
    ".": 0x0004,
}

NAME_FIELD_KEYS = ("first", "last", "codename", "city", "ward")
NAME_FIELD_LIMITS = (NAME_FIELD_MAX,) * len(NAME_FIELD_KEYS)
NAME_FIELD_BUFFER_BASE = 0x1290
NAME_FIELD_BUFFER_STRIDE = 0x20
NAME_FIELD_COUNT = len(NAME_FIELD_KEYS)
NAME_OCCUPATION_BUFFER_INDEX = 5
NAME_OCCUPATION_SELECTION_OFFSET = 0x1410
NAME_LOGICAL_FIELD_OFFSET = 0x1414
NAME_STATE_SIZE = 0x1418
# The stock PSP tab renderer uses this ABGR value for its selected yellow.
# Reusing it gives the occupation grid Saturn's selected-text behavior without
# introducing a PSP-only cursor box or a new shared-font color contract.
NAME_OCCUPATION_HIGHLIGHT_COLOR = 0xFF01EFE3

NAME_STATE_POINTER_RAW_ADDRESS = 0x00076EE4
NAME_STATE_POINTER_ADDRESS = NAME_DATA_SEGMENT_ADDRESS + NAME_STATE_POINTER_RAW_ADDRESS

# ``sdata/SE.bin`` stores se060.AIF at member zero, so PSP's sound dispatcher
# takes the Saturn sound number minus 60.  NAME's successful Done and empty-row
# buzz are therefore members 2 (se062) and 4 (se064), respectively.
NAME_SOUND_DISPATCH_ADDRESS = 0x000A0028
NAME_SOUND_ACCEPT_INDEX = 2
NAME_SOUND_ERROR_INDEX = 4

NAME_REAL_NAME_LIMIT_ADDRESS = 0x0009CE08
NAME_RENAME_CODENAME_LIMIT_ADDRESS = 0x0009CE28
NAME_CODENAME_LIMIT_ADDRESS = 0x0009DB14
NAME_ADDRESS_LIMIT_ADDRESS = 0x0009DAF4
NAME_FIELD_LIMIT_SOURCE_CONTRACTS = (
    ("first", NAME_REAL_NAME_LIMIT_ADDRESS, 0x24020006),
    ("rename_codename", NAME_RENAME_CODENAME_LIMIT_ADDRESS, 0x24020008),
    ("codename", NAME_CODENAME_LIMIT_ADDRESS, 0x24020008),
    ("city", NAME_ADDRESS_LIMIT_ADDRESS, 0x24020006),
)

# These stock stores seed the old combined address row.  The init wrapper owns
# the separate City/Ward defaults, so the four writes are neutralized after the
# checked memset call.
NAME_ADDRESS_DEFAULT_STORE_CONTRACTS = (
    ("name_address_default_09cdf4", 0x0009CDF4, 0xACC212D0, 0xACC012D0),
    ("name_address_default_09cdfc", 0x0009CDFC, 0xACC312D4, 0xACC012D4),
    ("name_address_default_09ce04", 0x0009CE04, 0xACC212DC, 0xACC012DC),
    ("name_address_default_09ce0c", 0x0009CE0C, 0xACC312E0, 0xACC012E0),
)


# -- Patch result contracts -------------------------------------------------


@dataclass(frozen=True)
class NameEntryPatchSource:
    """Authored PSP NAME grids and labels before binary compilation."""

    grids: tuple[tuple[str, str], ...]
    descriptor_labels: tuple[str | None, ...]
    default_city: str
    default_ward: str


@dataclass(frozen=True)
class NameEntryPatch:
    """Saturn-compatible NAME controller, renderer, codecs, and data writes."""

    label_draw_wrapper: AssembledCode
    glyph_to_byte: AssembledCode
    byte_to_glyph: AssembledCode
    runtime_helpers: tuple[AssembledCode, ...]
    writes: tuple[PatchWrite, ...]

    def write(self, name: str) -> PatchWrite:
        try:
            return next(write for write in self.writes if write.name == name)
        except StopIteration as error:
            raise KeyError(f"unknown Allegrex name-entry write: {name}") from error


# -- Allegrex instruction encoding -----------------------------------------


def _second_load_pointer_words(register: int, target_address: int) -> tuple[int, int]:
    """Encode one HI16/LO16 pair whose relocations target PT_LOAD number two.

    The PSP relocation records at the native name readers add the second
    segment's module-relative address at load time.  Their instruction
    immediates must therefore contain a segment-relative addend, unlike the
    absolute module addresses used by relocation-free cave helpers.
    """

    addend = target_address - DATA_LOAD_SEGMENT_ADDRESS
    if not 0 <= addend <= 0xFFFFFFFF:
        raise ValueError("PSP second-load pointer target is outside its segment")
    upper = (addend + 0x8000) >> 16
    if upper > 0xFFFF:
        raise ValueError("PSP second-load pointer addend exceeds a HI16/LO16 pair")
    return (
        _i_type(0x0F, ZERO, register, upper),
        _i_type(0x09, register, register, addend),
    )


# -- Checked hook contracts -------------------------------------------------


NAME_HOOK_CONTRACTS = (
    (
        "name_label_draw_call",
        NAME_LABEL_DRAW_CALL_ADDRESS,
        _jal_word(NAME_LABEL_DRAW_CALL_ADDRESS, 0x0009EEA8),
        _jal_word(NAME_LABEL_DRAW_CALL_ADDRESS, NAME_LABEL_DRAW_WRAPPER_ADDRESS),
    ),
    (
        "name_glyph_to_byte_call_09deb8",
        NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[0],
        _jal_word(NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[0], 0x0009EC08),
        _jal_word(NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[0], NAME_GLYPH_TO_BYTE_ADDRESS),
    ),
    (
        "name_glyph_to_byte_call_09ecac",
        NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[1],
        _jal_word(NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[1], 0x0009EC08),
        _jal_word(NAME_GLYPH_TO_BYTE_CALL_ADDRESSES[1], NAME_GLYPH_TO_BYTE_ADDRESS),
    ),
    (
        "name_byte_to_glyph_call",
        NAME_BYTE_TO_GLYPH_CALL_ADDRESS,
        _jal_word(NAME_BYTE_TO_GLYPH_CALL_ADDRESS, 0x0009EC3C),
        _jal_word(NAME_BYTE_TO_GLYPH_CALL_ADDRESS, NAME_BYTE_TO_GLYPH_ADDRESS),
    ),
)


# Every non-data NAME write pins the exact stock instruction it replaces.  The
# executable composer verifies these words before applying any cave or profile
# reader changes, so an address-map drift fails closed.
NAME_INSTRUCTION_PATCH_CONTRACTS = (
    # Controller hooks and expanded heap layout.
    ("name_state_size_alloc", 0x0009CD0C, (0x24041394,), (0x24041418,)),
    ("name_state_size_clear", 0x0009CD30, (0x24061394,), (0x24061418,)),
    (
        "name_init_call",
        0x0009CD34,
        (0x0C032795,),
        (_jal_word(0x0009CD34, NAME_INIT_WRAPPER_ADDRESS),),
    ),
    ("name_handle_init_base", 0x0009CDC4, (0x24621310,), (0x24621350,)),
    ("name_handle_init_rows", 0x0009CDE0, (0x28E20004,), (0x28E20006,)),
    ("name_limit_first", 0x0009CE08, (0x24020006,), (0x24020008,)),
    (
        "name_occupation_init_offset",
        0x0009CE14,
        (0xACC51390,),
        (0xACC51410,),
    ),
    ("name_rename_buffer_store", 0x0009CE64, (0xAE0212B0,), (0xAE0212D0,)),
    (
        "name_echo_call",
        0x0009D074,
        (0x0C027A1B,),
        (_jal_word(0x0009D074, NAME_ECHO_WRAPPER_ADDRESS),),
    ),
    (
        "name_prompt_call",
        0x0009D4A8,
        (0x0C027875,),
        (_jal_word(0x0009D4A8, NAME_PROMPT_WRAPPER_ADDRESS),),
    ),
    ("name_confirm_max", 0x0009D518, (0x24100006,), (0x24100008,)),
    (
        "name_confirm_draw_call",
        0x0009D620,
        (0x0C027875,),
        (_jal_word(0x0009D620, NAME_CONFIRM_WRAPPER_ADDRESS),),
    ),
    (
        "name_confirm_skip_stock_rows",
        0x0009D628,
        (0x24040006, 0x24050058),
        (0x1000002D, 0x00000000),
    ),
    ("name_rename_echo_row", 0x0009D7A8, (0x24040001,), (0x24040002,)),
    ("name_grid_entry_all_tabs", 0x0009D910, (0x5040000D,), (0x1000000D,)),
    # State 3 is the occupation screen.  Retarget only its cursor branch to the
    # existing post-draw exit; the shared grid-cursor draw at 0x9d2d0 remains.
    ("name_occupation_cursor_box", 0x0009D254, (0x10620022,), (0x10620020,)),
    (
        "name_select_call",
        0x0009D9F0,
        (0x0C02795F,),
        (_jal_word(0x0009D9F0, NAME_SELECT_WRAPPER_ADDRESS),),
    ),
    (
        "name_select_sound_call",
        0x0009D9FC,
        (0x0C02800A, 0x24040002),
        (
            _jal_word(0x0009D9FC, NAME_DONE_SOUND_WRAPPER_ADDRESS),
            0x24040002,
        ),
    ),
    ("name_insert_logical_row", 0x0009DA24, (0x8C820000,), (0x8C821414,)),
    (
        "name_done_call",
        0x0009DA70,
        (0x0C027A93,),
        (_jal_word(0x0009DA70, NAME_DONE_HANDLER_ADDRESS),),
    ),
    ("name_done_logical_row", 0x0009DA74, (0x8C440000,), (0x8C441414,)),
    ("name_limit_address", 0x0009DAF4, (0x24020006,), (0x24020008,)),
    ("name_limit_codename", 0x0009DB14, (0x24020008,), (0x24020008,)),
    (
        "name_button_call",
        0x0009DB7C,
        (0x0C000321,),
        (_jal_word(0x0009DB7C, NAME_BUTTON_HELPER_ADDRESS),),
    ),
    (
        "name_occupation_selection_store",
        0x0009DDB0,
        (0xAC821390,),
        (0xAC821410,),
    ),
    ("name_rename_buffer_load", 0x0009DEBC, (0x944412B0,), (0x944412D0,)),
    (
        "name_rename_sync_jump",
        0x0009DED4,
        (0x0802761E,),
        (_j_word(0x0009DED4, NAME_RENAME_SYNC_ADDRESS),),
    ),
    (
        "name_occupation_commit_load",
        0x0009DF68,
        (0x8CA21390,),
        (0x8CA21410,),
    ),
    (
        "name_commit_call",
        0x0009DF6C,
        (0x0C027B1C,),
        (_jal_word(0x0009DF6C, NAME_COMMIT_WRAPPER_ADDRESS),),
    ),
    (
        "name_reset_new_call",
        0x0009DFD4,
        (0x0C0273A3,),
        (_jal_word(0x0009DFD4, NAME_RESET_WRAPPER_ADDRESS),),
    ),
    (
        "name_reset_rename_call",
        0x0009DFEC,
        (0x0C0273A3,),
        (_jal_word(0x0009DFEC, NAME_RESET_WRAPPER_ADDRESS),),
    ),
    ("name_handle_cleanup_load", 0x0009E178, (0x8C431310,), (0x8C431350,)),
    ("name_handle_cleanup_store", 0x0009E194, (0xAC531310,), (0xAC531350,)),
    ("name_handle_cleanup_rows", 0x0009E1A4, (0x2A820004,), (0x2A820006,)),
    ("name_echo_occupation_cursor", 0x0009E8FC, (0x38820003,), (0x38820005,)),
    ("name_echo_handle_base", 0x0009E964, (0xAE021310,), (0xAE021350,)),
    ("name_echo_disable_address_suffix", 0x0009E980, (0x24020002,), (0x24020006,)),
    ("name_echo_occupation_row", 0x0009E988, (0x24020003,), (0x24020005,)),
    (
        "name_echo_occupation_offset",
        0x0009E9C8,
        (0x8C441390,),
        (0x8C441410,),
    ),
    ("name_finalizer_code_offset", 0x0009EC90, (0x2671000C,), (0x26710010,)),
    ("name_finalizer_packed_load", 0x0009ECA8, (0x96240000,), (0x92240000,)),
    ("name_finalizer_byte_stride", 0x0009ECB0, (0x26310002,), (0x26310001,)),
    (
        "name_load_call",
        0x000114A0,
        (0x0C00310C,),
        (_jal_word(0x000114A0, NAME_LOAD_WRAPPER_ADDRESS),),
    ),
    (
        "name_new_profile_jump",
        0x00074A3C,
        (0x0801D238,),
        (_j_word(0x00074A3C, NAME_NEW_PROFILE_WRAPPER_ADDRESS),),
    ),
    # Incremental EVENT/name-token readers.
    (
        "name_cache_first_inc_ptr",
        0x00073C7C,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["first"]),
    ),
    ("name_cache_first_inc_offset", 0x00073C8C, (0x94650006,), (0x94650000,)),
    (
        "name_cache_last_inc_ptr",
        0x00073CD0,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["last"]),
    ),
    (
        "name_cache_ward_inc_ptr",
        0x00073D4C,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["ward"]),
    ),
    ("name_cache_ward_inc_offset", 0x00073D60, (0x94650022,), (0x94650000,)),
    (
        "name_cache_city_inc_ptr",
        0x00073D68,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["city"]),
    ),
    ("name_cache_city_inc_offset", 0x00073D7C, (0x9465001C,), (0x94650000,)),
    (
        "name_cache_code_inc_ptr",
        0x00073DB8,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["codename"]),
    ),
    ("name_cache_code_inc_offset", 0x00073DCC, (0x9465000C,), (0x94650000,)),
    (
        "name_cache_first_full_hi",
        0x00073E4C,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["first"])[0],),
    ),
    (
        "name_cache_first_full_lo",
        0x00073E54,
        (0x24C66CFE,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["first"])[1],),
    ),
    ("name_cache_full_count", 0x00073E5C, (0x24070003,), (0x24070008,)),
    (
        "name_cache_last_full_hi",
        0x00073E70,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["last"])[0],),
    ),
    (
        "name_cache_last_full_lo",
        0x00073E78,
        (0x24C66CF8,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["last"])[1],),
    ),
    (
        "name_cache_ward_full_hi",
        0x00073EE0,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["ward"])[0],),
    ),
    (
        "name_cache_ward_full_lo",
        0x00073EE8,
        (0x24C66D1A,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["ward"])[1],),
    ),
    (
        "name_cache_city_full_hi",
        0x00073EF4,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["city"])[0],),
    ),
    (
        "name_cache_city_full_lo",
        0x00073EFC,
        (0x24C66D14,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["city"])[1],),
    ),
    (
        "name_cache_code_full_hi",
        0x00073F38,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["codename"])[0],),
    ),
    (
        "name_cache_code_full_lo",
        0x00073F40,
        (0x24C66D04,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["codename"])[1],),
    ),
    (
        "name_cache_parallel_first_inc_ptr",
        0x0007413C,
        (0x3C02003F, 0x24426CF8),
        _second_load_pointer_words(V0, NAME_RUNTIME_CACHE_ADDRESSES["first"]),
    ),
    ("name_cache_parallel_first_inc_offset", 0x0007414C, (0x94650006,), (0x94650000,)),
    (
        "name_cache_parallel_first_full_hi",
        0x000742B8,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["first"])[0],),
    ),
    (
        "name_cache_parallel_first_full_lo",
        0x000742C0,
        (0x24C66CFE,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["first"])[1],),
    ),
    ("name_cache_parallel_first_count", 0x000742CC, (0x24070003,), (0x24070008,)),
    # EVENT's combined Last+First renderer.
    (
        "name_cache_event_last_strlen_hi",
        0x000761CC,
        (0x3C04003F,),
        (_second_load_pointer_words(A0, NAME_RUNTIME_CACHE_ADDRESSES["last"])[0],),
    ),
    (
        "name_cache_event_draw_hi",
        0x000761E8,
        (0x3C06003F,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["last"])[0],),
    ),
    (
        "name_cache_event_draw_lo",
        0x000761FC,
        (0x24C66CF8,),
        (_second_load_pointer_words(A2, NAME_RUNTIME_CACHE_ADDRESSES["last"])[1],),
    ),
    (
        "name_cache_event_last_strlen_lo",
        0x00076308,
        (0x24846CF8,),
        (_second_load_pointer_words(A0, NAME_RUNTIME_CACHE_ADDRESSES["last"])[1],),
    ),
    ("name_cache_event_last_count", 0x00076310, (0x24050003,), (0x24050008,)),
    (
        "name_cache_event_first_strlen",
        0x0007631C,
        (0x3C04003F, 0x24846CFE),
        _second_load_pointer_words(A0, NAME_RUNTIME_CACHE_ADDRESSES["first"]),
    ),
    ("name_cache_event_first_count", 0x00076328, (0x24050003,), (0x24050008,)),
    ("name_cache_event_first_index", 0x00076334, (0x24110003,), (0x24110008,)),
    # MAP2D's city/ward readers are intentionally absent.  Their stock
    # three-glyph stack builders append Japanese suffixes and one path writes
    # fixed `Full Map` words; widening those readers to eight corrupts saved
    # registers.  The MAP2D-owned draw wrapper consumes compact profile bytes
    # without entering those buffers instead.
    (
        "name_cache_first_ui_ab914",
        0x000AB914,
        (0x3C04003F, 0x24846CFE),
        _second_load_pointer_words(A0, NAME_RUNTIME_CACHE_ADDRESSES["first"]),
    ),
    ("name_cache_first_ui_ab920_count", 0x000AB920, (0x24050003,), (0x24050008,)),
)


# -- Name-entry assembly ----------------------------------------------------


def _build_name_label_draw_wrapper() -> AssembledCode:
    """Apply NAME-only VWF placement, then tail-call the stock glyph drawer.

    The stock descriptor loop owns ``s2`` as its pen and advances it by sixteen
    after every draw.  The wrapper therefore adds ``width - 16`` before the
    stock increment.  On the first glyph, selected labels replace the stock x
    with a generated centered start.  Occupation descriptors 11-16 also mirror
    Saturn on every glyph: the live row/column choice is yellow and the other
    five are white.  Other callers retain their live ``t0..t2`` color and
    acceptance arguments for ``0x9eea8``.
    """

    code = _Assembler(NAME_LABEL_DRAW_WRAPPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addiu(T9, RA, NAME_WIDTH_TABLE_ADDRESS - pc_address)

    code.addiu(V0, A2, -PACKED_RUNTIME_FIRST)
    code.sltiu(V1, V0, PACKED_WIDTH_COUNT)
    code.beq(V1, ZERO, "fallback_width")
    code.delay_nop()
    code.addu(V1, T9, V0)
    code.lbu(V1, 0, V1)
    code.beq(ZERO, ZERO, "width_ready")
    code.delay_nop()

    code.label("fallback_width")
    code.addiu(V1, ZERO, 16)

    code.label("width_ready")
    code.bne(S4, ZERO, "advance_pen")
    code.delay_nop()
    code.srl(T3, S1, 7)
    code.addiu(T4, T3, -11)
    code.sltiu(T5, T4, 6)
    code.beq(T5, ZERO, "occupation_color_ready")
    code.delay_nop()
    # The stock call's delay slot has made s0 = state + descriptor*128, while
    # s1 remains descriptor*128.  Recover the live NAME state without adding a
    # relocation or depending on the separately normalized global pointer.
    code.subu(T6, S0, S1)
    code.addiu(S6, ZERO, -1)
    code.lw(T5, 0x1C, T6)
    code.sll(T5, T5, 1)
    code.lw(T6, 0x18, T6)
    code.addu(T5, T5, T6)
    code.bne(T4, T5, "occupation_color_ready")
    code.delay_nop()
    code.lui(S6, NAME_OCCUPATION_HIGHLIGHT_COLOR >> 16)
    code.ori(S6, S6, NAME_OCCUPATION_HIGHLIGHT_COLOR & 0xFFFF)

    code.label("occupation_color_ready")
    # The stock loop reloads t0 from s6 before each later glyph, so changing
    # the saved descriptor color on glyph zero recolors the complete label.
    code.addu(T0, S6, ZERO)
    code.sltiu(T4, T3, NAME_DESCRIPTOR_COUNT)
    code.beq(T4, ZERO, "advance_pen")
    code.delay_nop()
    code.sll(T3, T3, 1)
    code.addiu(T4, RA, NAME_X_START_TABLE_ADDRESS - pc_address)
    code.addu(T4, T4, T3)
    code.lhu(T4, 0, T4)
    code.ori(T5, ZERO, 0xFFFF)
    code.beq(T4, T5, "advance_pen")
    code.delay_nop()
    code.addu(A0, T4, ZERO)
    code.addu(S2, T4, ZERO)

    code.label("advance_pen")
    code.addiu(V0, V1, -16)
    code.addu(S2, S2, V0)
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=0x0009EEA8,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_glyph_to_byte() -> AssembledCode:
    """Map translated glyphs to packed bytes, preserving packed finalizer input."""

    code = _Assembler(NAME_GLYPH_TO_BYTE_ADDRESS)
    code.addiu(V0, A0, -PACKED_FIRST)
    code.sltiu(V1, V0, PACKED_WIDTH_COUNT)
    code.beq(V1, ZERO, "runtime_glyph")
    code.delay_nop()
    code.addu(V0, A0, ZERO)
    code.jr(RA)
    code.delay_nop()

    code.label("runtime_glyph")
    code.addiu(V0, A0, -PACKED_RUNTIME_FIRST)
    code.sltiu(V1, V0, PACKED_WIDTH_COUNT)
    code.beq(V1, ZERO, "fallback")
    code.delay_nop()
    code.addiu(V0, V0, PACKED_FIRST)
    code.jr(RA)
    code.delay_nop()

    code.label("fallback")
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=0x0009EC08,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_byte_to_glyph() -> AssembledCode:
    """Restore packed translated name bytes, else use the stock table."""

    code = _Assembler(NAME_BYTE_TO_GLYPH_ADDRESS)
    code.addiu(V0, A0, -PACKED_FIRST)
    code.sltiu(V1, V0, PACKED_WIDTH_COUNT)
    code.beq(V1, ZERO, "fallback")
    code.delay_nop()
    code.addiu(V0, A0, PACKED_RUNTIME_BIAS)
    code.jr(RA)
    code.delay_nop()

    code.label("fallback")
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=0x0009EC3C,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_init_wrapper(source: NameEntryPatchSource) -> AssembledCode:
    """Clear the expanded state, seed Saturn defaults, and enter First."""

    code = _Assembler(NAME_INIT_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
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
        target_address=0x000C9E54,
    )
    code.addu(A0, S0, ZERO)
    code.jalr(T9)
    code.delay_nop()

    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0x00, S0)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.sw(T0, 0x128C, S0)
    code.addiu(T0, ZERO, -1)
    code.sw(T0, NAME_OCCUPATION_SELECTION_OFFSET, S0)
    code.sw(ZERO, NAME_LOGICAL_FIELD_OFFSET, S0)
    code.lw(T1, 0x08, SP)
    code.beq(T1, ZERO, "defaults")
    code.delay_nop()
    code.addiu(T0, ZERO, 2)
    code.sw(T0, NAME_LOGICAL_FIELD_OFFSET, S0)
    code.label("defaults")
    for field_index, text in (
        (3, source.default_city),
        (4, source.default_ward),
    ):
        for glyph_index, character in enumerate(text):
            code.addiu(T0, ZERO, _name_runtime_glyph(character))
            code.sw(
                T0,
                NAME_FIELD_BUFFER_BASE
                + field_index * NAME_FIELD_BUFFER_STRIDE
                + glyph_index * 4,
                S0,
            )

    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_prompt_wrapper() -> AssembledCode:
    """Map the sidecar field to five independent Saturn prompts."""

    descriptors = (1, 6, 7, 8, 9)
    code = _Assembler(NAME_PROMPT_WRAPPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(T9, 0, T9)
    code.lw(V0, 4, T9)
    code.bne(V0, ZERO, "rename")
    code.delay_nop()
    code.lw(V0, 0, T9)
    code.addiu(V1, ZERO, 3)
    code.beq(V0, V1, "occupation")
    code.delay_nop()
    code.lw(V0, NAME_LOGICAL_FIELD_OFFSET, T9)
    for field_index, descriptor in enumerate(descriptors):
        code.addiu(V1, ZERO, field_index)
        code.beq(V0, V1, f"field_{field_index}")
        code.delay_nop()
    code.beq(ZERO, ZERO, "tail")
    code.delay_nop()
    for field_index, descriptor in enumerate(descriptors):
        code.label(f"field_{field_index}")
        code.addiu(A0, ZERO, descriptor)
        code.beq(ZERO, ZERO, "tail")
        code.delay_nop()
    code.label("rename")
    code.addiu(A0, ZERO, 26)
    code.beq(ZERO, ZERO, "tail")
    code.delay_nop()
    code.label("occupation")
    code.addiu(A0, ZERO, 10)
    code.label("tail")
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=0x0009E1D4,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_echo_wrapper() -> AssembledCode:
    """Select one of five text rows, or the sixth occupation row."""

    code = _Assembler(NAME_ECHO_WRAPPER_ADDRESS)
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(T9, 0, T9)
    code.addiu(V0, ZERO, 1)
    code.beq(A0, V0, "text")
    code.delay_nop()
    code.addiu(V0, ZERO, 3)
    code.bne(A0, V0, "tail")
    code.delay_nop()
    code.addiu(A0, ZERO, NAME_OCCUPATION_BUFFER_INDEX)
    code.beq(ZERO, ZERO, "tail")
    code.delay_nop()
    code.label("text")
    code.lw(A0, NAME_LOGICAL_FIELD_OFFSET, T9)
    code.label("tail")
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=0x0009E86C,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_done_handler() -> AssembledCode:
    """Validate one eight-cell row and advance the Saturn field sequence."""

    code = _Assembler(NAME_DONE_HANDLER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.addu(S1, A0, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S2,
        RA,
        pc_address=pc_address,
        target_address=0x0009CE8C,
    )
    _load_pc_relative_target(
        code,
        S0,
        RA,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(S0, 0, S0)
    code.sll(T0, S1, 5)
    code.addu(T0, T0, S0)
    code.addiu(T0, T0, NAME_FIELD_BUFFER_BASE)
    code.addiu(T1, ZERO, NAME_FIELD_MAX)
    code.addiu(T3, ZERO, _name_runtime_glyph(" "))
    code.label("validate")
    code.lw(T2, 0, T0)
    code.beq(T2, ZERO, "next_cell")
    code.delay_nop()
    code.bne(T2, T3, "valid")
    code.delay_nop()
    code.label("next_cell")
    code.addiu(T0, T0, 4)
    code.addiu(T1, T1, -1)
    code.bne(T1, ZERO, "validate")
    code.delay_nop()
    code.addiu(A0, ZERO, NAME_SOUND_ERROR_INDEX)
    code.bal_address(NAME_DONE_SOUND_WRAPPER_ADDRESS)
    code.delay_nop()
    code.beq(ZERO, ZERO, "return_zero")
    code.delay_nop()

    code.label("valid")
    code.addiu(A0, ZERO, NAME_SOUND_ACCEPT_INDEX)
    code.bal_address(NAME_DONE_SOUND_WRAPPER_ADDRESS)
    code.delay_nop()
    code.lw(T0, 4, S0)
    code.bne(T0, ZERO, "rename")
    code.delay_nop()
    code.sltiu(T0, S1, 4)
    code.beq(T0, ZERO, "occupation")
    code.delay_nop()
    code.addiu(S1, S1, 1)
    code.jalr(S2)
    code.delay_nop()
    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0, S0)
    code.sw(T0, 0x1C, S0)
    code.sw(S1, NAME_LOGICAL_FIELD_OFFSET, S0)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.sw(T0, 0x128C, S0)
    code.addiu(T0, ZERO, 3)
    code.sw(T0, 0x18, S0)
    code.beq(ZERO, ZERO, "return_zero")
    code.delay_nop()

    code.label("occupation")
    code.jalr(S2)
    code.delay_nop()
    code.addiu(T0, ZERO, 3)
    code.sw(T0, 0, S0)
    code.addiu(T0, ZERO, NAME_OCCUPATION_BUFFER_INDEX)
    code.sw(T0, NAME_LOGICAL_FIELD_OFFSET, S0)
    code.sw(T0, 8, S0)
    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0x10, S0)
    code.sw(ZERO, 0x128C, S0)
    code.beq(ZERO, ZERO, "return_zero")
    code.delay_nop()

    code.label("rename")
    code.addiu(T0, ZERO, 5)
    code.sw(T0, 0, S0)
    code.addiu(T0, ZERO, 6)
    code.sw(T0, 8, S0)

    code.label("return_zero")
    code.addu(V0, ZERO, ZERO)
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_select_wrapper() -> AssembledCode:
    """Translate one native grid glyph to the staged high-glyph page."""

    code = _Assembler(NAME_SELECT_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S0, RA, ZERO)
    _load_pc_relative_target(
        code,
        S1,
        S0,
        pc_address=pc_address,
        target_address=0x0009E57C,
    )
    code.jalr(S1)
    code.delay_nop()
    code.beq(V0, ZERO, "return")
    code.delay_nop()
    code.ori(T0, ZERO, NAME_GRID_DONE)
    code.beq(V0, T0, "return")
    code.delay_nop()
    code.addiu(T0, V0, -PACKED_RUNTIME_FIRST)
    code.sltiu(T1, T0, PACKED_WIDTH_COUNT)
    code.bne(T1, ZERO, "return")
    code.delay_nop()
    for low_start, count in ((0xCB, 10), (0xDC, 26), (0xFC, 26)):
        label = f"range_{low_start:x}"
        code.addiu(T0, V0, -low_start)
        code.sltiu(T1, T0, count)
        code.bne(T1, ZERO, label)
        code.delay_nop()
    _load_pc_relative_target(
        code,
        T0,
        S0,
        pc_address=pc_address,
        target_address=NAME_GRID_PUNCTUATION_TABLE_ADDRESS,
    )
    code.addiu(T1, ZERO, len(NAME_GRID_LOW_PUNCTUATION))
    code.label("punctuation")
    code.lhu(T2, 0, T0)
    code.beq(T2, V0, "punctuation_found")
    code.delay_nop()
    code.addiu(T0, T0, 4)
    code.addiu(T1, T1, -1)
    code.bne(T1, ZERO, "punctuation")
    code.delay_nop()
    code.addiu(V0, ZERO, -1)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()
    for low_start, _count in ((0xCB, 10), (0xDC, 26), (0xFC, 26)):
        code.label(f"range_{low_start:x}")
        code.addiu(V0, V0, 0x1D55)
        code.beq(ZERO, ZERO, "return")
        code.delay_nop()
    code.label("punctuation_found")
    code.lhu(V0, 2, T0)
    code.label("return")
    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_button_wrapper() -> AssembledCode:
    """Clear on Cross backspace and make Start park the cursor on Done."""

    code = _Assembler(NAME_BUTTON_HELPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S0, RA, ZERO)
    _load_pc_relative_target(
        code,
        S1,
        S0,
        pc_address=pc_address,
        target_address=0x00000C84,
    )
    _load_pc_relative_target(
        code,
        S2,
        S0,
        pc_address=pc_address,
        target_address=0x0009E6C4,
    )
    code.jalr(S1)
    code.delay_nop()
    code.beq(V0, ZERO, "start")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T0,
        S0,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(T0, 0, T0)
    code.lw(T1, 0x1288, T0)
    code.beq(T1, ZERO, "cross_return")
    code.delay_nop()
    code.lw(T2, NAME_LOGICAL_FIELD_OFFSET, T0)
    code.sll(T2, T2, 5)
    code.sll(T3, T1, 2)
    code.addu(T2, T2, T3)
    code.addu(T2, T2, T0)
    code.sw(ZERO, NAME_FIELD_BUFFER_BASE - 4, T2)
    code.label("cross_return")
    code.addiu(V0, ZERO, 1)
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()

    code.label("start")
    code.addiu(A0, ZERO, 8)
    code.jalr(S1)
    code.delay_nop()
    code.beq(V0, ZERO, "return_zero")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T9,
        S0,
        pc_address=pc_address,
        target_address=0x000A0028,
    )
    code.addiu(A0, ZERO, 2)
    code.jalr(T9)
    code.delay_nop()
    code.ori(A0, ZERO, NAME_GRID_DONE)
    code.jalr(S2)
    code.delay_nop()
    code.beq(ZERO, ZERO, "return_zero")
    code.delay_nop()
    code.label("return_zero")
    code.addu(V0, ZERO, ZERO)
    code.label("return")
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_done_sound_wrapper() -> AssembledCode:
    """Suppress pre-validation Done audio, else tail-call PSP's SE dispatcher."""

    code = _Assembler(NAME_DONE_SOUND_WRAPPER_ADDRESS)
    code.ori(T0, ZERO, NAME_GRID_DONE)
    code.bne(S0, T0, "play")
    code.delay_nop()
    code.addiu(T0, A0, -NAME_SOUND_ACCEPT_INDEX)
    code.bne(T0, ZERO, "play")
    code.delay_nop()
    code.jr(RA)
    code.delay_nop()

    code.label("play")
    code.addu(T8, RA, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        T9,
        RA,
        pc_address=pc_address,
        target_address=NAME_SOUND_DISPATCH_ADDRESS,
    )
    code.addu(RA, T8, ZERO)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _emit_name_call(
    code: _Assembler,
    target_register: int,
    *,
    selector: int,
    x: int,
    y: int,
    color: int,
) -> None:
    code.addiu(A0, ZERO, selector)
    code.addiu(A1, ZERO, x)
    code.addiu(A2, ZERO, y)
    code.addiu(A3, ZERO, color)
    code.jalr(target_register)
    code.delay_nop()


def _build_name_confirm_wrapper() -> AssembledCode:
    """Draw Saturn's grouped First+Last, Code, City+Ward confirmation."""

    code = _Assembler(NAME_CONFIRM_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.sw(S3, 0x0C, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S3, RA, ZERO)
    _load_pc_relative_target(
        code,
        S1,
        S3,
        pc_address=pc_address,
        target_address=0x0009E1D4,
    )
    _load_pc_relative_target(
        code,
        S2,
        S3,
        pc_address=pc_address,
        target_address=0x0009E86C,
    )
    _load_pc_relative_target(
        code,
        S0,
        S3,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(S0, 0, S0)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.sw(T0, 0x128C, S0)
    for field_index, x, y in (
        (0, 0x58, 0x28),
        (1, 0xF8, 0x28),
        (2, 0x58, 0x48),
        (3, 0x58, 0x68),
        (4, 0xF8, 0x68),
    ):
        _emit_name_call(code, S2, selector=field_index, x=x, y=y, color=0)
    _emit_name_call(code, S1, selector=10, x=0x58, y=0x88, color=-1)
    code.sw(ZERO, 0x128C, S0)
    _emit_name_call(
        code,
        S2,
        selector=NAME_OCCUPATION_BUFFER_INDEX,
        x=0xF8,
        y=0x88,
        color=0,
    )
    _emit_name_call(code, S1, selector=17, x=0x58, y=0xD8, color=-1)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.sw(T0, 0x128C, S0)
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.lw(S3, 0x0C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_commit_wrapper() -> AssembledCode:
    """Encode five staged rows into the unchanged 0x28-byte profile ABI."""

    code = _Assembler(NAME_COMMIT_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.sw(S3, 0x0C, SP)
    code.sw(S4, 0x08, SP)
    code.addu(S0, A1, ZERO)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S4, RA, ZERO)
    _load_pc_relative_target(
        code,
        S1,
        S4,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S2,
        S4,
        pc_address=pc_address,
        target_address=NAME_CACHE_REBUILD_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S3,
        S4,
        pc_address=pc_address,
        target_address=0x0009EC70,
    )
    code.addiu(S0, S0, NAME_FIELD_BUFFER_BASE)
    code.addiu(S4, ZERO, NAME_FIELD_COUNT)
    code.label("field")
    code.addiu(T4, ZERO, NAME_FIELD_MAX)
    code.addiu(T5, S0, (NAME_FIELD_MAX - 1) * 4)
    code.addiu(T3, ZERO, _name_runtime_glyph(" "))
    code.label("trim")
    code.lw(T1, 0, T5)
    code.beq(T1, ZERO, "trim_cell")
    code.delay_nop()
    code.bne(T1, T3, "trim_done")
    code.delay_nop()
    code.label("trim_cell")
    code.addiu(T4, T4, -1)
    code.addiu(T5, T5, -4)
    code.bne(T4, ZERO, "trim")
    code.delay_nop()
    code.label("trim_done")
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.label("glyph")
    code.beq(T4, ZERO, "zero")
    code.delay_nop()
    code.addiu(T4, T4, -1)
    code.lw(T1, 0, S0)
    code.beq(T1, ZERO, "interior_space")
    code.delay_nop()
    code.addiu(T2, T1, -PACKED_RUNTIME_FIRST)
    code.sltiu(T3, T2, PACKED_WIDTH_COUNT)
    code.beq(T3, ZERO, "zero")
    code.delay_nop()
    code.addiu(T2, T2, PACKED_FIRST)
    code.sb(T2, 0, S1)
    code.beq(ZERO, ZERO, "advance")
    code.delay_nop()
    code.label("interior_space")
    code.addiu(T2, ZERO, PACKED_LAST)
    code.sb(T2, 0, S1)
    code.beq(ZERO, ZERO, "advance")
    code.delay_nop()
    code.label("zero")
    code.sb(ZERO, 0, S1)
    code.label("advance")
    code.addiu(S0, S0, 4)
    code.addiu(S1, S1, 1)
    code.addiu(T0, T0, -1)
    code.bne(T0, ZERO, "glyph")
    code.delay_nop()
    code.addiu(S4, S4, -1)
    code.bne(S4, ZERO, "field")
    code.delay_nop()
    code.jalr(S2)
    code.delay_nop()
    code.jalr(S3)
    code.delay_nop()
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.lw(S3, 0x0C, SP)
    code.lw(S4, 0x08, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_cache_rebuild() -> AssembledCode:
    """Decode compact profile bytes into persistent high-glyph rows."""

    code = _Assembler(NAME_CACHE_REBUILD_ADDRESS)
    code.addiu(SP, SP, -0x20)
    code.sw(RA, 0x1C, SP)
    code.sw(S0, 0x18, SP)
    code.sw(S1, 0x14, SP)
    code.sw(S2, 0x10, SP)
    code.sw(S3, 0x0C, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code,
        S3,
        RA,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    _load_pc_relative_target(
        code,
        S1,
        RA,
        pc_address=pc_address,
        target_address=NAME_RUNTIME_CACHE_ADDRESS,
    )
    code.addiu(S0, S3, 8)  # Last is the first decoded row.
    code.addu(S2, ZERO, ZERO)
    code.label("row")
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.label("byte")
    code.lbu(T1, 0, S0)
    code.addiu(T2, T1, -PACKED_FIRST)
    code.sltiu(T3, T2, PACKED_WIDTH_COUNT)
    code.beq(T3, ZERO, "invalid")
    code.delay_nop()
    code.addiu(T1, T1, PACKED_RUNTIME_BIAS)
    code.beq(ZERO, ZERO, "store")
    code.delay_nop()
    code.label("invalid")
    code.addu(T1, ZERO, ZERO)
    code.label("store")
    code.sh(T1, 0, S1)
    code.addiu(S0, S0, 1)
    code.addiu(S1, S1, 2)
    code.addiu(T0, T0, -1)
    code.bne(T0, ZERO, "byte")
    code.delay_nop()
    code.addiu(S2, S2, 1)
    code.addiu(T0, ZERO, 1)
    code.beq(S2, T0, "first")
    code.delay_nop()
    code.addiu(T0, ZERO, 2)
    code.beq(S2, T0, "code")
    code.delay_nop()
    code.sltiu(T0, S2, NAME_FIELD_COUNT)
    code.bne(T0, ZERO, "row")
    code.delay_nop()
    code.addiu(S0, S3, NAME_PROFILE_FIELD_OFFSETS["codename"])
    code.addiu(S1, S3, NAME_PROFILE_CODENAME_MIRROR_OFFSET)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.label("mirror")
    code.lbu(T1, 0, S0)
    code.sb(T1, 0, S1)
    code.addiu(S0, S0, 1)
    code.addiu(S1, S1, 1)
    code.addiu(T0, T0, -1)
    code.bne(T0, ZERO, "mirror")
    code.delay_nop()
    code.beq(ZERO, ZERO, "return")
    code.delay_nop()
    code.label("first")
    code.addu(S0, S3, ZERO)
    code.beq(ZERO, ZERO, "row")
    code.delay_nop()
    code.label("code")
    code.addiu(S0, S3, NAME_PROFILE_FIELD_OFFSETS["codename"])
    code.beq(ZERO, ZERO, "row")
    code.delay_nop()
    code.label("return")
    code.lw(RA, 0x1C, SP)
    code.lw(S0, 0x18, SP)
    code.lw(S1, 0x14, SP)
    code.lw(S2, 0x10, SP)
    code.lw(S3, 0x0C, SP)
    code.addiu(SP, SP, 0x20)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_load_wrapper() -> AssembledCode:
    """Run the stock load finalizer, then rebuild persistent decoded names."""

    code = _Assembler(NAME_LOAD_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    _load_pc_relative_target(
        code, S0, RA, pc_address=pc_address, target_address=0x0000C430
    )
    _load_pc_relative_target(
        code,
        S1,
        RA,
        pc_address=pc_address,
        target_address=NAME_CACHE_REBUILD_ADDRESS,
    )
    code.jalr(S0)
    code.delay_nop()
    code.jalr(S1)
    code.delay_nop()
    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_new_profile_wrapper() -> AssembledCode:
    """Retire stock Japanese defaults after profile construction."""

    code = _Assembler(NAME_NEW_PROFILE_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S0, RA, ZERO)
    _load_pc_relative_target(
        code,
        T0,
        S0,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    code.addiu(T1, ZERO, 10)
    code.label("zero_names")
    code.sw(ZERO, 0, T0)
    code.addiu(T0, T0, 4)
    code.addiu(T1, T1, -1)
    code.bne(T1, ZERO, "zero_names")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        S1,
        S0,
        pc_address=pc_address,
        target_address=NAME_CACHE_REBUILD_ADDRESS,
    )
    code.jalr(S1)
    code.delay_nop()
    _load_pc_relative_target(
        code,
        T9,
        S0,
        pc_address=pc_address,
        target_address=0x000748E0,
    )
    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


def _build_name_reset_wrapper() -> AssembledCode:
    """Restart First or Codename after confirmation NO, preserving buffers."""

    code = _Assembler(NAME_RESET_WRAPPER_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S1, RA, ZERO)
    _load_pc_relative_target(
        code, S0, S1, pc_address=pc_address, target_address=0x0009CE8C
    )
    code.jalr(S0)
    code.delay_nop()
    _load_pc_relative_target(
        code,
        S0,
        S1,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(S0, 0, S0)
    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0, S0)
    code.addiu(T0, ZERO, NAME_FIELD_MAX)
    code.sw(T0, 0x128C, S0)
    code.addiu(T0, ZERO, 1)
    code.sw(T0, 0x1C, S0)
    code.addiu(T0, ZERO, 3)
    code.sw(T0, 0x18, S0)
    code.lw(T0, 4, S0)
    code.beq(T0, ZERO, "first")
    code.delay_nop()
    code.addiu(T0, ZERO, 2)
    code.beq(ZERO, ZERO, "store")
    code.delay_nop()
    code.label("first")
    code.addu(T0, ZERO, ZERO)
    code.label("store")
    code.sw(T0, NAME_LOGICAL_FIELD_OFFSET, S0)
    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(RA)
    code.delay_nop()
    return code.finish()


def _build_name_rename_sync() -> AssembledCode:
    """Mirror a renamed Codename into compact storage/cache, then continue."""

    code = _Assembler(NAME_RENAME_SYNC_ADDRESS)
    code.addiu(SP, SP, -0x10)
    code.sw(RA, 0x0C, SP)
    code.sw(S0, 0x08, SP)
    code.sw(S1, 0x04, SP)
    code.bal("pc")
    code.delay_nop()
    code.label("pc")
    pc_address = code.cursor
    code.addu(S0, RA, ZERO)
    _load_pc_relative_target(
        code,
        T0,
        S0,
        pc_address=pc_address,
        target_address=NAME_PROFILE_ADDRESS,
    )
    code.addiu(T1, T0, NAME_PROFILE_CODENAME_MIRROR_OFFSET)
    code.addiu(T2, T0, NAME_PROFILE_FIELD_OFFSETS["codename"])
    code.addiu(T4, ZERO, NAME_FIELD_MAX)
    code.addiu(T5, T1, NAME_FIELD_MAX - 1)
    code.label("trim")
    code.lbu(V0, 0, T5)
    code.beq(V0, ZERO, "trim_byte")
    code.delay_nop()
    code.addiu(T3, ZERO, PACKED_LAST)
    code.bne(V0, T3, "trim_done")
    code.delay_nop()
    code.label("trim_byte")
    code.addiu(T4, T4, -1)
    code.addiu(T5, T5, -1)
    code.bne(T4, ZERO, "trim")
    code.delay_nop()
    code.label("trim_done")
    code.addiu(T3, ZERO, NAME_FIELD_MAX)
    code.label("copy")
    code.beq(T4, ZERO, "copy_zero")
    code.delay_nop()
    code.addiu(T4, T4, -1)
    code.lbu(V0, 0, T1)
    code.bne(V0, ZERO, "copy_store")
    code.delay_nop()
    code.addiu(V0, ZERO, PACKED_LAST)
    code.beq(ZERO, ZERO, "copy_store")
    code.delay_nop()
    code.label("copy_zero")
    code.addu(V0, ZERO, ZERO)
    code.label("copy_store")
    code.sb(V0, 0, T2)
    code.addiu(T1, T1, 1)
    code.addiu(T2, T2, 1)
    code.addiu(T3, T3, -1)
    code.bne(T3, ZERO, "copy")
    code.delay_nop()
    _load_pc_relative_target(
        code,
        S1,
        S0,
        pc_address=pc_address,
        target_address=NAME_CACHE_REBUILD_ADDRESS,
    )
    code.jalr(S1)
    code.delay_nop()
    _load_pc_relative_target(
        code,
        V1,
        S0,
        pc_address=pc_address,
        target_address=NAME_STATE_POINTER_ADDRESS,
    )
    code.lw(V1, 0, V1)
    code.addiu(V0, ZERO, 0x32)
    _load_pc_relative_target(
        code,
        T9,
        S0,
        pc_address=pc_address,
        target_address=0x0009D878,
    )
    code.lw(RA, 0x0C, SP)
    code.lw(S0, 0x08, SP)
    code.lw(S1, 0x04, SP)
    code.addiu(SP, SP, 0x10)
    code.jr(T9)
    code.delay_nop()
    return code.finish()


# -- Name-entry patch composition ------------------------------------------


def _validate_name_entry_source(source: NameEntryPatchSource) -> None:
    if not isinstance(source, NameEntryPatchSource):
        raise TypeError("PSP name-entry source must be NameEntryPatchSource")
    if not isinstance(source.grids, tuple) or len(source.grids) != 3:
        raise ValueError("PSP name entry requires exactly three grid pages")
    for page_index, page in enumerate(source.grids):
        if not isinstance(page, tuple) or len(page) != 2:
            raise ValueError(
                f"PSP name-entry grid {page_index} must contain exactly two rows"
            )
        for row in page:
            if not isinstance(row, str) or len(row) > 13:
                raise ValueError(
                    "PSP name-entry authored rows must be strings of at most 13 cells"
                )
            for character in row:
                _packed_storage_index(character)

    for key, value in (
        ("default_city", source.default_city),
        ("default_ward", source.default_ward),
    ):
        if not isinstance(value, str) or not 1 <= len(value) <= NAME_FIELD_MAX:
            raise ValueError(
                f"PSP name-entry {key} must contain 1..{NAME_FIELD_MAX} characters"
            )
        for character in value:
            _packed_storage_index(character)

    if (
        not isinstance(source.descriptor_labels, tuple)
        or len(source.descriptor_labels) != NAME_DESCRIPTOR_COUNT
    ):
        raise ValueError(
            f"PSP name entry requires {NAME_DESCRIPTOR_COUNT} descriptor labels"
        )
    literal_labels = dict(NAME_DESCRIPTOR_LITERAL_LABELS)
    for index, label in enumerate(source.descriptor_labels):
        if index in NAME_DESCRIPTOR_PRESERVE_INDICES:
            if label is not None:
                raise ValueError(
                    f"PSP name descriptor {index} is stock-owned and must be None"
                )
            continue
        if index in literal_labels:
            if label != literal_labels[index]:
                raise ValueError(
                    f"PSP name descriptor {index} must be {literal_labels[index]!r}"
                )
            continue
        if index in NAME_DESCRIPTOR_SUPPRESS_INDICES:
            if label != "":
                raise ValueError(
                    f"PSP name descriptor {index} must be explicitly suppressed"
                )
            continue
        if not isinstance(label, str) or not label:
            raise ValueError(
                f"PSP name descriptor {index} requires a nonempty ASCII label"
            )
        for character in label:
            _packed_storage_index(character)


def _name_runtime_glyph(character: str) -> int:
    return PACKED_RUNTIME_FIRST + _packed_storage_index(character)


def _name_grid_glyph(character: str) -> int:
    code = ord(character)
    if character in NAME_GRID_LOW_PUNCTUATION:
        return NAME_GRID_LOW_PUNCTUATION[character]
    if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A:
        return code + 0x9B
    raise ValueError(f"character has no PSP NAME grid glyph: {character!r}")


def _build_name_grid(rows: tuple[str, str]) -> bytes:
    # Mirror saturn/engine/script/name/data.py:build_grid exactly inside the
    # active 4x13 rectangle. Its unused cells are selectable zero blanks;
    # 0x61 is only the PSP navigator guard outside that Saturn rectangle.
    cells = [NAME_GRID_SENTINEL] * NAME_GRID_WORD_COUNT
    for row_index in range(1, 5):
        for column_index in range(3, 16):
            cells[row_index * NAME_GRID_COLUMNS + column_index] = 0
    for row_index, row in enumerate(rows, 1):
        for column_index, character in enumerate(row, 3):
            cells[row_index * NAME_GRID_COLUMNS + column_index] = _name_grid_glyph(
                character
            )
    cells[4 * NAME_GRID_COLUMNS + 15] = NAME_GRID_DONE
    return struct.pack(f"<{NAME_GRID_WORD_COUNT}H", *cells)


def _encode_name_label(label: str) -> bytes:
    return struct.pack(
        f"<{len(label)}H", *(_name_runtime_glyph(character) for character in label)
    )


def _build_name_label_writes(
    source: NameEntryPatchSource,
) -> tuple[tuple[PatchWrite, ...], bytes]:
    blob = bytearray()
    offsets: dict[bytes, int] = {}
    descriptor_writes: list[PatchWrite] = []
    for index, label in enumerate(source.descriptor_labels):
        if index in NAME_DESCRIPTOR_PRESERVE_INDICES:
            continue
        assert label is not None
        if index in NAME_DESCRIPTOR_SUPPRESS_INDICES:
            descriptor_writes.append(
                PatchWrite(
                    f"name_label_descriptor_{index:02d}",
                    NAME_DESCRIPTOR_TABLE_ADDRESS + index * 8 + 4,
                    struct.pack("<I", 0),
                )
            )
            continue
        encoded = _encode_name_label(label)
        if encoded not in offsets:
            offsets[encoded] = len(blob)
            blob.extend(encoded)
        address = NAME_LABEL_BLOB_ADDRESS + offsets[encoded]
        raw_pointer = address - NAME_DATA_SEGMENT_ADDRESS
        descriptor_writes.append(
            PatchWrite(
                f"name_label_descriptor_{index:02d}",
                NAME_DESCRIPTOR_TABLE_ADDRESS + index * 8,
                struct.pack("<II", raw_pointer, len(label)),
            )
        )
    if len(blob) > NAME_LABEL_BLOB_STATIC_MAX_SIZE:
        raise ValueError(
            f"PSP name-entry label blob is {len(blob)} bytes; "
            f"maximum is {NAME_LABEL_BLOB_STATIC_MAX_SIZE}"
        )
    punctuation = bytearray()
    for character, low_glyph in NAME_GRID_LOW_PUNCTUATION.items():
        punctuation.extend(
            struct.pack("<HH", low_glyph, _name_runtime_glyph(character))
        )
    if len(punctuation) > NAME_LABEL_BLOB_MAX_SIZE - 0x3D0:
        raise ValueError("PSP NAME punctuation table exceeds the retired label pool")
    compiled_blob = bytearray(NAME_LABEL_BLOB_MAX_SIZE)
    compiled_blob[: len(blob)] = blob
    compiled_blob[0x3D0 : 0x3D0 + len(punctuation)] = punctuation
    return (
        tuple(descriptor_writes),
        bytes(compiled_blob),
    )


_NAME_X_START_CENTERS = {
    2: 144,
    3: 240,
    4: 336,
    5: 144,
    11: 184,
    12: 296,
    13: 184,
    14: 296,
    15: 184,
    16: 296,
    18: 304,
    19: 360,
}


def _build_name_x_start_table(
    widths: bytes,
    source: NameEntryPatchSource,
) -> bytes:
    starts = [-1] * NAME_DESCRIPTOR_COUNT
    for index, center in _NAME_X_START_CENTERS.items():
        label = source.descriptor_labels[index]
        assert label is not None
        width = sum(widths[_packed_storage_index(character)] for character in label)
        start = center - width // 2
        if not 0 <= start <= 0x7FFF:
            raise ValueError(
                f"PSP name descriptor {index} cannot be centered on-screen"
            )
        starts[index] = start
    return struct.pack(f"<{NAME_DESCRIPTOR_COUNT}h", *starts)


def build_name_entry_patch(
    widths: Iterable[int],
    source: NameEntryPatchSource,
) -> NameEntryPatch:
    """Build the five-field, eight-cell Saturn NAME contract on PSP.

    The native grid remains a low-glyph display surface.  Selected cells enter
    five independent high-glyph staging rows, while compact profile bytes and a
    persistent decoded cache preserve the unchanged save extent and satisfy
    every EVENT/menu reader after the NAME heap object is released.
    """

    width_table = _validate_widths(widths)
    _validate_name_entry_source(source)
    label_draw_wrapper = _build_name_label_draw_wrapper()
    glyph_to_byte = _build_name_glyph_to_byte()
    byte_to_glyph = _build_name_byte_to_glyph()
    runtime_helpers = (
        _build_name_init_wrapper(source),
        _build_name_prompt_wrapper(),
        _build_name_echo_wrapper(),
        _build_name_done_handler(),
        _build_name_select_wrapper(),
        _build_name_button_wrapper(),
        _build_name_done_sound_wrapper(),
        _build_name_confirm_wrapper(),
        _build_name_commit_wrapper(),
        _build_name_cache_rebuild(),
        _build_name_load_wrapper(),
        _build_name_new_profile_wrapper(),
        _build_name_reset_wrapper(),
        _build_name_rename_sync(),
    )
    x_starts = _build_name_x_start_table(width_table, source)
    descriptor_writes, label_blob = _build_name_label_writes(source)
    upper_grid = _build_name_grid(source.grids[0])
    lower_grid = _build_name_grid(source.grids[1])
    symbol_grid = _build_name_grid(source.grids[2])

    if label_draw_wrapper.end_address > NAME_GLYPH_TO_BYTE_ADDRESS:
        raise ValueError("PSP NAME label wrapper exceeds its cave partition")
    if glyph_to_byte.end_address > NAME_BYTE_TO_GLYPH_ADDRESS:
        raise ValueError("PSP NAME glyph-to-byte wrapper exceeds its cave partition")
    if byte_to_glyph.end_address > NAME_WIDTH_TABLE_ADDRESS:
        raise ValueError("PSP NAME byte-to-glyph wrapper exceeds its cave partition")
    if NAME_WIDTH_TABLE_ADDRESS + len(width_table) > NAME_X_START_TABLE_ADDRESS:
        raise ValueError("PSP NAME widths overlap the centered-x table")
    if NAME_X_START_TABLE_ADDRESS + len(x_starts) > NAME_INIT_WRAPPER_ADDRESS:
        raise ValueError("PSP NAME centered-x table overlaps controller helpers")
    helper_order = tuple(sorted(runtime_helpers, key=lambda helper: helper.address))
    for left, right in zip(helper_order, helper_order[1:]):
        if left.end_address > right.address:
            raise ValueError(
                "PSP NAME controller helpers overlap: "
                f"{left.address:#x}..{left.end_address:#x} and {right.address:#x}"
            )
    if helper_order[-1].end_address > EVENT_OPTION_RESET_WRAPPER_ADDRESS:
        raise ValueError("PSP NAME controller helpers exceed their cave partition")

    hook_writes = tuple(
        PatchWrite(name, address, _word_bytes(replacement_word))
        for name, address, _source_word, replacement_word in NAME_HOOK_CONTRACTS
    )
    instruction_writes = tuple(
        PatchWrite(name, address, _word_bytes(*replacement_words))
        for name, address, _source_words, replacement_words in (
            NAME_INSTRUCTION_PATCH_CONTRACTS
        )
        if replacement_words != _source_words
    )
    address_default_writes = tuple(
        PatchWrite(name, address, _word_bytes(replacement_word))
        for name, address, _source_word, replacement_word in (
            NAME_ADDRESS_DEFAULT_STORE_CONTRACTS
        )
    )
    helper_writes = tuple(
        PatchWrite(
            {
                NAME_INIT_WRAPPER_ADDRESS: "name_init_wrapper",
                NAME_PROMPT_WRAPPER_ADDRESS: "name_prompt_wrapper",
                NAME_ECHO_WRAPPER_ADDRESS: "name_echo_wrapper",
                NAME_DONE_HANDLER_ADDRESS: "name_done_handler",
                NAME_SELECT_WRAPPER_ADDRESS: "name_select_wrapper",
                NAME_BUTTON_HELPER_ADDRESS: "name_button_wrapper",
                NAME_DONE_SOUND_WRAPPER_ADDRESS: "name_done_sound_wrapper",
                NAME_CONFIRM_WRAPPER_ADDRESS: "name_confirm_wrapper",
                NAME_COMMIT_WRAPPER_ADDRESS: "name_commit_wrapper",
                NAME_CACHE_REBUILD_ADDRESS: "name_cache_rebuild",
                NAME_LOAD_WRAPPER_ADDRESS: "name_load_wrapper",
                NAME_NEW_PROFILE_WRAPPER_ADDRESS: "name_new_profile_wrapper",
                NAME_RESET_WRAPPER_ADDRESS: "name_reset_wrapper",
                NAME_RENAME_SYNC_ADDRESS: "name_rename_sync",
            }[helper.address],
            helper.address,
            helper.data,
        )
        for helper in runtime_helpers
    )
    writes = (
        hook_writes
        + instruction_writes
        + (
            *address_default_writes,
            *descriptor_writes,
            PatchWrite(
                "name_echo_eight_x_pointers",
                NAME_ECHO_X_POINTER_TABLE_ADDRESS,
                struct.pack("<3I", *(NAME_ECHO_EIGHT_X_RAW_ADDRESS,) * 3),
            ),
            PatchWrite(
                "name_grid0_count",
                NAME_GRID0_COUNT_ADDRESS,
                struct.pack("<I", NAME_GRID_WORD_COUNT),
            ),
            PatchWrite(
                "name_grid_upper_primary", NAME_GRID_PRIMARY_ADDRESS, upper_grid
            ),
            PatchWrite("name_grid_lower", NAME_GRID_LOWER_ADDRESS, lower_grid),
            PatchWrite("name_grid_symbol", NAME_GRID_SYMBOL_ADDRESS, symbol_grid),
            PatchWrite(
                "name_grid_upper_secondary",
                NAME_GRID_SECONDARY_UPPER_ADDRESS,
                upper_grid,
            ),
            PatchWrite("name_label_blob", NAME_LABEL_BLOB_ADDRESS, label_blob),
            PatchWrite(
                "name_label_draw_wrapper",
                label_draw_wrapper.address,
                label_draw_wrapper.data,
            ),
            PatchWrite("name_glyph_to_byte", glyph_to_byte.address, glyph_to_byte.data),
            PatchWrite("name_byte_to_glyph", byte_to_glyph.address, byte_to_glyph.data),
            PatchWrite("name_widths", NAME_WIDTH_TABLE_ADDRESS, width_table),
            PatchWrite("name_x_starts", NAME_X_START_TABLE_ADDRESS, x_starts),
            *helper_writes,
        )
    )
    if len({write.name for write in writes}) != len(writes):
        raise ValueError("PSP NAME patch contains duplicate write names")
    ordered = tuple(sorted(writes, key=lambda write: write.address))
    for left_write, right_write in zip(ordered, ordered[1:]):
        if left_write.end_address > right_write.address:
            raise ValueError(
                f"PSP NAME writes overlap: {left_write.name} and {right_write.name}"
            )
    return NameEntryPatch(
        label_draw_wrapper,
        glyph_to_byte,
        byte_to_glyph,
        runtime_helpers,
        writes,
    )


__all__ = [
    "NAME_ADDRESS_DEFAULT_STORE_CONTRACTS",
    "NAME_ADDRESS_LIMIT_ADDRESS",
    "NAME_BYTE_TO_GLYPH_ADDRESS",
    "NAME_BYTE_TO_GLYPH_CALL_ADDRESS",
    "NAME_CACHE_REBUILD_ADDRESS",
    "NAME_CODENAME_LIMIT_ADDRESS",
    "NAME_DESCRIPTOR_COUNT",
    "NAME_DESCRIPTOR_LITERAL_LABELS",
    "NAME_DESCRIPTOR_PRESERVE_INDICES",
    "NAME_DESCRIPTOR_SUPPRESS_INDICES",
    "NAME_DESCRIPTOR_TABLE_ADDRESS",
    "NAME_DONE_SOUND_WRAPPER_ADDRESS",
    "NAME_ECHO_EIGHT_X_ADDRESS",
    "NAME_ECHO_EIGHT_X_RAW_ADDRESS",
    "NAME_ECHO_X_POINTER_TABLE_ADDRESS",
    "NAME_FIELD_LIMITS",
    "NAME_FIELD_LIMIT_SOURCE_CONTRACTS",
    "NAME_GLYPH_TO_BYTE_ADDRESS",
    "NAME_GLYPH_TO_BYTE_CALL_ADDRESSES",
    "NAME_GRID0_COUNT_ADDRESS",
    "NAME_GRID_COLUMNS",
    "NAME_GRID_DONE",
    "NAME_GRID_LOWER_ADDRESS",
    "NAME_GRID_LOW_PUNCTUATION",
    "NAME_GRID_PRIMARY_ADDRESS",
    "NAME_GRID_ROWS",
    "NAME_GRID_SECONDARY_UPPER_ADDRESS",
    "NAME_GRID_SENTINEL",
    "NAME_GRID_SYMBOL_ADDRESS",
    "NAME_GRID_WORD_COUNT",
    "NAME_HOOK_CONTRACTS",
    "NAME_INSTRUCTION_PATCH_CONTRACTS",
    "NAME_LABEL_BLOB_ADDRESS",
    "NAME_LABEL_BLOB_MAX_SIZE",
    "NAME_LABEL_BLOB_STATIC_MAX_SIZE",
    "NAME_LABEL_DRAW_CALL_ADDRESS",
    "NAME_LABEL_DRAW_WRAPPER_ADDRESS",
    "NAME_REAL_NAME_LIMIT_ADDRESS",
    "NAME_RENAME_CODENAME_LIMIT_ADDRESS",
    "NAME_RUNTIME_CACHE_ADDRESS",
    "NAME_RUNTIME_CACHE_ADDRESSES",
    "NAME_RUNTIME_CACHE_RELOCATION_ADDENDS",
    "NAME_SELECT_WRAPPER_ADDRESS",
    "NAME_SOUND_ACCEPT_INDEX",
    "NAME_SOUND_DISPATCH_ADDRESS",
    "NAME_SOUND_ERROR_INDEX",
    "NAME_STATE_POINTER_ADDRESS",
    "NAME_STATE_POINTER_RAW_ADDRESS",
    "NAME_WIDTH_TABLE_ADDRESS",
    "NAME_X_START_TABLE_ADDRESS",
    "NameEntryPatch",
    "NameEntryPatchSource",
    "build_name_entry_patch",
]


