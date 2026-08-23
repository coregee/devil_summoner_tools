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

# CONFIG records use one Ark16 width table. This lives in core because later
# PSP surfaces can consume the same checked allocation without CONFIG owning
# their runtime dependency.
SHARED_ARK16_WIDTH_TABLE_ADDRESS = 0x0016F940

# The checked source-zero run has a reserved neighboring partition. Recording
# that boundary prevents CONFIG's wrapper from silently consuming it before
# the neighboring surface is ported.
BATTLE_NAME_DRAW_WRAPPER_ADDRESS = 0x0016F500

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
ITEM_NAME_RESOLVER_ADDRESS = 0x00172260
ITEM_NAME_DRAW_WRAPPER_ADDRESS = 0x00172360
ITEM_NAME_DRAW_WRAPPER_END_ADDRESS = 0x00172400
ITEM_DESCRIPTION_DRAW_WRAPPER_ADDRESS = 0x00172ABC
ITEM_DESCRIPTION_DRAW_WRAPPER_END_ADDRESS = 0x00172C38

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
