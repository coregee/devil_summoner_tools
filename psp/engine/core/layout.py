"""Neutral runtime-layout contracts shared by ported PSP surfaces."""

from __future__ import annotations


# Stock relocations encode second-PT_LOAD globals relative to this module
# address. Relocation-free cave helpers use the normalized address below.
DATA_LOAD_SEGMENT_ADDRESS = 0x0017A5C0

# The stock EVE renderer consumes the markerless-ASCII advances from this
# checked blank interval. The neighboring title-help allocation starts at
# 0x0013ED00.
EVE_ASCII_WIDTH_TABLE_ADDRESS = 0x0013EC20
WIDTH_TABLE_ADDRESS = EVE_ASCII_WIDTH_TABLE_ADDRESS
EVENT_CAPACITY_HELPER_ADDRESS = 0x0013F800
EVENT_OPTION_RESET_WRAPPER_ADDRESS = 0x00140B70
EVENT_CAVE_END_ADDRESS = 0x00140C38

# NAME shares the checked EVENT allocation without overlapping its helpers.
# Persisted profile rows are also consumed by EVENT, MAP2D, and savedata, so
# their second-load layout belongs to neutral core rather than the screen.
NAME_DATA_SEGMENT_ADDRESS = DATA_LOAD_SEGMENT_ADDRESS
NAME_FIELD_MAX = 8
NAME_PROFILE_RAW_ADDRESS = 0x003F6CF8
NAME_PROFILE_ADDRESS = NAME_DATA_SEGMENT_ADDRESS + NAME_PROFILE_RAW_ADDRESS
NAME_PROFILE_FIELD_OFFSETS = {
    "first": 0x00,
    "last": 0x08,
    "codename": 0x10,
    "city": 0x18,
    "ward": 0x20,
}
NAME_PROFILE_OCCUPATION_OFFSET = 0x28
NAME_PROFILE_CODENAME_MIRROR_OFFSET = 0x34

# Savedata's physical location records are shared with the later dungeon HUD.
# The compact ID table sits immediately before the active-item data partition.
SAVEDATA_LOCATION_SOURCE_RAW_ADDRESS = 0x000032C0
SAVEDATA_LOCATION_SOURCE_ADDRESS = (
    DATA_LOAD_SEGMENT_ADDRESS + SAVEDATA_LOCATION_SOURCE_RAW_ADDRESS
)
SAVEDATA_LOCATION_RECORD_COUNT = 144
SAVEDATA_LOCATION_RECORD_SIZE = 0x20
SAVEDATA_LOCATION_NAME_COUNT = 24
SAVEDATA_LOCATION_ID_TABLE_ADDRESS = 0x00108730

# The maze HUD reuses savedata's 144-to-24 physical/semantic selector. Its
# relocation-free wrappers and compiled two-row draw stream occupy two checked
# source-zero runs; one byte of adjacent zero-backed state tracks the record
# most recently staged by the stock maze-table formatter.
DUNGEON_LOCATION_MAZE_NAME_DRAW_WRAPPER_ADDRESS = 0x0017374C
DUNGEON_LOCATION_FLOOR_DRAW_WRAPPER_ADDRESS = 0x00173890
DUNGEON_LOCATION_MAZE_STAGE_WRAPPER_ADDRESS = 0x00173950
DUNGEON_LOCATION_NAME_DESCRIPTOR_TABLE_ADDRESS = 0x001739C0
DUNGEON_LOCATION_TRANSITION_NAME_BRIDGE_ADDRESS = 0x001739F0
DUNGEON_LOCATION_CAVE_SOURCE_START_ADDRESS = 0x0017374A
DUNGEON_LOCATION_CAVE_END_ADDRESS = 0x00173A60
DUNGEON_LOCATION_NAME_SEQUENCE_TABLE_ADDRESS = 0x001CCB9D
DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_SOURCE_START_ADDRESS = 0x001CCB9D
DUNGEON_LOCATION_NAME_SEQUENCE_CAVE_END_ADDRESS = 0x001CCE60
DUNGEON_LOCATION_STATE_ADDRESS = 0x00173A6C
DUNGEON_LOCATION_STATE_END_ADDRESS = 0x00173A6D
DUNGEON_LOCATION_TRANSITION_CURRENT_ID_ADDRESS = (
    DATA_LOAD_SEGMENT_ADDRESS + 0x00076D6A
)

# The savedata formatter owns the checked interval before the active-item
# description wrapper. Its static table boundary is ITEM_RUNTIME_DATA_ADDRESS,
# declared below and enforced by the runtime composer.
SAVEDATA_DETAIL_WRAPPER_ADDRESS = 0x00172740
SAVEDATA_LOCATION_TEXT_BLOB_ADDRESS = 0x00175488
SAVEDATA_LOCATION_TEXT_CAVE_END_ADDRESS = 0x001755CC

# CONFIG records use one Ark16 width table. This lives in core because later
# PSP surfaces can consume the same checked allocation without CONFIG owning
# their runtime dependency.
SHARED_ARK16_WIDTH_TABLE_ADDRESS = 0x0016F940

# The checked source-zero run has a reserved neighboring partition. Recording
# that boundary prevents CONFIG's wrapper from silently consuming it before
# the neighboring surface is ported.
BATTLE_NAME_DRAW_WRAPPER_ADDRESS = 0x0016F500
BATTLE_NAME_DRAW_WRAPPER_END_ADDRESS = 0x0016F700

