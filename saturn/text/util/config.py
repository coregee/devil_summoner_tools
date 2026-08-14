"""Load reusable Saturn source encodings from one strict JSON catalog."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .tokens import valid_name

TEXT_ROOT = Path(__file__).resolve().parent.parent
ENCODINGS_PATH = TEXT_ROOT / "config" / "encodings.json"
FONT_CONFIG_ROOT = TEXT_ROOT.parent / "font" / "config"

_ID_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_FONT_RE = re.compile(r"([a-z][a-z0-9_]*)/([a-z][a-z0-9_]*)\Z")
_HEX_RE = re.compile(r"0x[0-9a-f]+\Z")
_NAMED_GLYPH_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}\Z")
_CODEC_WIDTHS = {"ascii": 1, "glyph_u8": 1, "glyph_u16be": 2}


@dataclass(frozen=True)
class Alphabet:
    name: str
    font: str | None
    glyphs: Mapping[int, str]


@dataclass(frozen=True)
class SourceEncoding:
    name: str
    codec: str
    zero: str
    glyphs: Mapping[int, str]
    controls: Mapping[int, str]
    control_ranges: tuple[tuple[int, int], ...]
    ambiguous_glyphs: frozenset[str]
    named_glyph_codes: Mapping[str, int]

    @property
    def unit_width(self) -> int:
        return _CODEC_WIDTHS[self.codec]

    def is_control(self, code: int) -> bool:
        return any(start <= code <= end for start, end in self.control_ranges)


@dataclass(frozen=True)
class EncodingCatalog:
    alphabets: Mapping[str, Alphabet]
    source_encodings: Mapping[str, SourceEncoding]

    def source(self, name: str) -> SourceEncoding:
        try:
            return self.source_encodings[name]
        except KeyError as error:
            choices = ", ".join(self.source_encodings)
            raise ValueError(
                f"unknown source encoding {name!r}; choose from {choices}"
            ) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing configuration file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(row: dict[str, Any], expected: set[str], context: str) -> None:
    if set(row) != expected:
        raise ValueError(
            f"{context} fields are {sorted(row)}, expected {sorted(expected)}"
        )


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier")
    return value


def _hex_code(value: Any, context: str, limit: int) -> int:
    if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase 0x-prefixed hexadecimal text")
    code = int(value, 16)
    if code >= limit:
        raise ValueError(f"{context} exceeds its code-unit width")
    return code


def _atlas_index(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a nonnegative decimal glyph index")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str) and value.isdecimal():
        index = int(value)
    else:
        raise ValueError(f"{context} must be a nonnegative decimal glyph index")
    if index < 0:
        raise ValueError(f"{context} cannot be negative")
    return index


def _font_glyphs(path: Path) -> dict[int, str]:
    """Read original glyph values from a font package definition."""
    document = _object(_read_json(path), str(path))
    atlas = _object(document.get("atlas"), f"{path}.atlas")
    groups = _object(atlas.get("groups"), f"{path}.atlas.groups")
    glyphs: dict[int, str] = {}

    def add(index: int, value: str, context: str) -> None:
        if index in glyphs:
            raise ValueError(f"{context} maps glyph {index} more than once")
        if not isinstance(value, str) or not value:
            raise ValueError(f"{context} has an invalid glyph value")
        glyphs[index] = value

    for group_name, entries in groups.items():
        context = f"{path}.atlas.groups.{group_name}"
        if not isinstance(entries, list):
            raise ValueError(f"{context} must be an array")
        for number, raw_entry in enumerate(entries):
            entry_context = f"{context}[{number}]"
            entry = _object(raw_entry, entry_context)
            if "start" in entry:
                value_keys = set(entry) & {"characters", "glyphs"}
                if len(value_keys) != 1:
                    raise ValueError(f"{entry_context} needs one glyph value field")
                values = entry[next(iter(value_keys))]
                if isinstance(values, str):
                    characters = tuple(values)
                elif isinstance(values, list):
                    characters = tuple(values)
                else:
                    raise ValueError(f"{entry_context} has invalid glyph values")
                start = _atlas_index(entry["start"], f"{entry_context}.start")
                for offset, character in enumerate(characters):
                    add(start + offset, character, entry_context)
                continue

            mappings = {key: value for key, value in entry.items() if key != "replace"}
            if not mappings:
                raise ValueError(f"{entry_context} has no glyph mappings")
            for raw_index, raw_value in mappings.items():
                index = _atlas_index(raw_index, f"{entry_context}.{raw_index}")
                if isinstance(raw_value, dict) and len(raw_value) == 1:
                    original = next(iter(raw_value))
                else:
                    original = raw_value
                add(index, original, entry_context)
    return glyphs


def _load_alphabets(
    value: Any,
    font_root: Path,
    context: str,
) -> dict[str, Alphabet]:
    rows = _object(value, context)
    alphabets: dict[str, Alphabet] = {}
    for raw_name, definition in rows.items():
        name = _identifier(raw_name, f"{context} name")
        if isinstance(definition, str):
            match = _FONT_RE.fullmatch(definition)
            if match is None:
                raise ValueError(
                    f"{context}.{name} must be a safe disc/font reference"
                )
            disc, font = match.groups()
            path = font_root / disc / f"{font}.json"
            alphabets[name] = Alphabet(
                name,
                definition,
                MappingProxyType(_font_glyphs(path)),
            )
            continue

        row = _object(definition, f"{context}.{name}")
        _fields(row, {"glyphs"}, f"{context}.{name}")
        glyph_rows = _object(row["glyphs"], f"{context}.{name}.glyphs")
        glyphs: dict[int, str] = {}
        for raw_code, glyph in glyph_rows.items():
            code = _hex_code(raw_code, f"{context}.{name}.glyphs.{raw_code}", 0x10000)
            if not isinstance(glyph, str) or not glyph:
                raise ValueError(f"{context}.{name}.glyphs.{raw_code} is invalid")
            glyphs[code] = glyph
        if not glyphs:
            raise ValueError(f"{context}.{name}.glyphs must not be empty")
        alphabets[name] = Alphabet(name, None, MappingProxyType(glyphs))
    if not alphabets:
        raise ValueError(f"{context} must not be empty")
    return alphabets


def _load_vocabularies(
    value: Any,
    context: str,
) -> dict[str, Mapping[int, str]]:
    rows = _object(value, context)
    vocabularies: dict[str, Mapping[int, str]] = {}
    for raw_name, raw_codes in rows.items():
        name = _identifier(raw_name, f"{context} name")
        code_rows = _object(raw_codes, f"{context}.{name}")
        codes: dict[int, str] = {}
        tokens: set[str] = set()
        for raw_code, token in code_rows.items():
            code = _hex_code(raw_code, f"{context}.{name}.{raw_code}", 0x10000)
            if not isinstance(token, str) or not valid_name(token):
                raise ValueError(f"{context}.{name}.{raw_code} has an invalid token")
            if token in tokens:
                raise ValueError(f"{context}.{name} repeats token {token!r}")
            codes[code] = token
            tokens.add(token)
        vocabularies[name] = MappingProxyType(dict(sorted(codes.items())))
    if vocabularies.get("none") != {}:
        raise ValueError(f"{context}.none must be an empty vocabulary")
    return vocabularies


def _ranges(value: Any, context: str, limit: int) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    result: list[tuple[int, int]] = []
    previous_end = -1
    for index, raw_range in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(raw_range, list) or len(raw_range) != 2:
            raise ValueError(f"{item_context} must contain a start and end")
        start = _hex_code(raw_range[0], f"{item_context}[0]", limit)
        end = _hex_code(raw_range[1], f"{item_context}[1]", limit)
        if start > end or start <= previous_end:
            raise ValueError(f"{context} must be ordered and disjoint")
        result.append((start, end))
        previous_end = end
    return tuple(result)


def _load_source(
    name: str,
    value: Any,
    alphabets: Mapping[str, Alphabet],
    vocabularies: Mapping[str, Mapping[int, str]],
    context: str,
) -> SourceEncoding:
    row = _object(value, context)
    _fields(
        row,
        {"codec", "zero", "glyph_banks", "control_vocabulary", "control_ranges"},
        context,
    )
    codec = row["codec"]
    if not isinstance(codec, str) or codec not in _CODEC_WIDTHS:
        raise ValueError(f"{context}.codec must be one of {', '.join(_CODEC_WIDTHS)}")
    limit = 1 << (_CODEC_WIDTHS[codec] * 8)
    zero = row["zero"]
    zero_modes = {
        "glyph",
        "skip",
        "space",
        "separator_space",
        "separator_newline",
    }
    if not isinstance(zero, str) or zero not in zero_modes:
        choices = ", ".join(sorted(zero_modes))
        raise ValueError(f"{context}.zero must be one of {choices}")

    vocabulary_name = row["control_vocabulary"]
    if not isinstance(vocabulary_name, str) or vocabulary_name not in vocabularies:
        raise ValueError(f"{context}.control_vocabulary is unknown")
    controls = vocabularies[vocabulary_name]
    if any(code >= limit for code in controls):
        raise ValueError(f"{context}.control_vocabulary has an oversized code")
    control_ranges = _ranges(
        row["control_ranges"],
        f"{context}.control_ranges",
        limit,
    )
    if any(
        not any(start <= code <= end for start, end in control_ranges)
        for code in controls
    ):
        raise ValueError(f"{context} has a named control outside its control ranges")

    raw_banks = row["glyph_banks"]
    if not isinstance(raw_banks, list):
        raise ValueError(f"{context}.glyph_banks must be an array")
    if codec == "ascii" and raw_banks:
        raise ValueError(f"{context}: ASCII uses its built-in printable alphabet")
    if codec != "ascii" and not raw_banks:
        raise ValueError(f"{context}: glyph codecs need an alphabet bank")

    glyphs = {code: chr(code) for code in range(0x20, 0x7F)} if codec == "ascii" else {}
    previous_end = -1
    for index, raw_bank in enumerate(raw_banks):
        bank_context = f"{context}.glyph_banks[{index}]"
        bank = _object(raw_bank, bank_context)
        _fields(bank, {"alphabet", "start", "end", "glyph_start"}, bank_context)
        alphabet_name = bank["alphabet"]
        if not isinstance(alphabet_name, str) or alphabet_name not in alphabets:
            raise ValueError(f"{bank_context}.alphabet is unknown")
        start = _hex_code(bank["start"], f"{bank_context}.start", limit)
        end = _hex_code(bank["end"], f"{bank_context}.end", limit)
        glyph_start = _hex_code(
            bank["glyph_start"],
            f"{bank_context}.glyph_start",
            0x10000,
        )
        if start > end or start <= previous_end:
            raise ValueError(f"{context}.glyph_banks must be ordered and disjoint")
        if any(start <= high and low <= end for low, high in control_ranges):
            raise ValueError(f"{bank_context} overlaps a control range")

        alphabet = alphabets[alphabet_name]
        for glyph_index, glyph in alphabet.glyphs.items():
            code = start + glyph_index - glyph_start
            if start <= code <= end:
                glyphs[code] = glyph
        previous_end = end

    range_overlap = {
        code
        for code in glyphs
        if any(low <= code <= high for low, high in control_ranges)
    }
    if range_overlap:
        rendered = ", ".join(f"{code:#x}" for code in sorted(range_overlap))
        raise ValueError(f"{context} maps control-range code(s) as glyphs: {rendered}")

    counts = Counter(glyphs.values())
    ambiguous = frozenset(value for value, count in counts.items() if count > 1)
    named_glyph_codes: dict[str, int] = {}
    for code, value in glyphs.items():
        if (match := _NAMED_GLYPH_RE.fullmatch(value)) and value not in ambiguous:
            token = match.group(1)
            if not valid_name(token):
                raise ValueError(f"{context} has invalid named glyph {value!r}")
            named_glyph_codes[token] = code
    if collisions := set(named_glyph_codes) & set(controls.values()):
        rendered = ", ".join(sorted(collisions))
        raise ValueError(
            f"{context} reuses named glyphs as controls: {rendered}"
        )

    return SourceEncoding(
        name,
        codec,
        zero,
        MappingProxyType(dict(sorted(glyphs.items()))),
        controls,
        control_ranges,
        ambiguous,
        MappingProxyType(named_glyph_codes),
    )


def load_config(
    path: Path = ENCODINGS_PATH,
    *,
    font_config_root: Path = FONT_CONFIG_ROOT,
) -> EncodingCatalog:
    document = _object(_read_json(path), str(path))
    _fields(
        document,
        {"version", "alphabets", "control_vocabularies", "source_encodings"},
        str(path),
    )
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError(f"{path}: unsupported encoding catalog version")

    alphabets = _load_alphabets(
        document["alphabets"], font_config_root, f"{path}.alphabets"
    )
    vocabularies = _load_vocabularies(
        document["control_vocabularies"], f"{path}.control_vocabularies"
    )
    source_rows = _object(document["source_encodings"], f"{path}.source_encodings")
    sources: dict[str, SourceEncoding] = {}
    for raw_name, value in source_rows.items():
        name = _identifier(raw_name, f"{path}.source_encodings name")
        sources[name] = _load_source(
            name,
            value,
            alphabets,
            vocabularies,
            f"{path}.source_encodings.{name}",
        )
    if not sources:
        raise ValueError(f"{path}.source_encodings must not be empty")
    return EncodingCatalog(
        MappingProxyType(alphabets),
        MappingProxyType(sources),
    )
