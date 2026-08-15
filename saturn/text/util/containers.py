"""Extract records with four declarative container shapes.

The container layer owns binary framing.  It emits only stable physical record
selectors, source-encoding names, and decoded reference text.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from .codecs import decode_text, read_units
from .config import EncodingCatalog, SourceEncoding
from .sources import SourceSpec

_HEX_RE = re.compile(r"0x[0-9a-f]+\Z")
_ID_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_PAGE_CLEAR = 0x8002
_PAGE_EDGES = frozenset({0x8002, 0x8003})
_PAYLOAD_OPS = frozenset({0x8006, 0x8007, *range(0x8010, 0x8024)})


@dataclass(frozen=True, slots=True)
class CorpusSeed:
    id: str
    source_encoding: str
    reference: str


@dataclass(frozen=True, order=True, slots=True)
class Region:
    file: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SourceExtraction:
    records: tuple[CorpusSeed, ...]
    regions: tuple[Region, ...]


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(
    value: Mapping[str, Any],
    required: set[str],
    context: str,
    *,
    optional: set[str] = frozenset(),
) -> None:
    actual = set(value)
    if not required <= actual or not actual <= required | optional:
        expected = sorted(required | optional)
        raise ValueError(f"{context} fields are {sorted(actual)}, expected {expected}")


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase identifier")
    return value


def _integer(value: Any, context: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{context} must be a {qualifier} integer")
    return value


def _hex(value: Any, context: str, *, limit: int | None = None) -> int:
    if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase 0x-prefixed hexadecimal")
    number = int(value, 16)
    if limit is not None and number >= limit:
        raise ValueError(f"{context} is outside its allowed range")
    return number


def _blob(name: Any, blobs: Mapping[str, bytes], context: str) -> tuple[str, bytes]:
    file_name = _identifier(name, context)
    try:
        return file_name, blobs[file_name]
    except KeyError as error:
        raise ValueError(f"{context} references unknown file {file_name!r}") from error


def _blob_set(
    names: Any, blobs: Mapping[str, bytes], context: str
) -> tuple[tuple[str, bytes], ...]:
    if not isinstance(names, list) or not names:
        raise ValueError(f"{context} must be a nonempty file-id array")
    output: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for index, name in enumerate(names):
        found = _blob(name, blobs, f"{context}[{index}]")
        if found[0] in seen:
            raise ValueError(f"{context} repeats file {found[0]!r}")
        seen.add(found[0])
        output.append(found)
    return tuple(output)


def _encoding(name: Any, catalog: EncodingCatalog, context: str) -> SourceEncoding:
    if not isinstance(name, str):
        raise ValueError(f"{context} must name a source encoding")
    try:
        return catalog.source(name)
    except ValueError as error:
        raise ValueError(f"{context}: {error}") from error


def _slice(data: bytes, start: int, size: int, context: str) -> bytes:
    end = start + size
    if start < 0 or end > len(data):
        raise ValueError(f"{context} exceeds its physical file")
    return data[start:end]


def _frame(
    raw: bytes,
    encoding: SourceEncoding,
    value: Any,
    context: str,
) -> tuple[bytes, int | None]:
    row = _object(value, f"{context}.framing")
    kind = row.get("type")
    if kind in {"none", "zero_padded", "zero_terminated"}:
        _fields(row, {"type"}, f"{context}.framing")
        code = None
    elif kind in {"terminated", "optional_terminated", "boundary"}:
        _fields(row, {"type", "code"}, f"{context}.framing")
        code = _hex(
            row["code"],
            f"{context}.framing.code",
            limit=1 << (encoding.unit_width * 8),
        )
    else:
        raise ValueError(f"{context}.framing.type is invalid")

    units = read_units(raw, encoding)
    if kind == "none" or kind == "boundary":
        visible = units
    elif kind == "zero_padded":
        end = len(units)
        while end and units[end - 1] == 0:
            end -= 1
        visible = units[:end]
    elif kind == "zero_terminated":
        if 0 not in units:
            raise ValueError(f"{context}: field has no zero terminator")
        end = units.index(0)
        if any(units[end + 1 :]):
            raise ValueError(f"{context}: nonzero data follows the zero terminator")
        visible = units[:end]
    else:
        assert code is not None
        occurrences = units.count(code)
        if kind == "terminated" and occurrences != 1:
            raise ValueError(f"{context}: expected exactly one {code:#x} terminator")
        if kind == "optional_terminated" and occurrences > 1:
            raise ValueError(f"{context}: expected at most one {code:#x} terminator")
        if not occurrences:
            if kind == "terminated":
                raise AssertionError("unreachable")
            if 0 in units:
                raise ValueError(f"{context}: full unterminated field contains padding")
            visible = units
        else:
            end = units.index(code)
            if any(units[end + 1 :]):
                raise ValueError(f"{context}: nonzero data follows the terminator")
            visible = units[:end]

    width = encoding.unit_width
    framed = b"".join(unit.to_bytes(width, "big") for unit in visible)
    return framed, code if kind == "boundary" else None


def _ranges(value: Any, context: str, count: int) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    output: set[int] = set()
    previous_end = -1
    for index, raw in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"{item_context} must contain an inclusive start and end")
        start = _integer(raw[0], f"{item_context}[0]")
        end = _integer(raw[1], f"{item_context}[1]")
        if start > end or start <= previous_end or end >= count:
            raise ValueError(f"{context} must be ordered, disjoint, and in range")
        output.update(range(start, end + 1))
        previous_end = end
    return frozenset(output)


def _override_map(
    value: Any,
    context: str,
    count: int,
    field: str,
) -> dict[int, str]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    output: dict[int, str] = {}
    for index, raw in enumerate(value):
        row_context = f"{context}[{index}]"
        row = _object(raw, row_context)
        _fields(row, {"messages", field}, row_context)
        selected = _ranges(row["messages"], f"{row_context}.messages", count)
        setting = row[field]
        if not isinstance(setting, str) or not setting:
            raise ValueError(f"{row_context}.{field} must be nonempty text")
        overlap = set(output) & selected
        if overlap:
            raise ValueError(f"{row_context} overlaps an earlier override")
        output.update({message: setting for message in selected})
    return output


def _has_payload(words: tuple[int, ...]) -> bool:
    return any(not (word & 0x8000) or word in _PAYLOAD_OPS for word in words)


def _split_eve_pages(
    words: tuple[int, ...], context: str
) -> tuple[tuple[int, ...], ...]:
    try:
        text_end = words.index(0x8000)
    except ValueError:
        text_end = len(words)
    pages: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    page_start = 0
    cursor = 0
    while cursor < text_end:
        if not (words[cursor] & 0x8000):
            cursor += 1
            continue
        run_start = cursor
        while cursor < text_end and words[cursor] & 0x8000:
            cursor += 1
        run = words[run_start:cursor]
        page_positions = [i for i, word in enumerate(run) if word in _PAGE_EDGES]
        if _PAGE_CLEAR not in run:
            continue
        first = run_start + page_positions[0]
        after_last = run_start + page_positions[-1] + 1
        if _has_payload(words[after_last:text_end]):
            if not _has_payload(words[page_start:first]):
                continue
            pages.append((words[page_start:first], words[first:after_last]))
            page_start = after_last
        else:
            pages.append((words[page_start:first], words[first:]))
            page_start = len(words)
            break
    if page_start < len(words) or not pages:
        content_end = text_end
        while content_end > page_start and words[content_end - 1] == 0x8003:
            content_end -= 1
        pages.append((words[page_start:content_end], words[content_end:]))
    reconstructed = tuple(
        word
        for content, boundary in pages
        for part in (content, boundary)
        for word in part
    )
    if reconstructed != words:
        raise ValueError(f"{context}: EVE page split is not lossless")
    return tuple(content for content, _boundary in pages)


def _eve_page_payload(words: tuple[int, ...]) -> tuple[int, ...]:
    """Remove a leading page-clear boundary from the decoded content view."""
    edge_end = 0
    while edge_end < len(words) and words[edge_end] in _PAGE_EDGES:
        edge_end += 1
    if _PAGE_CLEAR in words[:edge_end]:
        return words[edge_end:]
    return words


def _extract_eve(
    source: SourceSpec,
    config: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    catalog: EncodingCatalog,
    disc: str,
) -> SourceExtraction:
    context = f"source {source.name}"
    _fields(
        config,
        {
            "type",
            "file",
            "table_offset",
            "body_offset",
            "source_encoding",
            "source_encoding_overrides",
            "expected_messages",
            "expected_pages",
            "expected_body_bytes",
        },
        context,
    )
    file_name, data = _blob(config["file"], blobs, f"{context}.file")
    table_offset = _hex(config["table_offset"], f"{context}.table_offset")
    body_offset = _hex(config["body_offset"], f"{context}.body_offset")
    if not 0 <= table_offset < body_offset <= len(data):
        raise ValueError(f"{context}: EVE table/body offsets are outside the file")
    expected_messages = _integer(
        config["expected_messages"], f"{context}.expected_messages", positive=True
    )
    expected_pages = _integer(
        config["expected_pages"], f"{context}.expected_pages", positive=True
    )
    expected_body = _hex(
        config["expected_body_bytes"], f"{context}.expected_body_bytes"
    )

    pointers: list[int] = []
    cursor = table_offset
    while cursor + 2 <= body_offset:
        pointer = int.from_bytes(data[cursor : cursor + 2], "big")
        cursor += 2
        if pointer == 0xFFFF:
            break
        pointers.append(pointer)
    else:
        raise ValueError(f"{context}: EVE pointer table has no 0xffff sentinel")
    if len(pointers) != expected_messages:
        raise ValueError(
            f"{context}: found {len(pointers)} messages, expected {expected_messages}"
        )
    if pointers[0] != 0 or any(a >= b for a, b in pairwise(pointers)):
        raise ValueError(f"{context}: EVE pointers are not strict starts from zero")
    final_start = body_offset + pointers[-1] * 2
    final_end = None
    for offset in range(final_start, len(data) - 1, 2):
        if int.from_bytes(data[offset : offset + 2], "big") == 0x8000:
            final_end = offset + 2
            break
    if final_end is None:
        raise ValueError(f"{context}: final EVE message has no 0x8000 terminator")
    if any(data[final_end:]):
        raise ValueError(f"{context}: nonzero data follows the EVE body")
    if final_end - body_offset != expected_body:
        raise ValueError(
            f"{context}: body uses {final_end - body_offset:#x} bytes, "
            f"expected {expected_body:#x}"
        )

    default_encoding = _encoding(
        config["source_encoding"], catalog, f"{context}.source_encoding"
    )
    if default_encoding.unit_width != 2:
        raise ValueError(f"{context}: EVE records require a 16-bit source encoding")
    encoding_overrides = _override_map(
        config["source_encoding_overrides"],
        f"{context}.source_encoding_overrides",
        len(pointers),
        "source_encoding",
    )
    override_encodings = {
        index: _encoding(name, catalog, f"{context}.source_encoding_overrides")
        for index, name in encoding_overrides.items()
    }
    if any(encoding.unit_width != 2 for encoding in override_encodings.values()):
        raise ValueError(f"{context}: EVE overrides require 16-bit encodings")

    final_end_word = (final_end - body_offset) // 2
    ends = (*pointers[1:], final_end_word)
    records: list[CorpusSeed] = []
    page_count = 0
    for message_index, (start_word, end_word) in enumerate(zip(pointers, ends)):
        start = body_offset + start_word * 2
        count = end_word - start_word
        if count <= 0:
            raise ValueError(f"{context}: message {message_index} is empty")
        words = struct.unpack_from(f">{count}H", data, start)
        encoding = override_encodings.get(message_index, default_encoding)
        pages = _split_eve_pages(words, f"{context}: message {message_index}")
        for page_index, page_words in enumerate(pages):
            # Page numbers include structural/control-only pages so an inserted
            # or removed boundary cannot silently reground later records.  The
            # corpus itself contains only pages with a text payload.
            payload_words = _eve_page_payload(page_words)
            if not _has_payload(payload_words):
                continue
            raw = (
                struct.pack(f">{len(payload_words)}H", *payload_words)
                if payload_words
                else b""
            )
            records.append(
                CorpusSeed(
                    f"{disc}.{source.name}.m{message_index:04d}.p{page_index:02d}",
                    encoding.name,
                    decode_text(raw, encoding),
                )
            )
        page_count += len(pages)
    if page_count != expected_pages:
        raise ValueError(
            f"{context}: found {page_count} pages, expected {expected_pages}"
        )
    return SourceExtraction(tuple(records), (Region(file_name, 0, len(data)),))


def _extract_pointer_bank(
    source: SourceSpec,
    config: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    catalog: EncodingCatalog,
    disc: str,
) -> SourceExtraction:
    context = f"source {source.name}"
    _fields(
        config,
        {
            "type",
            "file",
            "table_offset",
            "table_end",
            "body_offset",
            "pointer_unit",
            "terminator",
            "source_encoding",
            "expected_records",
            "sentinel_offset",
        },
        context,
    )
    file_name, data = _blob(config["file"], blobs, f"{context}.file")
    encoding = _encoding(
        config["source_encoding"], catalog, f"{context}.source_encoding"
    )
    table_offset = _hex(config["table_offset"], f"{context}.table_offset")
    table_end = _hex(config["table_end"], f"{context}.table_end")
    body_offset = _hex(config["body_offset"], f"{context}.body_offset")
    if not 0 <= table_offset < table_end <= body_offset <= len(data):
        raise ValueError(f"{context}: invalid pointer-table bounds")
    multiplier = {"byte": 1, "word": 2}.get(config["pointer_unit"])
    if multiplier is None:
        raise ValueError(f"{context}.pointer_unit must be byte or word")
    terminator = _hex(
        config["terminator"],
        f"{context}.terminator",
        limit=1 << (encoding.unit_width * 8),
    )
    expected = _integer(
        config["expected_records"], f"{context}.expected_records", positive=True
    )
    expected_sentinel = _hex(config["sentinel_offset"], f"{context}.sentinel_offset")

    pointers: list[int] = []
    cursor = table_offset
    while cursor + 2 <= table_end:
        pointer = int.from_bytes(data[cursor : cursor + 2], "big")
        if pointer == 0xFFFF:
            break
        pointers.append(pointer)
        cursor += 2
    else:
        raise ValueError(f"{context}: pointer table has no 0xffff sentinel")
    if cursor != expected_sentinel:
        raise ValueError(
            f"{context}: sentinel is at {cursor:#x}, expected {expected_sentinel:#x}"
        )
    if len(pointers) != expected:
        raise ValueError(
            f"{context}: found {len(pointers)} records, expected {expected}"
        )
    if pointers[0] != 0 or any(a >= b for a, b in pairwise(pointers)):
        raise ValueError(f"{context}: pointers are not strict starts from zero")
    if any(data[cursor + 2 : body_offset]):
        raise ValueError(f"{context}: nonzero data follows the pointer sentinel")

    starts = [body_offset + pointer * multiplier for pointer in pointers]
    ends = (*starts[1:], len(data))
    records: list[CorpusSeed] = []
    for index, (start, end) in enumerate(zip(starts, ends)):
        raw = _slice(data, start, end - start, f"{context}: record {index}")
        units = read_units(raw, encoding)
        if not units or units[-1] != terminator or terminator in units[:-1]:
            raise ValueError(
                f"{context}: record {index} has invalid terminator framing"
            )
        visible = raw[: -encoding.unit_width]
        records.append(
            CorpusSeed(
                f"{disc}.{source.name}.p{index:04d}",
                encoding.name,
                decode_text(visible, encoding),
            )
        )
    return SourceExtraction(
        tuple(records), (Region(file_name, table_offset, len(data)),)
    )


def _extract_fixed_records(
    source: SourceSpec,
    config: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    catalog: EncodingCatalog,
    disc: str,
) -> SourceExtraction:
    context = f"source {source.name}"
    _fields(
        config,
        {"type", "blocks", "fields"},
        context,
        optional={"file", "files"},
    )
    has_file = "file" in config
    has_files = "files" in config
    if has_file == has_files:
        raise ValueError(f"{context} must declare exactly one of file or files")
    file_blobs = (
        (_blob(config["file"], blobs, f"{context}.file"),)
        if has_file
        else _blob_set(config["files"], blobs, f"{context}.files")
    )
    raw_blocks = config["blocks"]
    raw_fields = config["fields"]
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError(f"{context}.blocks must be a nonempty array")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError(f"{context}.fields must be a nonempty array")

    fields: list[tuple[str, int, int, SourceEncoding, Any]] = []
    field_names: set[str] = set()
    for index, raw_field in enumerate(raw_fields):
        field_context = f"{context}.fields[{index}]"
        row = _object(raw_field, field_context)
        _fields(
            row,
            {"name", "offset", "units", "source_encoding", "framing"},
            field_context,
        )
        name = _identifier(row["name"], f"{field_context}.name")
        if name in field_names:
            raise ValueError(f"{context}: duplicate fixed field {name!r}")
        field_names.add(name)
        fields.append(
            (
                name,
                _hex(row["offset"], f"{field_context}.offset"),
                _integer(row["units"], f"{field_context}.units", positive=True),
                _encoding(
                    row["source_encoding"], catalog, f"{field_context}.source_encoding"
                ),
                row["framing"],
            )
        )

    blocks: list[tuple[int, int, int, str]] = []
    for block_index, raw_block in enumerate(raw_blocks):
        block_context = f"{context}.blocks[{block_index}]"
        block = _object(raw_block, block_context)
        _fields(block, {"base", "count", "stride"}, block_context)
        base = _hex(block["base"], f"{block_context}.base")
        count = _integer(block["count"], f"{block_context}.count", positive=True)
        stride = _hex(block["stride"], f"{block_context}.stride")
        if stride <= 0:
            raise ValueError(f"{block_context}.stride must be positive")
        for name, offset, units, encoding, framing in fields:
            if offset + units * encoding.unit_width > stride:
                raise ValueError(f"{block_context}: field {name!r} exceeds its stride")
        blocks.append((base, count, stride, block_context))

    records: list[CorpusSeed] = []
    regions: list[Region] = []
    for file_name, data in file_blobs:
        selector = f".{file_name}" if has_files else ""
        for base, count, stride, block_context in blocks:
            for record_index in range(count):
                record_base = base + record_index * stride
                for name, offset, units, encoding, framing in fields:
                    start = record_base + offset
                    record_context = (
                        f"{block_context}: {file_name} record {record_index}.{name}"
                    )
                    raw = _slice(
                        data,
                        start,
                        units * encoding.unit_width,
                        record_context,
                    )
                    visible, boundary = _frame(
                        raw,
                        encoding,
                        framing,
                        record_context,
                    )
                    if boundary is not None:
                        raise ValueError(
                            f"{block_context}: fixed fields cannot use boundary framing"
                        )
                    records.append(
                        CorpusSeed(
                            f"{disc}.{source.name}{selector}.o{start:06x}.{name}",
                            encoding.name,
                            decode_text(visible, encoding),
                        )
                    )
                    regions.append(Region(file_name, start, start + len(raw)))
    ordered = sorted(regions)
    for previous, current in pairwise(ordered):
        if previous.file == current.file and current.start < previous.end:
            raise ValueError(f"{context}: fixed fields overlap")
    return SourceExtraction(tuple(records), tuple(regions))


def _record_location(
    raw_location: Any,
    *,
    default_file: str,
    encoding: SourceEncoding,
    framing: Any,
    join: str,
    blobs: Mapping[str, bytes],
    context: str,
) -> tuple[
    str, tuple[bytes, ...], tuple[Region, ...], tuple[tuple[str, int, int], ...]
]:
    location = _object(raw_location, context)
    _fields(location, {"spans"}, context)
    raw_spans = location["spans"]
    if not isinstance(raw_spans, list) or not raw_spans:
        raise ValueError(f"{context}.spans must be a nonempty array")
    if join not in {"newline", "none"}:
        raise ValueError(f"{context}: join must be newline or none")
    texts: list[str] = []
    framed_parts: list[bytes] = []
    regions: list[Region] = []
    signature: list[tuple[str, int, int]] = []
    for index, raw_span in enumerate(raw_spans):
        span_context = f"{context}.spans[{index}]"
        span = _object(raw_span, span_context)
        _fields(span, {"offset", "units"}, span_context, optional={"file"})
        file_name, data = _blob(
            span.get("file", default_file), blobs, f"{span_context}.file"
        )
        offset = _hex(span["offset"], f"{span_context}.offset")
        units = _integer(span["units"], f"{span_context}.units", positive=True)
        size = units * encoding.unit_width
        raw = _slice(data, offset, size, span_context)
        visible, boundary = _frame(raw, encoding, framing, span_context)
        region_end = offset + size
        if boundary is not None:
            boundary_raw = _slice(
                data, region_end, encoding.unit_width, f"{span_context} boundary"
            )
            actual_boundary = int.from_bytes(boundary_raw, "big")
            if actual_boundary != boundary:
                raise ValueError(
                    f"{span_context}: boundary is {actual_boundary:#x}, expected "
                    f"{boundary:#x}"
                )
            region_end += encoding.unit_width
        texts.append(decode_text(visible, encoding))
        framed_parts.append(visible)
        regions.append(Region(file_name, offset, region_end))
        signature.append((file_name, offset, size))
    separator = "{n}" if join == "newline" else ""
    return separator.join(texts), tuple(framed_parts), tuple(regions), tuple(signature)


def _extract_addressed(
    source: SourceSpec,
    config: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    catalog: EncodingCatalog,
    disc: str,
) -> SourceExtraction:
    context = f"source {source.name}"
    _fields(
        config,
        {"type", "file", "default_source_encoding", "tables", "records"},
        context,
    )
    default_file, _data = _blob(config["file"], blobs, f"{context}.file")
    default_encoding = _encoding(
        config["default_source_encoding"], catalog, f"{context}.default_source_encoding"
    )
    raw_tables = config["tables"]
    raw_records = config["records"]
    if not isinstance(raw_tables, list) or not isinstance(raw_records, list):
        raise ValueError(f"{context}.tables and .records must be arrays")
    if not raw_tables and not raw_records:
        raise ValueError(f"{context} has no addressed text")

    output: list[CorpusSeed] = []
    regions: list[Region] = []
    claims: dict[str, list[tuple[int, int, str]]] = {}

    def claim(
        owned: list[Region] | tuple[Region, ...], owner: str, fork_of: str | None = None
    ) -> None:
        for region in owned:
            for prior_start, prior_end, prior_owner in claims.get(region.file, []):
                if region.start < prior_end and prior_start < region.end:
                    exact_fork = (
                        fork_of == prior_owner
                        and region.start == prior_start
                        and region.end == prior_end
                    )
                    if not exact_fork:
                        raise ValueError(
                            f"{context}: {owner} overlaps {prior_owner} in "
                            f"{region.file}"
                        )
            claims.setdefault(region.file, []).append((region.start, region.end, owner))

    table_names: set[str] = set()
    for table_index, raw_table in enumerate(raw_tables):
        table_context = f"{context}.tables[{table_index}]"
        table = _object(raw_table, table_context)
        _fields(
            table,
            {"name", "count", "framing", "require_identical_bytes", "locations"},
            table_context,
            optional={"source_encoding"},
        )
        name = _identifier(table["name"], f"{table_context}.name")
        if name in table_names:
            raise ValueError(f"{context}: duplicate addressed table {name!r}")
        table_names.add(name)
        count = _integer(table["count"], f"{table_context}.count", positive=True)
        encoding = _encoding(
            table.get("source_encoding", default_encoding.name),
            catalog,
            f"{table_context}.source_encoding",
        )
        identical = table["require_identical_bytes"]
        if type(identical) is not bool:
            raise ValueError(f"{table_context}.require_identical_bytes must be boolean")
        raw_locations = table["locations"]
        if not isinstance(raw_locations, list) or not raw_locations:
            raise ValueError(f"{table_context}.locations must be a nonempty array")
        locations: list[tuple[str, bytes, int, int, int]] = []
        for location_index, raw_location in enumerate(raw_locations):
            location_context = f"{table_context}.locations[{location_index}]"
            location = _object(raw_location, location_context)
            _fields(
                location,
                {"base", "stride", "units"},
                location_context,
                optional={"file"},
            )
            file_name, data = _blob(
                location.get("file", default_file), blobs, f"{location_context}.file"
            )
            locations.append(
                (
                    file_name,
                    data,
                    _hex(location["base"], f"{location_context}.base"),
                    _hex(location["stride"], f"{location_context}.stride"),
                    _integer(
                        location["units"], f"{location_context}.units", positive=True
                    ),
                )
            )
        for record_index in range(count):
            reference: str | None = None
            reference_raw: bytes | None = None
            table_regions: list[Region] = []
            for location_index, (file_name, data, base, stride, units) in enumerate(
                locations
            ):
                start = base + record_index * stride
                raw = _slice(
                    data,
                    start,
                    units * encoding.unit_width,
                    f"{table_context}: record {record_index} copy {location_index}",
                )
                visible, boundary = _frame(
                    raw,
                    encoding,
                    table["framing"],
                    f"{table_context}: record {record_index} copy {location_index}",
                )
                end = start + len(raw)
                if boundary is not None:
                    boundary_raw = _slice(
                        data, end, encoding.unit_width, f"{table_context} boundary"
                    )
                    if int.from_bytes(boundary_raw, "big") != boundary:
                        raise ValueError(
                            f"{table_context}: record {record_index} has wrong boundary"
                        )
                    end += encoding.unit_width
                text = decode_text(visible, encoding)
                if reference is None:
                    reference, reference_raw = text, visible
                elif text != reference:
                    raise ValueError(
                        f"{table_context}: record {record_index} mirrors differ"
                    )
                elif identical and visible != reference_raw:
                    raise ValueError(
                        f"{table_context}: record {record_index} mirror bytes differ"
                    )
                table_regions.append(Region(file_name, start, end))
            assert reference is not None
            owner = f"table {name}[{record_index}]"
            claim(table_regions, owner)
            regions.extend(table_regions)
            output.append(
                CorpusSeed(
                    f"{disc}.{source.name}.{name}.r{record_index:04d}",
                    encoding.name,
                    reference,
                )
            )

    interim: list[
        tuple[
            str,
            str,
            SourceEncoding,
            str,
            tuple[Region, ...],
            tuple[tuple[str, int, int], ...],
            str | None,
        ]
    ] = []
    record_names: set[str] = set()
    signatures: dict[str, tuple[tuple[str, int, int], ...]] = {}
    for record_index, raw_record in enumerate(raw_records):
        record_context = f"{context}.records[{record_index}]"
        record = _object(raw_record, record_context)
        _fields(
            record,
            {"name", "locations"},
            record_context,
            optional={
                "source_encoding",
                "framing",
                "join",
                "require_identical_bytes",
                "fork_of",
            },
        )
        name = _identifier(record["name"], f"{record_context}.name")
        if name in record_names:
            raise ValueError(f"{context}: duplicate addressed record {name!r}")
        record_names.add(name)
        encoding = _encoding(
            record.get("source_encoding", default_encoding.name),
            catalog,
            f"{record_context}.source_encoding",
        )
        framing = record.get("framing", {"type": "none"})
        join = record.get("join", "newline")
        identical = record.get("require_identical_bytes", False)
        if type(identical) is not bool:
            raise ValueError(
                f"{record_context}.require_identical_bytes must be boolean"
            )
        locations = record["locations"]
        if not isinstance(locations, list) or not locations:
            raise ValueError(f"{record_context}.locations must be a nonempty array")
        reference: str | None = None
        reference_raw: tuple[bytes, ...] | None = None
        record_regions: list[Region] = []
        signature: tuple[tuple[str, int, int], ...] | None = None
        for location_index, location in enumerate(locations):
            text, visible, found_regions, found_signature = _record_location(
                location,
                default_file=default_file,
                encoding=encoding,
                framing=framing,
                join=join,
                blobs=blobs,
                context=f"{record_context}.locations[{location_index}]",
            )
            if reference is None:
                reference, reference_raw, signature = text, visible, found_signature
            elif text != reference:
                raise ValueError(
                    f"{record_context}: mirrored locations decode differently"
                )
            elif identical and visible != reference_raw:
                raise ValueError(f"{record_context}: mirrored location bytes differ")
            record_regions.extend(found_regions)
        assert reference is not None and signature is not None
        fork_of = record.get("fork_of")
        if fork_of is not None:
            fork_name = _identifier(fork_of, f"{record_context}.fork_of")
            if fork_name not in signatures or signatures[fork_name] != signature:
                raise ValueError(
                    f"{record_context}.fork_of must name an identical earlier location"
                )
        signatures[name] = signature
        claim(record_regions, name, fork_of)
        first_offset = signature[0][1]
        selector = f"o{first_offset:06x}"
        interim.append(
            (
                selector,
                name,
                encoding,
                reference,
                tuple(record_regions),
                signature,
                fork_of,
            )
        )

    selector_counts: dict[str, int] = {}
    for selector, *_rest in interim:
        selector_counts[selector] = selector_counts.get(selector, 0) + 1
    for (
        selector,
        name,
        encoding,
        reference,
        record_regions,
        _signature,
        _fork_of,
    ) in interim:
        count = selector_counts[selector]
        suffix = f".{name}" if count > 1 else ""
        output.append(
            CorpusSeed(
                f"{disc}.{source.name}.{selector}{suffix}",
                encoding.name,
                reference,
            )
        )
        regions.extend(record_regions)
    return SourceExtraction(tuple(output), tuple(regions))


def extract_source(
    source: SourceSpec,
    blobs: Mapping[str, bytes],
    catalog: EncodingCatalog,
    disc: str,
) -> SourceExtraction:
    config = source.container
    kind = config["type"]
    if kind == "eve":
        return _extract_eve(source, config, blobs, catalog, disc)
    if kind == "pointer_bank":
        return _extract_pointer_bank(source, config, blobs, catalog, disc)
    if kind == "fixed_records":
        return _extract_fixed_records(source, config, blobs, catalog, disc)
    if kind == "addressed":
        return _extract_addressed(source, config, blobs, catalog, disc)
    raise AssertionError(f"unhandled container type {kind!r}")


def merge_regions(regions: tuple[Region, ...] | list[Region]) -> tuple[Region, ...]:
    """Return a deterministic union used for owned-byte identity checks."""
    output: list[Region] = []
    for region in sorted(regions):
        if region.start < 0 or region.end <= region.start:
            raise ValueError(f"invalid owned region {region}")
        if output and output[-1].file == region.file and region.start <= output[-1].end:
            previous = output[-1]
            output[-1] = Region(
                previous.file, previous.start, max(previous.end, region.end)
            )
        else:
            output.append(region)
    return tuple(output)