# Command-menu help adapts the stock C998 call to the retained EVE renderer in
# the exact gap before the shared CONFIG Ark16 table.
COMMAND_MENU_HELP_DRAW_WRAPPER_ADDRESS = 0x0016F700
COMMAND_MENU_HELP_DRAW_WRAPPER_END_ADDRESS = 0x0016F800

CONFIG_RECORD_TABLE_ADDRESS = 0x0016FA00
CONFIG_RECORD_STRIDE = 0x100
CONFIG_RECORD_COUNT = 29
CONFIG_RECORD_TABLE_END_ADDRESS = (
    CONFIG_RECORD_TABLE_ADDRESS + CONFIG_RECORD_COUNT * CONFIG_RECORD_STRIDE
)
BATTLE_NAME_CODE_TABLE_ADDRESS = CONFIG_RECORD_TABLE_END_ADDRESS
BATTLE_NAME_CAVE_END_ADDRESS = 0x00171800
CONFIG_CAVE_END_ADDRESS = 0x00172C38

# Command help and later COMP party cards share one per-frame retained-handle
# lifecycle. This slice installs the neutral owner with command help as its
# first consumer.
EVE_UI_HANDLE_FRAME_WRAPPER_ADDRESS = 0x00172014
EVE_UI_HANDLE_APPEND_ADDRESS = 0x001720C0
EVE_UI_HANDLE_STATE_ADDRESS = 0x00172175
EVE_UI_HANDLE_CAVE_END_ADDRESS = 0x00172200

# The PSP-only item renderer uses the remaining checked partitions in the
# CONFIG cave. It shares the Compendium packed renderer and EVE widths.
ITEM_RUNTIME_DATA_ADDRESS = 0x0010884F
ITEM_RUNTIME_DATA_END_ADDRESS = 0x00108944
ITEM_EVENT_INSERT_WRAPPER_ADDRESS = 0x00171D24
ITEM_EVENT_INSERT_WRAPPER_END_ADDRESS = 0x00171E00
BATTLE_RESULT_DRAW_WRAPPER_ADDRESS = ITEM_EVENT_INSERT_WRAPPER_END_ADDRESS
BATTLE_RESULT_STATIC_STORAGE_ADDRESS = 0x00172200
ITEM_NAME_RESOLVER_ADDRESS = 0x00172260
BATTLE_RESULT_CAVE_END_ADDRESS = ITEM_NAME_RESOLVER_ADDRESS
ITEM_NAME_DRAW_WRAPPER_ADDRESS = 0x00172360
ITEM_NAME_DRAW_WRAPPER_END_ADDRESS = 0x00172400
ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS = 0x00172ABC
ITEM_DESCRIPTION_DRAW_WRAPPER_END_ADDRESS = 0x00172C38

# MAP2D fills the remaining partitions between the active-item wrappers and
# savedata. Its dynamic profile renderer, top prompt rows, width table, and
# fixed destination rows share one checked source-zero allocation.
MAP2D_DYNAMIC_DRAW_WRAPPER_ADDRESS = 0x00171800
MAP2D_TOP_DRAW_WRAPPER_ADDRESS = 0x00172400
MAP2D_WIDTH_TABLE_ADDRESS = 0x00172600
MAP2D_TOP_ROW_TABLE_ADDRESS = 0x00172680
MAP2D_FIXED_ROW_TABLE_ADDRESS = 0x00172700

# The Compendium owns three checked source-zero code partitions near the end
# of .rodata. Prose retains the original lore arena; the packed full-name
# table occupies its tail, making the two runtime halves one atomic surface.
COMPENDIUM_DRAW_WRAPPER_ADDRESS = 0x00176794
COMPENDIUM_DRAW_WRAPPER_END_ADDRESS = 0x00176900
COMPENDIUM_NAME_DRAW_WRAPPER_ADDRESS = 0x00177130
COMPENDIUM_NAME_DRAW_WRAPPER_END_ADDRESS = 0x00177290
COMPENDIUM_NAME_COMPARE_WRAPPER_ADDRESS = 0x00177AC0
COMPENDIUM_NAME_COMPARE_WRAPPER_END_ADDRESS = 0x00177C24
COMPENDIUM_NAME_TABLE_ADDRESS = 0x001BDB00
COMPENDIUM_NAME_TABLE_SIZE = 3_205
COMPENDIUM_NAME_TABLE_END_ADDRESS = (
    COMPENDIUM_NAME_TABLE_ADDRESS + COMPENDIUM_NAME_TABLE_SIZE
)

# The common six-card COMP party panel uses a file-backed source-zero .data
# partition. Its Ark10 widths follow the same packed printable-ASCII order as
# EVENT/help; the five fixed CHARNAME rows occupy the final table partition.
COMP_PARTY_NAME_DRAW_WRAPPER_ADDRESS = 0x001C23F4
COMP_PARTY_NAME_WIDTH_TABLE_ADDRESS = 0x001C2640
COMP_PARTY_NAME_CHARACTER_TABLE_ADDRESS = 0x001C26A0
COMP_PARTY_NAME_CAVE_END_ADDRESS = 0x001C2740
