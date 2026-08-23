"""Compile canonical Demon Compendium prose into the PSP BOOT arenas."""

from __future__ import annotations

import json
import struct
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from psp.text.util.assets import load_asset_field
from psp.text.util.event_packed import encode_ascii

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "compendium.json"
COMPENDIUM_PROFILE_COUNT = 319
COMPENDIUM_LIVE_PROFILE_COUNT = 292
COMPENDIUM_FIELD_COUNT = 3
COMPENDIUM_POINTER_RECORD_SIZE = 0x10
COMPENDIUM_TEXT_ARENA_SIZE = 0x1D028
COMPENDIUM_ORIGIN_WIDTH = 195
COMPENDIUM_BODY_WIDTH = 315
COMPENDIUM_ORIGIN_LINE_LIMIT = 1
COMPENDIUM_SUMMARY_LINE_LIMIT = 3
COMPENDIUM_DETAIL_LINE_LIMIT = 11
COMPENDIUM_TERMINATOR = 0x00
COMPENDIUM_NEWLINE = 0x01

_FIELD_NAMES = ("compendium_origin", "compendium_summary", "compendium_detail")
_LIVE_STATUSES = frozenset(("live_saturn", "live_psp"))
_ROW_STATUSES = _LIVE_STATUSES | frozenset(("empty", "orphan_unbound"))
_NORMALIZE_CHARACTERS = {
    "\u00a0": " ",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "–": "-",
    "—": "-",
}


@dataclass(frozen=True, slots=True)
class CompendiumProfileText:
    row_index: int
    flags: int
    record_id: str | None
    origin: str | None
    summary: str | None
    detail: str | None
    reviewed: bool = False

    @property
    def live(self) -> bool:
        return self.record_id is not None


@dataclass(frozen=True, slots=True)
class CompendiumPackedProfile:
    row_index: int
    record_id: str
    flags: int
    origin_lines: tuple[str, ...]
    summary_lines: tuple[str, ...]
    detail_lines: tuple[str, ...]
    pointers: tuple[int, int, int]
    reviewed: bool


@dataclass(frozen=True, slots=True)
class CompendiumTextBuild:
    text_arena: bytes
    pointer_table: bytes
    profiles: tuple[CompendiumPackedProfile, ...]
    used_size: int
    unique_string_count: int
    translated_field_count: int
    reviewed_field_count: int


