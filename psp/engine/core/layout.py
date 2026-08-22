"""Neutral runtime-layout contracts shared by ported PSP surfaces."""

from __future__ import annotations


# Stock relocations encode second-PT_LOAD globals relative to this module
# address. Relocation-free cave helpers use the normalized address below.
DATA_LOAD_SEGMENT_ADDRESS = 0x0017A5C0

# CONFIG records use one Ark16 width table. This lives in core because later
# PSP surfaces can consume the same checked allocation without CONFIG owning
# their runtime dependency.
SHARED_ARK16_WIDTH_TABLE_ADDRESS = 0x0016F940

# The checked source-zero run has a reserved neighboring partition. Recording
# that boundary prevents CONFIG's wrapper from silently consuming it before
# the neighboring surface is ported.
BATTLE_NAME_DRAW_WRAPPER_ADDRESS = 0x0016F500

CONFIG_RECORD_TABLE_ADDRESS = 0x0016FA00
CONFIG_RECORD_STRIDE = 0x100
CONFIG_RECORD_COUNT = 29
CONFIG_RECORD_TABLE_END_ADDRESS = (
    CONFIG_RECORD_TABLE_ADDRESS + CONFIG_RECORD_COUNT * CONFIG_RECORD_STRIDE
)
CONFIG_CAVE_END_ADDRESS = 0x00172C38
