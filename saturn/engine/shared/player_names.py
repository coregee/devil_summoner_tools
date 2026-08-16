"""Shared runtime contract for player-entered Saturn names.

The game saves the five editable name fields as eight ASCII bytes each.  The
renderer-facing buffers use the generated FONT16/FONT8 atlases instead, so
SAVE/LOAD and NAME.BIN must agree on both the WRAM addresses and the complete
byte conversion tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from text.util.tokens import Named, Text, parse_tokens


MAX_NAME_BYTES = 8
FONT16_TERMINATOR = 0x8000
FONT16_ROW_WORDS = MAX_NAME_BYTES + 1
FONT16_ROW_STRIDE = FONT16_ROW_WORDS * 2

NAME_FW = 0x0023FDF0
NAME_FW_FULL = 0x0023FE50
CODENAME_BYTES = 0x0023FFD0


@dataclass(frozen=True, slots=True)
class PlayerNameField:
    key: str
    stage_address: int
    row_index: int

    @property
    def runtime_address(self) -> int:
        return NAME_FW + self.row_index * FONT16_ROW_STRIDE


@dataclass(frozen=True, slots=True)
class FullNameTemplate:
    field_order: tuple[str, str]
    separator: str


PLAYER_NAME_FIELDS = (
    PlayerNameField("first_name", 0x002029E0, 0),
    PlayerNameField("last_name", 0x002029E8, 1),
    PlayerNameField("codename", 0x002029D8, 2),
    PlayerNameField("city", 0x002029F0, 3),
    PlayerNameField("ward", 0x002029F8, 4),
)
PLAYER_NAME_FIELD_BY_KEY: Mapping[str, PlayerNameField] = MappingProxyType(
    {field.key: field for field in PLAYER_NAME_FIELDS}
)


def parse_full_name_template(
    value: str,
    *,
    allow_reverse: bool = True,
) -> FullNameTemplate:
    """Parse two player-name tokens separated by one authored literal.

    Token parsing matters here: escaped braces are literal separator text, while
    named placeholders retain their semantic identity.  Renderers decide how
    many font glyphs the separator may occupy.
    """
    tokens = parse_tokens(value)
    if (
        len(tokens) != 3
        or not isinstance(tokens[0], Named)
        or not isinstance(tokens[1], Text)
        or not isinstance(tokens[2], Named)
    ):
        raise ValueError(
            "full-name template must be "
            "'{first_name}<literal>{last_name}' or the reverse"
        )
    order = (tokens[0].name, tokens[2].name)
    allowed = {("first_name", "last_name")}
    if allow_reverse:
        allowed.add(("last_name", "first_name"))
    if order not in allowed:
        suffix = " or the reverse" if allow_reverse else ""
        raise ValueError(
            "full-name template must use first_name then last_name" + suffix
        )
    return FullNameTemplate(order, tokens[1].value)


def byte_to_font16_table(codes: Mapping[str, int]) -> tuple[int, ...]:
    """Map every saved byte safely into one generated FONT16 atlas."""
    try:
        fallback = codes["?"]
        blank = codes[" "]
    except KeyError as error:
        raise ValueError("FONT16 player-name atlas needs '?' and space") from error
    table = [fallback] * 256
    table[0] = blank
    for value in range(0x20, 0x7F):
        table[value] = codes.get(chr(value), fallback)
    if any(not 0 <= value <= 0xFFFF for value in table):
        raise ValueError("FONT16 player-name code exceeds one word")
    return tuple(table)


def byte_to_advance_table(advances: Mapping[str, int]) -> bytes:
    """Map every saved byte to its deterministic proportional advance."""
    try:
        fallback = advances["?"]
    except KeyError as error:
        raise ValueError("FONT16 player-name metrics need '?'") from error
    table = bytearray([fallback] * 256)
    table[0] = 0
    for value in range(0x20, 0x7F):
        table[value] = advances.get(chr(value), fallback)
    return bytes(table)


def byte_to_font8_table(codes: Mapping[str, int]) -> bytes:
    """Map saved ASCII into the generated narrow FONT8 alphabet."""
    try:
        fallback = codes["?"]
    except KeyError as error:
        raise ValueError("FONT8 player-name atlas needs '?'") from error
    table = bytearray([fallback] * 256)
    table[0] = 0
    for value in range(0x20, 0x7F):
        table[value] = codes.get(chr(value), fallback)
    return bytes(table)