def load_compendium_profiles(
    path: Path = CONFIG_PATH,
) -> tuple[CompendiumProfileText, ...]:
    """Resolve all 319 physical rows through the shared semantic catalogue."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP Compendium binding: {path}") from error
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "demon_compendium"
        or document.get("target") != "BOOT.BIN"
        or document.get("profile_count") != COMPENDIUM_PROFILE_COUNT
        or document.get("live_profile_count") != COMPENDIUM_LIVE_PROFILE_COUNT
        or document.get("fields") != list(_FIELD_NAMES)
        or not isinstance(document.get("rows"), list)
        or len(document["rows"]) != COMPENDIUM_PROFILE_COUNT
    ):
        raise ValueError(f"{path}: unsupported PSP Compendium binding")

    output: list[CompendiumProfileText] = []
    seen_assets: set[str] = set()
    live_count = 0
    for row_index, row in enumerate(document["rows"]):
        context = f"{path}: row {row_index}"
        if not isinstance(row, dict) or set(row) != {
            "row_index", "status", "flags", "asset"
        }:
            raise ValueError(f"{context}: invalid row contract")
        if row["row_index"] != row_index or row["status"] not in _ROW_STATUSES:
            raise ValueError(f"{context}: physical identity changed")
        flags_text = row["flags"]
        if (
            not isinstance(flags_text, str)
            or len(flags_text) != 10
            or not flags_text.startswith("0x")
        ):
            raise ValueError(f"{context}: flags changed")
        try:
            flags = int(flags_text, 16)
        except ValueError as error:
            raise ValueError(f"{context}: flags changed") from error
        asset = row["asset"]
        if row["status"] in _LIVE_STATUSES:
            if (
                not isinstance(asset, str)
                or not asset
                or asset in seen_assets
            ):
                raise ValueError(f"{context}: live asset identity changed")
            seen_assets.add(asset)
            fields = tuple(
                load_asset_field(f"demons.json#{asset}.{field_name}")
                for field_name in _FIELD_NAMES
            )
            output.append(
                CompendiumProfileText(
                    row_index,
                    flags,
                    f"demons.json#{asset}",
                    fields[0][1],
                    fields[1][1],
                    fields[2][1],
                )
            )
            live_count += 1
        else:
            if asset is not None:
                raise ValueError(f"{context}: inactive row owns an asset")
            output.append(
                CompendiumProfileText(row_index, flags, None, None, None, None)
            )
    if live_count != COMPENDIUM_LIVE_PROFILE_COUNT:
        raise ValueError(
            f"PSP Compendium has {live_count} live rows; "
            f"expected {COMPENDIUM_LIVE_PROFILE_COUNT}"
        )
    return tuple(output)


def _normalize_text(value: str, context: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{context}: translation must be text")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    for source, replacement in _NORMALIZE_CHARACTERS.items():
        normalized = normalized.replace(source, replacement)
    normalized = normalized.replace("{n}", "\n")
    if not normalized.strip():
        raise ValueError(f"{context}: translation is empty")
    if "{" in normalized or "}" in normalized:
        raise ValueError(f"{context}: unsupported brace token")
    if any(
        character != "\n" and not 0x20 <= ord(character) <= 0x7E
        for character in normalized
    ):
        raise ValueError(f"{context}: translation must normalize to printable ASCII")
    return normalized


def _measure(value: str, measure_ascii: Callable[[str], int], context: str) -> int:
    width = measure_ascii(value)
    if not isinstance(width, int) or isinstance(width, bool) or width < 0:
        raise ValueError(f"{context}: width callback returned an invalid value")
    return width


def _wrap_field(
    value: str,
    measure_ascii: Callable[[str], int],
    *,
    width_limit: int,
    line_limit: int,
    context: str,
) -> tuple[str, ...]:
    normalized = _normalize_text(value, context)
    lines: list[str] = []
    for explicit_line in normalized.split("\n"):
        words = explicit_line.split()
        if not words:
            if not lines or lines[-1] != "":
                lines.append("")
            continue
        current: list[str] = []
        for word in words:
            word_width = _measure(word, measure_ascii, context)
            if word_width > width_limit:
                raise ValueError(
                    f"{context}: word {word!r} is {word_width}px; "
                    f"limit is {width_limit}px"
                )
            candidate = " ".join((*current, word))
            if current and _measure(candidate, measure_ascii, context) > width_limit:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        lines.append(" ".join(current))

    while lines and lines[-1] == "":
        lines.pop()
    if not lines or any(not line for line in lines):
        raise ValueError(f"{context}: blank Compendium rows are unsupported")
    if len(lines) > line_limit:
        raise ValueError(
            f"{context}: wrapped to {len(lines)} rows; limit is {line_limit}"
        )
    for line_index, line in enumerate(lines):
        width = _measure(line, measure_ascii, context)
        if width > width_limit:
            raise ValueError(
                f"{context}: row {line_index} is {width}px; limit is {width_limit}px"
            )
    return tuple(lines)


def _encode_lines(lines: tuple[str, ...]) -> bytes:
    output = bytearray()
    for line_index, line in enumerate(lines):
        if line_index:
            output.append(COMPENDIUM_NEWLINE)
        output.extend(encode_ascii(line))
    output.append(COMPENDIUM_TERMINATOR)
    return bytes(output)


def build_compendium_text(
    profiles: Iterable[CompendiumProfileText],
    measure_ascii: Callable[[str], int],
    *,
    arena_size: int,
    arena_raw_address: int,
) -> CompendiumTextBuild:
    """Wrap, deduplicate, and place every live profile in the retail arena."""

    try:
        rows = tuple(profiles)
    except TypeError as error:
        raise TypeError("PSP Compendium profiles must be iterable") from error
    if len(rows) != COMPENDIUM_PROFILE_COUNT:
        raise ValueError(
            f"PSP Compendium has {len(rows)} rows; expected {COMPENDIUM_PROFILE_COUNT}"
        )
    if not callable(measure_ascii):
        raise TypeError("PSP Compendium width callback must be callable")
    if arena_size != COMPENDIUM_TEXT_ARENA_SIZE:
        raise ValueError(
            f"PSP Compendium arena size is {arena_size!r}; "
            f"expected {COMPENDIUM_TEXT_ARENA_SIZE}"
        )
    if (
        not isinstance(arena_raw_address, int)
        or isinstance(arena_raw_address, bool)
        or not 0 <= arena_raw_address <= 0xFFFFFFFF
    ):
        raise ValueError("PSP Compendium raw arena address must be u32")

    arena = bytearray(arena_size)
    table = bytearray(COMPENDIUM_PROFILE_COUNT * COMPENDIUM_POINTER_RECORD_SIZE)
    pool = bytearray()
    offsets: dict[bytes, int] = {}
    packed_profiles: list[CompendiumPackedProfile] = []
    live_count = 0

    def place(encoded: bytes, context: str) -> int:
        existing = offsets.get(encoded)
        if existing is not None:
            return arena_raw_address + existing
        offset = len(pool)
        if offset + len(encoded) > arena_size:
            raise ValueError(
                f"{context}: Compendium text needs {offset + len(encoded)} bytes; "
                f"arena capacity is {arena_size}"
            )
        pool.extend(encoded)
        offsets[encoded] = offset
        return arena_raw_address + offset

    for expected_index, row in enumerate(rows):
        context = f"PSP Compendium row {expected_index}"
        if not isinstance(row, CompendiumProfileText):
            raise TypeError(f"{context}: row has the wrong type")
        if row.row_index != expected_index:
            raise ValueError(f"{context}: physical row identity changed")
        if (
            not isinstance(row.flags, int)
            or isinstance(row.flags, bool)
            or not 0 <= row.flags <= 0xFFFFFFFF
        ):
            raise ValueError(f"{context}: flags must be u32")
        if not isinstance(row.reviewed, bool):
            raise TypeError(f"{context}: reviewed must be boolean")

        origin = row.origin
        summary = row.summary
        detail = row.detail
        fields = (origin, summary, detail)
        pointers: tuple[int, int, int]
        if row.live:
            live_count += 1
            if not isinstance(row.record_id, str) or not row.record_id:
                raise ValueError(f"{context}: live row needs a stable record ID")
            if (
                not isinstance(origin, str)
                or not isinstance(summary, str)
                or not isinstance(detail, str)
            ):
                raise ValueError(f"{context}: live row needs all three translations")
            origin_lines = _wrap_field(
                origin,
                measure_ascii,
                width_limit=COMPENDIUM_ORIGIN_WIDTH,
                line_limit=COMPENDIUM_ORIGIN_LINE_LIMIT,
                context=f"{context} origin",
            )
            summary_lines = _wrap_field(
                summary,
                measure_ascii,
                width_limit=COMPENDIUM_BODY_WIDTH,
                line_limit=COMPENDIUM_SUMMARY_LINE_LIMIT,
                context=f"{context} summary",
            )
            detail_lines = _wrap_field(
                detail,
                measure_ascii,
                width_limit=COMPENDIUM_BODY_WIDTH,
                line_limit=COMPENDIUM_DETAIL_LINE_LIMIT,
                context=f"{context} detail",
            )
            pointers = (
                place(_encode_lines(origin_lines), f"{context} field 0"),
                place(_encode_lines(summary_lines), f"{context} field 1"),
                place(_encode_lines(detail_lines), f"{context} field 2"),
            )
            packed_profiles.append(
                CompendiumPackedProfile(
                    row_index=row.row_index,
                    record_id=row.record_id,
                    flags=row.flags,
                    origin_lines=origin_lines,
                    summary_lines=summary_lines,
                    detail_lines=detail_lines,
                    pointers=pointers,
                    reviewed=row.reviewed,
                )
            )
        else:
            if any(field is not None for field in fields):
                raise ValueError(f"{context}: empty row cannot contain translations")
            pointers = (0, 0, 0)
        struct.pack_into(
            "<IIII",
            table,
            expected_index * COMPENDIUM_POINTER_RECORD_SIZE,
            *pointers,
            row.flags,
        )

    if live_count != COMPENDIUM_LIVE_PROFILE_COUNT:
        raise ValueError(
            f"PSP Compendium has {live_count} live rows; "
            f"expected {COMPENDIUM_LIVE_PROFILE_COUNT}"
        )
    arena[: len(pool)] = pool
    reviewed_profiles = sum(profile.reviewed for profile in packed_profiles)
    return CompendiumTextBuild(
        text_arena=bytes(arena),
        pointer_table=bytes(table),
        profiles=tuple(packed_profiles),
        used_size=len(pool),
        unique_string_count=len(offsets),
        translated_field_count=live_count * COMPENDIUM_FIELD_COUNT,
        reviewed_field_count=reviewed_profiles * COMPENDIUM_FIELD_COUNT,
    )

__all__ = [
    "CONFIG_PATH",
    "COMPENDIUM_BODY_WIDTH",
    "COMPENDIUM_DETAIL_LINE_LIMIT",
    "COMPENDIUM_FIELD_COUNT",
    "COMPENDIUM_LIVE_PROFILE_COUNT",
    "COMPENDIUM_NEWLINE",
    "COMPENDIUM_ORIGIN_LINE_LIMIT",
    "COMPENDIUM_ORIGIN_WIDTH",
    "COMPENDIUM_POINTER_RECORD_SIZE",
    "COMPENDIUM_PROFILE_COUNT",
    "COMPENDIUM_SUMMARY_LINE_LIMIT",
    "COMPENDIUM_TERMINATOR",
    "COMPENDIUM_TEXT_ARENA_SIZE",
    "CompendiumPackedProfile",
    "CompendiumProfileText",
    "CompendiumTextBuild",
    "build_compendium_text",
    "load_compendium_profiles",
]

