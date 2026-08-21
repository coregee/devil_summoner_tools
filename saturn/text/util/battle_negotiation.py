"""Compile the complete Saturn battle-negotiation text surface."""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath

from .assets import load_bound_translations, load_physical_records
from .event_codec import EventDictionary, pack_direct_codes
from .event_repack import CompiledEventBank, EveBank, FontMetrics, _page_structure
from .sources import SourceManifest
from .tokens import Named, Raw, Text, parse_tokens


NEGOTIATION_EVE_SOURCES = (
    "bosstalk",
    "tlk_bst",
    "kemo",
    "tlk_kofu",
    "nbl_m",
    "tlk_hirk",
    "tlk_yngm",
    "grl",
    "tlk_boy",
    "cld_f",
    "tlk_lady",
    "tlk_crzy",
    "jijy",
    "cyni",
    "tlk_west",
    "slm",
)
COMBAT_INSERT_CODES = frozenset({0x8010, *range(0x8012, 0x8018)})
COMBAT_NAMED_WORDS = {
    "WAIT": 0x8003,
    "BEAT": 0x8004,
    "demon_name": 0x8010,
    "race": 0x8012,
    "requested_item": 0x8013,
    "offered_item": 0x8014,
    "codename": 0x8015,
    "kyouji_name": 0x8016,
    "rei_name": 0x8017,
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
COMBAT_INSERT_WIDTHS = {
    0x8010: 8 * 16,
    0x8012: 6 * 16,
    0x8013: 8 * 16,
    0x8014: 8 * 16,
    0x8015: 8 * 16,
    0x8016: 6 * 16,
    0x8017: 2 * 16,
}
LITERAL_GLYPHS = {"『": 0x0105, "♂": 0x00B8, "←": 0x00BF, "□": 0x00C0}
STRUCTURAL_EDGE_CODES = frozenset({0x8000, 0x8002, 0x8003})
PAUSE_CODES = frozenset({0x8003, 0x8004})
SOFT_WRAP_CODE = 0x07FE
MEASURE_START_CODE = 0x07FC
MEASURE_END_CODE = 0x07FD
STATIC_HINT_BASE = 0x0750
STATIC_HINT_LIMIT = MEASURE_START_CODE
STATIC_HINT_MAX = STATIC_HINT_LIMIT - STATIC_HINT_BASE - 1
SPACE_CODE = 267
DIALOGUE_WIDTH = 300
_EVE_ID_RE = re.compile(r"game\.([a-z0-9_]+)\.m([0-9]{4})\.p([0-9]{2})\Z")
_OFFSET_ID_RE = re.compile(r"game\.[a-z0-9_]+\.o([0-9a-f]{6})(?:\.[a-z0-9_]+)?\Z")
_PUNCTUATION_SPACE_RE = re.compile(r"([.!?])([A-Za-z{])")


def _normalize(value: str) -> str:
    replacements = {
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
    for source, replacement in replacements.items():
        value = value.replace(source, replacement)
    value = value.replace("{n}", "\n")
    value = "\n".join(" ".join(line.split()) for line in value.split("\n"))
    value = _PUNCTUATION_SPACE_RE.sub(r"\1 \2", value)
    return re.sub(r" \{(BEAT|WAIT)\}", r"{\1}", value)


def _text_codes(value: str, metrics: FontMetrics) -> list[int]:
    output: list[int] = []
    start = 0
    for position, character in enumerate(value):
        literal = LITERAL_GLYPHS.get(character)
        if literal is None:
            continue
        if start < position:
            output.extend(glyph.code for glyph in metrics.segment_output(value[start:position]))
        output.append(literal)
        start = position + 1
    if start < len(value):
        output.extend(glyph.code for glyph in metrics.segment_output(value[start:]))
    return output


def _direct_codes(value: str, metrics: FontMetrics) -> list[int]:
    output: list[int] = []
    for token in parse_tokens(value):
        if isinstance(token, Text):
            output.extend(_text_codes(token.value, metrics))
        elif isinstance(token, Raw):
            if token.width != 2:
                raise ValueError("battle negotiation requires 16-bit raw tokens")
            output.append(token.value)
        else:
            try:
                output.append(COMBAT_NAMED_WORDS[token.name])
            except KeyError as error:
                raise ValueError(
                    f"unsupported battle-negotiation token {{{token.name}}}"
                ) from error
    return output


def _width(value: str, metrics: FontMetrics) -> int:
    advances = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    width = 0
    for code in _direct_codes(value, metrics):
        if code in COMBAT_INSERT_WIDTHS:
            width += COMBAT_INSERT_WIDTHS[code]
        elif code in {0x00B8, 0x00BF, 0x00C0, 0x00C1, 0x0105, 0x0106}:
            width += 16
        elif code < 0x8000:
            width += advances.get(code, 16)
    return width


@dataclass(frozen=True, slots=True)
class CombatLine:
    text: str
    break_after: int | None


def _combat_lines(value: str, metrics: FontMetrics) -> list[CombatLine]:
    explicit_lines = _normalize(value).split("\n")
    lines: list[CombatLine] = []
    for explicit_index, explicit_line in enumerate(explicit_lines):
        words = [word for word in explicit_line.split(" ") if word]
        wrapped: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join((*current, word))
            if current and _width(candidate, metrics) > DIALOGUE_WIDTH:
                wrapped.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            wrapped.append(" ".join(current))
        elif not words:
            wrapped.append("")
        for wrapped_index, line in enumerate(wrapped):
            if wrapped_index < len(wrapped) - 1:
                break_after = SOFT_WRAP_CODE
            elif explicit_index < len(explicit_lines) - 1:
                break_after = 0x8001
            else:
                break_after = None
            lines.append(CombatLine(line, break_after))
    return lines


def _stage_line(
    line: CombatLine,
    line_position: int,
    metrics: FontMetrics,
) -> list[int]:
    direct = _direct_codes(line.text, metrics)
    widths = {glyph.code: glyph.advance for glyph in metrics.glyphs}
    widths.update({code: 16 for code in (0x00B8, 0x00BF, 0x00C0, 0x00C1, 0x0105, 0x0106)})
    staged: list[int] = []
    run: list[int] = []
    first_run = True

    def flush_run() -> None:
        nonlocal first_run
        if not run:
            return
        static_width = sum(widths.get(code, 0) for code in run)
        inserts = [index for index, code in enumerate(run) if code in COMBAT_INSERT_CODES]
        if first_run and line_position == 0:
            staged.extend(run)
        elif inserts == [0]:
            staged.extend((MEASURE_START_CODE, MEASURE_START_CODE, static_width + 1))
            staged.extend(run)
        elif inserts or static_width > STATIC_HINT_MAX:
            staged.extend((MEASURE_START_CODE, *run, MEASURE_END_CODE, *run))
        else:
            staged.append(STATIC_HINT_BASE + static_width)
            staged.extend(run)
        run.clear()
        first_run = False

    for code in direct:
        if code == SPACE_CODE or (code >= 0x8000 and code not in COMBAT_INSERT_CODES):
            flush_run()
            staged.append(code)
        else:
            run.append(code)
    flush_run()
    return staged


def _skeleton(words: tuple[int, ...]) -> tuple[list[int], list[int]]:
    payload = [index for index, word in enumerate(words) if word not in STRUCTURAL_EDGE_CODES]
    if not payload:
        return [word for word in words if word in STRUCTURAL_EDGE_CODES], []
    lead = [word for word in words[: payload[0]] if word in STRUCTURAL_EDGE_CODES]
    tail = [word for word in words[payload[-1] + 1 :] if word in STRUCTURAL_EDGE_CODES]
    return lead, tail


def encode_negotiation_message(
    original: tuple[int, ...],
    pages: list[str],
    metrics: FontMetrics,
    dictionary: EventDictionary,
) -> tuple[int, ...]:
    _page_sizes, breaks = _page_structure(original)
    if len(pages) != len(breaks):
        raise ValueError(
            f"translation page count {len(pages)} != source page count {len(breaks)}"
        )
    lead, tail = _skeleton(original)
    encoded_pages: list[tuple[list[CombatLine], list[list[int]]]] = []
    for text in pages:
        lines = _combat_lines(text, metrics)
        if any(_width(line.text, metrics) > DIALOGUE_WIDTH for line in lines):
            raise ValueError("battle-negotiation line exceeds 300 pixels")
        staged = [
            dictionary.encode_codes(_stage_line(line, index, metrics))
            for index, line in enumerate(lines)
        ]
        encoded_pages.append((lines, staged))

    first_translated_word = next(
        (
            word
            for _lines, encoded_lines in encoded_pages
            for line in encoded_lines
            for word in line
            if word not in {MEASURE_START_CODE, MEASURE_END_CODE}
            and not STATIC_HINT_BASE <= word < STATIC_HINT_LIMIT
        ),
        None,
    )
    if (
        first_translated_word in PAUSE_CODES
        and original[0] != first_translated_word
    ):
        raise ValueError("battle-negotiation translation cannot move an initial pause")

    output = list(lead)
    for page_index, (lines, encoded_lines) in enumerate(encoded_pages):
        for line_index, line in enumerate(encoded_lines):
            if line_index:
                break_code = lines[line_index - 1].break_after
                if break_code is None:
                    raise ValueError("battle-negotiation line is missing its break")
                output.append(break_code)
            output.extend(line)
        if page_index < len(encoded_pages) - 1:
            boundary = breaks[page_index]
            if 0x8002 not in boundary:
                raise ValueError("battle-negotiation page boundary has no clear")
            output.extend(boundary)
    output.extend(tail)
    if 0x8000 not in tail:
        output.append(0x8000)
    return tuple(output)


def load_negotiation_translations() -> dict[str, str]:
    prefixes = tuple(f"game.{source}." for source in NEGOTIATION_EVE_SOURCES)
    physical = load_physical_records()
    required = {record_id for record_id in physical if record_id.startswith(prefixes)}
    return dict(load_bound_translations(prefixes, required_ids=required))


def compile_negotiation_banks(
    manifest: SourceManifest,
    stock_files: dict[PurePosixPath, bytes],
    translations: dict[str, str],
    metrics: FontMetrics,
    dictionary: EventDictionary,
) -> tuple[CompiledEventBank, ...]:
    sources = {source.name: source for source in manifest.sources}
    compiled: list[CompiledEventBank] = []
    for source_name in NEGOTIATION_EVE_SOURCES:
        source = sources[source_name]
        container = dict(source.container)
        file_spec = manifest.files[container["file"]]
        stock = stock_files[file_spec.path]
        if len(stock) != file_spec.size or hashlib.sha256(stock).hexdigest() != file_spec.stock_sha256:
            raise ValueError(f"{file_spec.path}: stock identity changed")
        table_offset = int(container["table_offset"], 16)
        body_offset = int(container["body_offset"], 16)
        bank = EveBank.parse(stock, table_offset, body_offset)
        if len(bank.messages) != container["expected_messages"]:
            raise ValueError(f"{file_spec.path}: message count changed")
        by_message: dict[int, list[tuple[int, str]]] = {}
        for physical_id, translation in translations.items():
            match = _EVE_ID_RE.fullmatch(physical_id)
            assert match is not None
            selected_source, message, page = match.groups()
            if selected_source == source_name:
                by_message.setdefault(int(message), []).append((int(page), translation))
        words: list[tuple[int, ...]] = []
        translated_pages = 0
        source_pages = 0
        for message in bank.messages:
            source_pages += len(_page_structure(message.words)[1])
            rows = sorted(by_message.get(message.index, ()))
            if [page for page, _text in rows] != list(range(len(rows))):
                raise ValueError(f"{source_name}: message {message.index} has incomplete pages")
            if not rows:
                # Six stock messages are structural/control-only and therefore
                # have no translator-facing asset field.
                words.append(message.words)
                continue
            pages = [text for _page, text in rows]
            try:
                encoded = encode_negotiation_message(
                    message.words, pages, metrics, dictionary
                )
            except ValueError as error:
                raise ValueError(
                    f"{source_name}: message {message.index}: {error}"
                ) from error
            words.append(encoded)
            translated_pages += len(pages)
        if source_pages != container["expected_pages"]:
            raise ValueError(f"{file_spec.path}: source page count changed")
        output = bank.rebuild(stock, tuple(words))
        rebuilt = EveBank.parse(output, table_offset, body_offset)
        compiled.append(
            CompiledEventBank(
                source_name,
                file_spec.path,
                output,
                len(words),
                translated_pages,
                rebuilt.body_size,
            )
        )
    return tuple(compiled)


def compile_combat_fixed_text(
    stock: bytes,
    metrics: FontMetrics,
) -> bytes:
    physical = load_physical_records()
    prefixes = ("game.combat_condition_messages.", "game.combat_system.")
    required = {
        record_id
        for record_id in physical
        if record_id.startswith("game.combat_condition_messages.")
    } | {
        "game.combat_system.o0528f4",
        "game.combat_system.o05291c",
        "game.combat_system.o052944",
        "game.combat_system.o05454e",
    }
    translations = load_bound_translations(prefixes, required_ids=required)
    capacities = {
        "game.combat_system.o0528f4": 3,
        "game.combat_system.o05291c": 7,
        "game.combat_system.o052944": 5,
        "game.combat_system.o05454e": 7,
    }
    output = bytearray(stock)
    for physical_id, translation in translations.items():
        match = _OFFSET_ID_RE.fullmatch(physical_id)
        assert match is not None
        offset = int(match.group(1), 16)
        capacity = capacities.get(physical_id, 22)
        normalized = _normalize(translation)
        if "\n" in normalized:
            raise ValueError(f"{physical_id}: fixed negotiation text cannot contain a newline")
        words = pack_direct_codes(_direct_codes(normalized, metrics))
        payload = (*words, 0x8000)
        if len(payload) > capacity:
            raise ValueError(
                f"{physical_id}: needs {len(payload)} words, capacity is {capacity}"
            )
        padded = (*payload, *((0,) * (capacity - len(payload))))
        struct.pack_into(f">{capacity}H", output, offset, *padded)
    return bytes(output)
