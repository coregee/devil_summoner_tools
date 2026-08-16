"""The compact, deterministic word codec used by Saturn EVENT dialogue."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PACKED_TOKEN_BASE = 8
PACKED_TOKEN_LIMIT = 120
DICTIONARY_TOKEN_START = 63
DICTIONARY_RECORD_SIZE = 8
MAX_EXPANSION = DICTIONARY_RECORD_SIZE - 1
SPACE_CODE = 267
BASE_CODES = (SPACE_CODE, *range(1, DICTIONARY_TOKEN_START))
CODE_TO_BASE_TOKEN = {code: token for token, code in enumerate(BASE_CODES)}


def _replace_pair(
    tokens: list[int], pair: tuple[int, int], replacement: int
) -> list[int]:
    output: list[int] = []
    position = 0
    while position < len(tokens):
        if (
            position + 1 < len(tokens)
            and (tokens[position], tokens[position + 1]) == pair
        ):
            output.append(replacement)
            position += 2
        else:
            output.append(tokens[position])
            position += 1
    return output


@dataclass(frozen=True, slots=True)
class EventDictionary:
    """Sequential byte-pair merges over the compact Latin alphabet."""

    merges: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if len(self.merges) > PACKED_TOKEN_LIMIT - DICTIONARY_TOKEN_START:
            raise ValueError("EVENT dictionary has too many merges")
        expansions = [tuple((token,)) for token in range(DICTIONARY_TOKEN_START)]
        for index, pair in enumerate(self.merges):
            token = DICTIONARY_TOKEN_START + index
            if len(pair) != 2 or any(not 0 <= value < token for value in pair):
                raise ValueError(f"EVENT dictionary token {token} is invalid")
            expansion = expansions[pair[0]] + expansions[pair[1]]
            if len(expansion) > MAX_EXPANSION:
                raise ValueError(
                    f"EVENT dictionary token {token} expands beyond "
                    f"{MAX_EXPANSION} glyphs"
                )
            expansions.append(expansion)

    @property
    def expansions(self) -> tuple[tuple[int, ...], ...]:
        rows = [tuple((token,)) for token in range(DICTIONARY_TOKEN_START)]
        for left, right in self.merges:
            rows.append(rows[left] + rows[right])
        return tuple(rows[DICTIONARY_TOKEN_START:])

    def encode_codes(self, codes: list[int]) -> list[int]:
        """Pack supported glyph runs two tokens per u16; retain other words."""
        output: list[int] = []
        direct: list[int] = []

        def flush() -> None:
            tokens = list(direct)
            for index, pair in enumerate(self.merges):
                tokens = _replace_pair(
                    tokens, pair, DICTIONARY_TOKEN_START + index
                )
            for position in range(0, len(tokens), 2):
                first = tokens[position] + PACKED_TOKEN_BASE
                second = (
                    tokens[position + 1] + PACKED_TOKEN_BASE
                    if position + 1 < len(tokens)
                    else 0
                )
                output.append(first << 8 | second)
            direct.clear()

        for code in codes:
            token = CODE_TO_BASE_TOKEN.get(code)
            if token is None:
                flush()
                output.append(code)
            else:
                direct.append(token)
        flush()
        return output

    def decode_words(self, words: tuple[int, ...] | list[int]) -> list[int]:
        output: list[int] = []
        expansions = self.expansions
        for word in words:
            first = word >> 8
            token = first - PACKED_TOKEN_BASE
            if not 0 <= token < PACKED_TOKEN_LIMIT:
                output.append(word)
                continue
            packed = [token]
            if second := word & 0xFF:
                second_token = second - PACKED_TOKEN_BASE
                if not 0 <= second_token < PACKED_TOKEN_LIMIT:
                    raise ValueError(f"invalid packed EVENT byte {second:#x}")
                packed.append(second_token)
            for packed_token in packed:
                base_tokens = (
                    expansions[packed_token - DICTIONARY_TOKEN_START]
                    if packed_token >= DICTIONARY_TOKEN_START
                    else (packed_token,)
                )
                output.extend(BASE_CODES[value] for value in base_tokens)
        return output

    def runtime_table(self) -> bytes:
        table = bytearray(
            (PACKED_TOKEN_LIMIT - DICTIONARY_TOKEN_START)
            * DICTIONARY_RECORD_SIZE
        )
        for index, expansion in enumerate(self.expansions):
            offset = index * DICTIONARY_RECORD_SIZE
            table[offset] = len(expansion)
            table[offset + 1 : offset + 1 + len(expansion)] = bytes(expansion)
        return bytes(table)


def load_event_dictionary(path: Path) -> EventDictionary:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing EVENT codec configuration: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error
    expected = {
        "version": 1,
        "token_base": PACKED_TOKEN_BASE,
        "token_limit": PACKED_TOKEN_LIMIT,
        "dictionary_token_start": DICTIONARY_TOKEN_START,
        "max_expansion": MAX_EXPANSION,
        "base_codes": list(BASE_CODES),
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise ValueError(f"{path}: invalid EVENT codec {key}")
    try:
        merges = tuple(tuple(pair) for pair in document["merges"])
    except (KeyError, TypeError) as error:
        raise ValueError(f"{path}: invalid EVENT codec merges") from error
    return EventDictionary(merges)
