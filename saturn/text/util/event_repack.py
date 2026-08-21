"""Compile the authored general-event surface into the four Saturn EVE banks."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .assets import (
    load_bound_translations,
    load_physical_records,
)
from .event_codec import EventDictionary
from .sources import SourceManifest
from .tokens import Named, Raw, Text, parse_tokens


GENERAL_EVENT_SOURCES = ("mesfile", "evfile_0", "evfile_1", "evfile_2")
SHOP_EVENT_SOURCES = ("shopsmp",)
EVENT_INSERT_CODES = {
    "first_name": 0x8006,
    "last_name": 0x8007,
    "drink_name": 0x8017,
    "item_name": 0x8018,
    "demon_name": 0x8019,
    "ward": 0x801B,
    "city": 0x801C,
    "race": 0x801F,
    "event_id": 0x8022,
    "codename": 0x8023,
}
NAMED_WORDS = {
    **EVENT_INSERT_CODES,
    "WAIT": 0x8003,
    "NL": 0x8004,
    "yen_symbol": 0x00C0,
    "mag_symbol": 0x00C1,
    "white_square": 0x00C0,
    "square_symbol": 0x00C0,
    "heart_symbol": 0x0105,
    "happy_symbol": 0x0106,
    "maru_symbol": 0x0106,
    "circle_symbol": 0x010A,
    "latin_space": 0x010B,
    "plus_symbol": 0x010C,
    "minus_symbol": 0x010D,
    "times_symbol": 0x010E,
}
NORMALIZE_CHARACTERS = {
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "—": "-",
    "–": "-",
    "…": "...",
    "é": "e",
    "　": " ",
    " ": " ",
}
_PUNCTUATION_SPACE_RE = re.compile(r"([.!?])([A-Za-z{])")
_PHYSICAL_ID_RE = re.compile(
    r"game\.([a-z0-9_]+)\.m([0-9]{4})\.p([0-9]{2})\Z"
)


def _normalize_english(value: str) -> str:
    for source, replacement in NORMALIZE_CHARACTERS.items():
        value = value.replace(source, replacement)
    value = value.replace("{n}", "\n")
    value = "\n".join(" ".join(line.split()) for line in value.split("\n"))
    return _PUNCTUATION_SPACE_RE.sub(r"\1 \2", value)


@dataclass(frozen=True, slots=True)
class Glyph:
    text: str
    code: int
    advance: int
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FontMetrics:
    font: str
    glyphs: tuple[Glyph, ...]

    @classmethod
    def load(cls, path: Path) -> "FontMetrics":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"missing generated font metrics: {path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}: invalid JSON") from error
        if document.get("version") != 2 or not document.get("complete"):
            raise ValueError(f"{path}: incomplete or unsupported font metrics")
        try:
            glyphs = tuple(
                Glyph(
                    row["text"],
                    row["code"],
                    row["advance"],
                    tuple(row.get("aliases", ())),
                )
                for row in document["glyphs"]
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"{path}: malformed glyph metrics") from error
        if (
            not glyphs
            or len({glyph.code for glyph in glyphs}) != len(glyphs)
            or any(not 1 <= glyph.advance <= 0xFF for glyph in glyphs)
        ):
            raise ValueError(f"{path}: invalid glyph metrics")
        return cls(document["font"], glyphs)

    @property
    def by_text(self) -> dict[str, Glyph]:
        output = self.output_by_text
        for glyph in self.glyphs:
            for value in glyph.aliases:
                output.setdefault(value, glyph)
        return output

    @property
    def output_by_text(self) -> dict[str, Glyph]:
        """Return only glyphs actually present in the rebuilt font."""
        output: dict[str, Glyph] = {}
        for glyph in self.glyphs:
            output.setdefault(glyph.text, glyph)
        return output

    def _segment(self, value: str, mapping: dict[str, Glyph]) -> tuple[Glyph, ...]:
        compounds = tuple(
            sorted(
                (
                    (text, glyph)
                    for text, glyph in mapping.items()
                    if len(text) > 1
                ),
                key=lambda item: (-len(item[0]), item[1].code),
            )
        )
        output: list[Glyph] = []
        position = 0
        while position < len(value):
            compound = next(
                (
                    (text, glyph)
                    for text, glyph in compounds
                    if value.startswith(text, position)
                ),
                None,
            )
            if compound is not None:
                text, glyph = compound
                output.append(glyph)
                position += len(text)
                continue
            try:
                output.append(mapping[value[position]])
            except KeyError as error:
                raise ValueError(
                    f"unsupported {self.font} translation character "
                    f"{value[position]!r}"
                ) from error
            position += 1
        return tuple(output)

    def segment(self, value: str) -> tuple[Glyph, ...]:
        return self._segment(value, self.by_text)

    def segment_output(self, value: str) -> tuple[Glyph, ...]:
        """Segment translated output without accepting replaced source aliases."""
        return self._segment(value, self.output_by_text)

    def measure_output(self, value: str) -> int:
        return self.measure(value)

    def measure(self, value: str) -> int:
        width = 0
        for token in parse_tokens(value):
            if isinstance(token, Text):
                width += sum(
                    glyph.advance for glyph in self.segment_output(token.value)
                )
            elif isinstance(token, Raw) and token.kind == "GLYPH":
                width += 16
            elif isinstance(token, Named) and token.name in {
                "yen_symbol",
                "mag_symbol",
                "white_square",
                "square_symbol",
                "heart_symbol",
                "happy_symbol",
                "maru_symbol",
                "circle_symbol",
                "latin_space",
                "plus_symbol",
                "minus_symbol",
                "times_symbol",
            }:
                width += 16
            else:
                # The live first/last/codename fields accept eight characters.
                # This matches the mature renderer's conservative wrap reserve.
                width += 80
        return width

    def encode(
        self,
        value: str,
        *,
        dictionary: EventDictionary | None,
    ) -> list[int]:
        output: list[int] = []
        normalized = _normalize_english(value)
        for line_index, line in enumerate(normalized.split("\n")):
            if line_index:
                output.append(0x8001)
            for token in parse_tokens(line):
                if isinstance(token, Text):
                    codes = [
                        glyph.code for glyph in self.segment_output(token.value)
                    ]
                    output.extend(
                        dictionary.encode_codes(codes)
                        if dictionary is not None
                        else codes
                    )
                elif isinstance(token, Raw):
                    if token.width != 2:
                        raise ValueError("EVENT output requires 16-bit raw tokens")
                    output.append(token.value)
                else:
                    try:
                        output.append(NAMED_WORDS[token.name])
                    except KeyError as error:
                        raise ValueError(
                            f"unsupported EVENT token {{{token.name}}}"
                        ) from error
        return output


@dataclass(frozen=True, slots=True)
class EveMessage:
    index: int
    words: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EveBank:
    table_offset: int
    body_offset: int
    body_size: int
    messages: tuple[EveMessage, ...]

    @classmethod
    def parse(cls, data: bytes, table_offset: int, body_offset: int) -> "EveBank":
        if not 0 <= table_offset < body_offset <= len(data):
            raise ValueError("EVE table/body offsets lie outside the file")
        pointers: list[int] = []
        cursor = table_offset
        while cursor + 2 <= body_offset:
            pointer = int.from_bytes(data[cursor : cursor + 2], "big")
            cursor += 2
            if pointer == 0xFFFF:
                break
            pointers.append(pointer)
        else:
            raise ValueError("EVE pointer table has no 0xffff sentinel")
        if (
            not pointers
            or pointers[0] != 0
            or any(left >= right for left, right in zip(pointers, pointers[1:]))
        ):
            raise ValueError("EVE pointers are not strict starts from zero")
        final_start = body_offset + pointers[-1] * 2
        final_end = next(
            (
                offset + 2
                for offset in range(final_start, len(data) - 1, 2)
                if int.from_bytes(data[offset : offset + 2], "big") == 0x8000
            ),
            None,
        )
        if final_end is None or any(data[final_end:]):
            raise ValueError("EVE final message has no clean 0x8000 boundary")
        final_end_word = (final_end - body_offset) // 2
        ends = (*pointers[1:], final_end_word)
        messages = tuple(
            EveMessage(
                index,
                struct.unpack_from(
                    f">{end - start}H", data, body_offset + start * 2
                ),
            )
            for index, (start, end) in enumerate(zip(pointers, ends))
        )
        return cls(table_offset, body_offset, final_end - body_offset, messages)

    def rebuild(self, source: bytes, words_by_message: tuple[tuple[int, ...], ...]) -> bytes:
        if len(words_by_message) != len(self.messages):
            raise ValueError("EVE rebuild changed the message count")
        pointers: list[int] = []
        body = bytearray()
        for index, words in enumerate(words_by_message):
            if not words or any(not 0 <= word <= 0xFFFF for word in words):
                raise ValueError(f"EVE message {index} is invalid")
            pointer = len(body) // 2
            if pointer > 0xFFFF:
                raise ValueError("EVE pointer exceeds a 16-bit word offset")
            pointers.append(pointer)
            body.extend(struct.pack(f">{len(words)}H", *words))
        if words_by_message[-1][-1] != 0x8000:
            raise ValueError("EVE final message lost its terminator")
        capacity = len(source) - self.body_offset
        if len(body) > capacity:
            raise ValueError(f"EVE body needs {len(body)} bytes; capacity is {capacity}")
        table_size = (len(pointers) + 1) * 2
        if table_size > self.body_offset - self.table_offset:
            raise ValueError("EVE pointer table exceeds its reserved region")
        output = bytearray(source)
        for index, pointer in enumerate(pointers):
            struct.pack_into(">H", output, self.table_offset + index * 2, pointer)
        struct.pack_into(">H", output, self.table_offset + len(pointers) * 2, 0xFFFF)
        output[self.body_offset : self.body_offset + len(body)] = body
        old_end = self.body_offset + self.body_size
        output[self.body_offset + len(body) : old_end] = bytes(
            max(0, self.body_size - len(body))
        )
        rebuilt = EveBank.parse(bytes(output), self.table_offset, self.body_offset)
        if tuple(message.words for message in rebuilt.messages) != words_by_message:
            raise ValueError("rebuilt EVE bank did not round-trip")
        return bytes(output)


def _terminator_suffix(words: tuple[int, ...]) -> tuple[int, ...]:
    try:
        return words[words.index(0x8000) :]
    except ValueError:
        return (0x8000,)


def _with_terminator(words: list[int], original: tuple[int, ...]) -> tuple[int, ...]:
    output = [word for word in words if word != 0x8000]
    output.extend(_terminator_suffix(original))
    return tuple(output)


def _page_structure(
    words: tuple[int, ...],
) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...]]:
    try:
        words = words[: words.index(0x8000) + 1]
    except ValueError:
        pass
    glyphs = [0]
    breaks: list[list[int]] = [[]]
    position = 0
    while position < len(words):
        word = words[position]
        if word & 0x8000:
            run: list[int] = []
            while position < len(words) and words[position] & 0x8000:
                run.append(words[position])
                position += 1
            page_break = [value for value in run if value in (0x8002, 0x8003)]
            later_payload = any(not (later & 0x8000) for later in words[position:])
            if page_break and (0x8002 in run or not later_payload):
                breaks[-1] = page_break
                if 0x8002 in run and later_payload:
                    glyphs.append(0)
                    breaks.append([])
        else:
            glyphs[-1] += 1
            position += 1
    return tuple(glyphs), tuple(tuple(row) for row in breaks)


def _source_page_count(words: tuple[int, ...]) -> int:
    """Count extraction pages without treating a leading clear as an empty page."""
    glyphs, breaks = _page_structure(words)
    if len(glyphs) > 1 and glyphs[0] == 0 and 0x8002 in breaks[0]:
        return len(glyphs) - 1
    return len(glyphs)


def _wrap_lines(text: str, metrics: FontMetrics) -> list[str]:
    lines: list[str] = []
    for explicit_line in _normalize_english(text).split("\n"):
        words = [word for word in explicit_line.split(" ") if word]
        current: list[str] = []
        for word in words:
            candidate = " ".join((*current, word))
            if current and metrics.measure(candidate) > 300:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        elif not words:
            lines.append("")
    return lines


def _encode_page_lines(
    lines: list[str], metrics: FontMetrics, dictionary: EventDictionary | None
) -> list[int]:
    output: list[int] = []
    for index, line in enumerate(lines):
        if index:
            output.append(0x8001)
        output.extend(metrics.encode(line, dictionary=dictionary))
    return output


def encode_event_message(
    original: tuple[int, ...],
    pages: list[str],
    metrics: FontMetrics,
    dictionary: EventDictionary,
    *,
    raw_reader: bool,
) -> tuple[int, ...]:
    _page_sizes, breaks = _page_structure(original)
    final_break = list(breaks[-1])
    if raw_reader:
        output = metrics.encode(" ".join(pages), dictionary=None)
        output.extend(final_break)
        return _with_terminator(output, original)

    if len(pages) == 1:
        lines = _wrap_lines(pages[0], metrics)
        interior = breaks[:-1]
        separator_template = (
            list(interior[-1])
            if interior
            else ([0x8003, 0x8002] if 0x8003 in final_break else [0x8002])
        )
        capacity_pages = max(1, -(-len(lines) // 3))
        page_count = min(len(lines), max(capacity_pages, len(interior) + 1))
        output: list[int] = []
        position = 0
        for page_index in range(page_count):
            remaining = len(lines) - position
            pages_left = page_count - page_index
            line_count = -(-remaining // pages_left)
            if not 1 <= line_count <= 3:
                raise ValueError("EVENT dialogue exceeds three lines per page")
            output.extend(
                _encode_page_lines(
                    lines[position : position + line_count], metrics, dictionary
                )
            )
            position += line_count
            if page_index < page_count - 1:
                separator = list(
                    interior[page_index]
                    if page_index < len(interior)
                    else separator_template
                )
                if 0x8002 not in separator:
                    separator.append(0x8002)
                output.extend(separator)
        output.extend(final_break)
        return _with_terminator(output, original)

    if len(pages) != len(breaks):
        raise ValueError(
            f"translation page count {len(pages)} != source page count {len(breaks)}"
        )
    output = []
    interior = breaks[:-1]
    for group_index, text in enumerate(pages):
        lines = _wrap_lines(text, metrics)
        subpages = max(1, -(-len(lines) // 3))
        position = 0
        for subpage in range(subpages):
            remaining = len(lines) - position
            pages_left = subpages - subpage
            line_count = -(-remaining // pages_left)
            output.extend(
                _encode_page_lines(
                    lines[position : position + line_count], metrics, dictionary
                )
            )
            position += line_count
            last_subpage = subpage == subpages - 1
            last_group = group_index == len(pages) - 1
            if not last_subpage:
                separator = list(
                    interior[group_index]
                    if group_index < len(interior)
                    else final_break
                )
                if 0x8002 not in separator:
                    separator.append(0x8002)
                output.extend(separator)
            elif not last_group:
                output.extend(interior[group_index])
    output.extend(final_break)
    return _with_terminator(output, original)


def _expanded_ranges(rows: object, context: str) -> frozenset[int]:
    if not isinstance(rows, list):
        raise ValueError(f"{context} must be an array")
    output: set[int] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError(f"{context}[{index}] must be a pair")
        start, end = row
        if type(start) is not int or type(end) is not int or start > end:
            raise ValueError(f"{context}[{index}] is invalid")
        output.update(range(start, end + 1))
    return frozenset(output)


def message_encoding_overrides(
    container: object, context: str
) -> dict[int, str]:
    if not isinstance(container, dict):
        container = dict(container)  # MappingProxyType
    if container["source_encoding"] != "game_font12_16_event_skip":
        raise ValueError(f"{context}: unsupported default EVENT encoding")
    output: dict[int, str] = {}
    supported = {"game_font16_event_space", "game_font12_event_space"}
    for index, row in enumerate(container["source_encoding_overrides"]):
        encoding = row.get("source_encoding")
        if encoding not in supported:
            raise ValueError(
                f"{context}: unsupported general EVENT override {encoding!r}"
            )
        messages = _expanded_ranges(
            row.get("messages"), f"{context}.overrides[{index}]"
        )
        overlap = messages & output.keys()
        if overlap:
            raise ValueError(f"{context}: EVENT encoding overrides overlap")
        output.update((message, encoding) for message in messages)
    return output


def load_event_source_translations(source_names: tuple[str, ...]) -> dict[str, str]:
    """Resolve selected physical EVENT pages to their authored translations."""
    prefixes = tuple(f"game.{source}." for source in source_names)
    physical = load_physical_records()
    expected = {
        record_id for record_id in physical if record_id.startswith(prefixes)
    }
    return dict(
        load_bound_translations(prefixes, required_ids=expected)
    )


def load_event_translations() -> dict[str, str]:
    """Resolve every physical general-EVENT page to its authored translation."""
    return load_event_source_translations(GENERAL_EVENT_SOURCES)


@dataclass(frozen=True, slots=True)
class CompiledEventBank:
    source: str
    path: PurePosixPath
    data: bytes
    messages: int
    pages: int
    body_bytes: int


def compile_event_sources(
    manifest: SourceManifest,
    stock_files: dict[PurePosixPath, bytes],
    translations: dict[str, str],
    font16_metrics: FontMetrics,
    dictionary: EventDictionary,
    source_names: tuple[str, ...],
    *,
    font12_metrics: FontMetrics | None = None,
    preserve_encodings: frozenset[str] = frozenset(),
) -> tuple[CompiledEventBank, ...]:
    sources = {source.name: source for source in manifest.sources}
    compiled: list[CompiledEventBank] = []
    for source_name in source_names:
        try:
            source = sources[source_name]
        except KeyError as error:
            raise ValueError(f"missing general EVENT source {source_name}") from error
        container = dict(source.container)
        file_spec = manifest.files[container["file"]]
        stock = stock_files[file_spec.path]
        if len(stock) != file_spec.size:
            raise ValueError(f"{file_spec.path}: stock size changed")
        digest = hashlib.sha256(stock).hexdigest()
        if digest != file_spec.stock_sha256:
            raise ValueError(
                f"{file_spec.path}: stock SHA-256 is {digest}, "
                f"expected {file_spec.stock_sha256}"
            )
        table_offset = int(container["table_offset"], 16)
        body_offset = int(container["body_offset"], 16)
        bank = EveBank.parse(stock, table_offset, body_offset)
        expected_messages = container["expected_messages"]
        if len(bank.messages) != expected_messages:
            raise ValueError(
                f"{file_spec.path}: found {len(bank.messages)} messages, "
                f"expected {expected_messages}"
            )
        overrides = message_encoding_overrides(container, source_name)
        if any(message >= len(bank.messages) for message in overrides):
            raise ValueError(f"{source_name}: encoding override is out of range")
        by_message: dict[int, list[tuple[int, str]]] = {}
        for physical_id, translation in translations.items():
            match = _PHYSICAL_ID_RE.fullmatch(physical_id)
            assert match is not None
            selected_source, message_text, page_text = match.groups()
            if selected_source == source_name:
                by_message.setdefault(int(message_text), []).append(
                    (int(page_text), translation)
                )
        words: list[tuple[int, ...]] = []
        page_count = 0
        source_page_count = 0
        for message in bank.messages:
            source_page_count += _source_page_count(message.words)
            page_rows = sorted(by_message.get(message.index, ()))
            if not page_rows:
                # A small number of stock messages are structural/control-only.
                # They are not translator-facing records and remain byte-identical.
                words.append(message.words)
                continue
            encoding = overrides.get(message.index)
            if [page for page, _translation in page_rows] != list(
                range(len(page_rows))
            ):
                raise ValueError(
                    f"{source_name}: message {message.index} has non-contiguous pages"
                )
            if encoding in preserve_encodings:
                words.append(message.words)
                continue
            pages = [translation for _page, translation in page_rows]
            if encoding is None:
                message_metrics = font16_metrics
                raw_reader = False
            elif encoding == "game_font16_event_space":
                message_metrics = font16_metrics
                raw_reader = True
            else:
                if font12_metrics is None:
                    raise ValueError(
                        f"{source_name}: FONT12 EVENT output has no metrics"
                    )
                message_metrics = font12_metrics
                raw_reader = True
            words.append(
                encode_event_message(
                    message.words,
                    pages,
                    message_metrics,
                    dictionary,
                    raw_reader=raw_reader,
                )
            )
            page_count += len(pages)
        expected_pages = container["expected_pages"]
        if source_page_count != expected_pages:
            raise ValueError(
                f"{file_spec.path}: source has {source_page_count} pages, "
                f"expected {expected_pages}"
            )
        output = bank.rebuild(stock, tuple(words))
        rebuilt = EveBank.parse(output, table_offset, body_offset)
        compiled.append(
            CompiledEventBank(
                source_name,
                file_spec.path,
                output,
                len(words),
                page_count,
                rebuilt.body_size,
            )
        )
    return tuple(compiled)


def compile_event_banks(
    manifest: SourceManifest,
    stock_files: dict[PurePosixPath, bytes],
    translations: dict[str, str],
    metrics: FontMetrics,
    dictionary: EventDictionary,
) -> tuple[CompiledEventBank, ...]:
    return compile_event_sources(
        manifest,
        stock_files,
        translations,
        metrics,
        dictionary,
        GENERAL_EVENT_SOURCES,
    )
