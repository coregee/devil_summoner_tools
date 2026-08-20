"""Pure contracts shared by the cloned EVENT and MSGR dialogue windows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.sh2 import Assembly, AssemblyError, assemble_file
from text.util.event_repack import FontMetrics


EVENT_BANK_NAMES = (
    "MESFILE.EVE",
    "EVFILE_0.EVE",
    "EVFILE_1.EVE",
    "EVFILE_2.EVE",
)


@dataclass(frozen=True, slots=True)
class EventWindowAssembly:
    data: bytes
    labels: Mapping[str, int]


def assemble_checked(
    source: Path,
    address: int,
    symbols: Mapping[str, int],
    context: str,
) -> Assembly:
    try:
        result = assemble_file(source, address, dict(symbols))
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"{context}: {error}") from error
    if result.warnings:
        raise ValueError(f"{context}: assembly warnings: {result.warnings}")
    return result


def build_advance_payload(
    source: Path,
    address: int,
    symbols: Mapping[str, int],
    font12_widths: bytes,
    context: str,
) -> bytes:
    """Link the shared advance code to its immediate FONT12 width table."""
    code = assemble_checked(source, address, symbols, context)
    if code.labels.get("font12_widths") != address + len(code.data):
        raise ValueError(f"{context}: FONT12 width-table link changed")
    return code.data + font12_widths


def font12_widths(metrics: FontMetrics, *, space_code: int = 267) -> bytes:
    """Build the complete byte-indexed FONT12 width table used by both VMs."""
    output = bytearray(space_code + 1)
    for glyph in metrics.glyphs:
        if not 0 <= glyph.code < len(output) or not 0 <= glyph.advance <= 0xFF:
            raise ValueError("FONT12 metrics exceed the event-window width contract")
        output[glyph.code] = glyph.advance
    output[space_code] = output[0]
    return bytes(output)


def font16_layout(metrics_path: Path) -> tuple[int, int]:
    """Return the generated FONT16 code limit and appended width-table offset."""
    try:
        document = _object(
            json.loads(
                metrics_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicates,
            ),
            str(metrics_path),
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing event-window metrics: {metrics_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{metrics_path}: invalid JSON") from error
    table = _object(document.get("width_table"), f"{metrics_path}.width_table")
    code_limit = table.get("code_limit")
    storage_glyph = table.get("storage_glyph")
    if (
        document.get("version") != 2
        or document.get("font") != "FONT16.FON"
        or document.get("complete") is not True
        or type(code_limit) is not int
        or type(storage_glyph) is not int
        or code_limit <= 0
        or storage_glyph <= 0
    ):
        raise ValueError("FONT16 metrics have an invalid runtime width layout")
    return code_limit, storage_glyph * 32


def font_signature(font12_path: Path, font16_path: Path) -> tuple[int, int]:
    """Find one stable byte that distinguishes the live FONT12/FONT16 atlas."""
    try:
        font12 = font12_path.read_bytes()
        font16 = font16_path.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(
            f"missing generated event-window font: {error.filename}"
        ) from error
    record_start = 11 * 32
    candidates = (
        enumerate(
            zip(
                font12[record_start : record_start + 32],
                font16[record_start : record_start + 32],
            ),
            record_start,
        ),
        enumerate(zip(font12, font16)),
    )
    for rows in candidates:
        for offset, (font12_byte, font16_byte) in rows:
            if font12_byte != font16_byte and 0 < font12_byte < 0x80:
                return offset, font12_byte
    raise ValueError("FONT12 and FONT16 have no usable runtime signature")


def compact_width_tables(metrics: FontMetrics) -> tuple[bytes, int, bytes]:
    glyphs = sorted(metrics.glyphs, key=lambda glyph: glyph.code)
    if len(glyphs) < 2:
        raise ValueError("event-window FONT16 metrics need at least two glyphs")
    gap_size, split = max(
        (right.code - left.code - 1, index)
        for index, (left, right) in enumerate(zip(glyphs, glyphs[1:]), 1)
    )
    if gap_size <= 0:
        raise ValueError("event-window FONT16 metrics have no compact-table gap")
    low_glyphs = glyphs[:split]
    high_glyphs = glyphs[split:]
    low = bytearray(low_glyphs[-1].code + 1)
    high_start = high_glyphs[0].code
    high = bytearray(high_glyphs[-1].code - high_start + 1)
    for glyph in low_glyphs:
        low[glyph.code] = glyph.advance
    for glyph in high_glyphs:
        high[glyph.code - high_start] = glyph.advance
    if len(low) > 0x7F or len(high) > 0x7F:
        raise ValueError("event-window compact width tables exceed SH-2 immediates")
    return bytes(low), high_start, bytes(high)


def build_menu_payload(
    source: Path,
    address: int,
    metrics16: FontMetrics,
    font12_widths: bytes,
    symbols: Mapping[str, int],
    context: str,
) -> bytes:
    """Link the shared raw-menu drawer to compact FONT16/FONT12 tables."""
    low, high_start, high = compact_width_tables(metrics16)
    base_symbols = {
        **symbols,
        "FONT12_CODE_LIMIT": len(font12_widths),
        "LOW_TABLE_LENGTH": len(low),
        "HIGH_TABLE_LENGTH": len(high),
        "HIGH_START": high_start,
        "LOW_TABLE": 0,
        "FONT12_TABLE": 0,
    }
    probe = assemble_checked(source, address, base_symbols, context)
    table_address = probe.labels["table_data"]
    final_symbols = {
        **base_symbols,
        "LOW_TABLE": table_address + len(high),
        "FONT12_TABLE": table_address + len(high) + len(low),
    }
    code = assemble_checked(source, address, final_symbols, context)
    if code.labels.get("table_data") != table_address:
        raise ValueError(f"{context}: linked table address changed code layout")
    payload = bytearray(code.data)
    payload.extend(high)
    payload.extend(low)
    payload.extend(font12_widths)
    payload.extend(bytes((-len(payload)) % 4))
    return bytes(payload)


def build_packed_fetch_payload(
    source: Path,
    address: int,
    dictionary: bytes,
    *,
    return_code: int,
    return_zero: int,
    context: str,
) -> bytes:
    """Link the shared packed fetcher to dictionary data and private state."""
    symbols = {
        "STATE": address,
        "DICTIONARY": address,
        "RETURN_CODE": return_code,
        "RETURN_ZERO": return_zero,
    }
    probe = assemble_checked(source, address, symbols, context)
    dictionary_address = (address + len(probe.data) + 3) & ~3
    state_address = (dictionary_address + len(dictionary) + 3) & ~3
    code = assemble_checked(
        source,
        address,
        {
            **symbols,
            "DICTIONARY": dictionary_address,
            "STATE": state_address,
        },
        context,
    )
    payload = bytearray(code.data)
    payload.extend(bytes(dictionary_address - address - len(payload)))
    payload.extend(dictionary)
    payload.extend(bytes(state_address - address - len(payload)))
    payload.extend(bytes(16))
    return bytes(payload)


def build_two_glyph_payload(
    source: Path,
    address: int,
    *,
    original_update: int,
    visible_blitter: int,
    tail_continue: int,
    context: str,
) -> EventWindowAssembly:
    """Link update/blit/tail entry points and the private visible-count byte."""
    symbols = {
        "ORIGINAL_UPDATE": original_update,
        "VISIBLE_BLITTER": visible_blitter,
        "VISIBLE_COUNT": address,
        "TAIL_CONTINUE": tail_continue,
    }
    probe = assemble_checked(source, address, symbols, context)
    state_address = (address + len(probe.data) + 3) & ~3
    code = assemble_checked(
        source,
        address,
        {**symbols, "VISIBLE_COUNT": state_address},
        context,
    )
    if len(code.data) != len(probe.data):
        raise ValueError(f"{context}: state placement changed code size")
    payload = bytearray(code.data)
    payload.extend(bytes(state_address - address - len(payload)))
    payload.append(0)
    return EventWindowAssembly(bytes(payload), MappingProxyType(code.labels))


def build_absolute_jump(
    source: Path,
    address: int,
    target: int,
    context: str,
) -> bytes:
    return assemble_checked(source, address, {"TARGET": target}, context).data


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing event-window input: {path}") from error


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def validate_event_text_build(
    build_path: Path,
    generated_root: Path,
    codec_sha256: str,
    runtime_table_sha256: str,
    font16_metrics_sha256: str,
    *,
    expected_records: int = 2028,
) -> tuple[Path, ...]:
    """Validate the exact packed EVE generation consumed by both overlay VMs.

    The runtime decoder is meaningful only with the same four banks and codec
    generation. Returning every file read lets each surface publish complete
    freshness provenance without depending on another surface module.
    """
    try:
        document = _object(
            json.loads(
                build_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicates,
            ),
            str(build_path),
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing event-window text build: {build_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{build_path}: invalid JSON") from error

    fields = {
        "version",
        "surface",
        "codec_sha256",
        "runtime_table_sha256",
        "font16_metrics_sha256",
        "records",
        "outputs",
    }
    if set(document) != fields:
        raise ValueError(f"{build_path}: invalid event text-build fields")
    if (
        document["version"] != 1
        or document["surface"] != "event.dialogue"
        or document["codec_sha256"] != codec_sha256
        or document["runtime_table_sha256"] != runtime_table_sha256
        or document["font16_metrics_sha256"] != font16_metrics_sha256
        or document["records"] != expected_records
    ):
        raise ValueError("general EVENT text build is stale for this dialogue runtime")

    outputs = _object(document["outputs"], f"{build_path}.outputs")
    if set(outputs) != set(EVENT_BANK_NAMES):
        raise ValueError("general EVENT text build has the wrong output set")
    paths = tuple(generated_root / name for name in EVENT_BANK_NAMES)
    page_count = 0
    for path in paths:
        row = _object(outputs[path.name], f"{build_path}.outputs.{path.name}")
        if set(row) != {"sha256", "messages", "pages", "body_bytes"} or any(
            type(row[name]) is not int or row[name] <= 0
            for name in ("messages", "pages", "body_bytes")
        ):
            raise ValueError(f"{build_path}.outputs.{path.name} is malformed")
        expected = row.get("sha256")
        if not isinstance(expected, str) or file_sha256(path) != expected:
            raise ValueError(f"generated {path.name} does not match its text build")
        page_count += int(row["pages"])
    if page_count != expected_records:
        raise ValueError("general EVENT text build record/page count is inconsistent")
    return (build_path, *paths)
