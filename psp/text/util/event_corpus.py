"""Repack the checked shared corpus into the standard PSP EVENT banks.

The main EVENT renderer has a byte-cursor/VWF hook, but several menu readers
still consume literal u16 glyph words.  This module therefore packs every
bound shared page owned by the standard EVENT VM, encodes every checked
opcode-3 option as raw Ark or insert words, and preserves non-option
direct-reader messages plus genuinely PSP-only pages with no shared identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from psp.archive.pack import PspPack
from psp.text.util.assets import ASSET_ROOT, load_asset_field

from .event_dvlname import (
    DVLNAME_RUNTIME_MAGIC,
    build_psp_dvlname_runtime_table,
    load_psp_dvlname_text,
)
from .event_bank import (
    KNOWN_BANKS,
    MESSAGE_BODY_OFFSET,
    EveBinding,
    PspEveBank,
    PspEveFiles,
    PspEveMessage,
    has_payload,
    split_pages,
)
from .event_packed import (
    encode_ascii,
    encode_logical_word,
    glyph_code_for_character,
    normalize_ascii,
)

SCRIPT_TABLE_OFFSET = 0x22
SCRIPT_BODY_OFFSET = 0x800
EVENT_SURFACE_WIDTH = 320
EVENT_SIDE_MARGIN = 10
EVENT_DIALOGUE_WIDTH = EVENT_SURFACE_WIDTH - EVENT_SIDE_MARGIN * 2
EVENT_LINES_PER_PAGE = 3
EVENT_INSERT_WIDTH = 80
EVENT_NAME_INSERT_WIDTH = EVENT_INSERT_WIDTH
EVENT_RUNTIME_GLYPH_CAP = 120
EVENT_OPTION_HANDLE_POOL = 84
EVENT_OPTION_GRID_WIDTH = EVENT_DIALOGUE_WIDTH // 2
EVENT_OPTION_STACKED_WIDTH = EVENT_DIALOGUE_WIDTH
TEXT_ROOT = Path(__file__).resolve().parents[1]
EVENT_BINDINGS_ROOT = TEXT_ROOT / "config" / "event"
EVENT_OPTION_CONFIG_PATH = TEXT_ROOT / "config" / "event_options.json"
EVENT_OPTION_CORPUS_PATH = ASSET_ROOT / "events" / "event_psp.json"
EVENT_OPTION_CORPUS = "events/event_psp.json"
DVLNAME_RUNTIME_HEADER_SIZE = 8

EVENT_BANK_NAMES = frozenset({"SHOPSMP", "EVFILE_0", "EVFILE_1", "MESFILE", "EVFILE_2"})
EVENT_BINDINGS = tuple(
    binding for binding in KNOWN_BANKS if binding.name in EVENT_BANK_NAMES
)
if len(EVENT_BINDINGS) != len(EVENT_BANK_NAMES):
    raise ValueError("standard PSP EVENT bank inventory changed")

# These records are selected by code paths that bypass the EVENT decoder.
# The explicit ranges mirror the semantic roles inherited by the PSP port;
# script-menu options found below are added from the checked PSP bytecode.
_FORCED_RAW_MESSAGES = {
    "SHOPSMP": frozenset({0})
    | frozenset(range(68, 79))
    | frozenset(range(81, 98))
    | frozenset(range(101, 109))
    | frozenset(range(109, 267))
    | frozenset(range(272, 275))
    | frozenset({773, 774, 779}),
    "EVFILE_0": frozenset({33, 34, 35, 57, 58, 60, 240, 258, 259, 272}),
}
EXPECTED_RAW_MESSAGE_COUNTS = {
    "SHOPSMP": 212,
    "EVFILE_0": 71,
    "EVFILE_1": 23,
    "MESFILE": 0,
    "EVFILE_2": 2,
}

_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
_LITERAL_GLYPH_CODES = {
    "\n": 0x8001,
    "\u300e": 0x005E,
    "\u2642": 0x0048,
    "\u2190": 0x0068,
}
_NAMED_EVENT_CODES = {
    "n": 0x8001,
    "WAIT": 0x8003,
    "NL": 0x8004,
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
    "yen_symbol": 0x004E,
    "white_square": 0x004E,
}
_NAME_INSERT_TOKENS = frozenset({"first_name", "last_name", "ward", "city", "codename"})
_NAME_INSERT_CODES = frozenset(
    _NAMED_EVENT_CODES[token] for token in _NAME_INSERT_TOKENS
)
_EVENT_INSERT_CODES = frozenset({0x8006, 0x8007, *range(0x8017, 0x8024)})
_SHARED_GLYPH_TO_PSP = {
    0x00AE: 0x0005,
    0x00B8: 0x0048,
    0x00BF: 0x0068,
    0x00C0: 0x004E,
    0x0105: 0x005E,
    0x010A: 0x005A,
    0x010B: 0x0065,
    0x010D: 0x003C,
    0x010E: 0x003E,
}
_ZERO_WIDTH_TOKENS = frozenset({"WAIT", "NL"})
_NAMED_GLYPH_TOKENS = frozenset({"yen_symbol", "white_square"})


def payload_pages(message: PspEveMessage):
    """Return only text-bearing pages while preserving checked page order."""

    pages = tuple(page for page in split_pages(message) if has_payload(page.words))
    if tuple(page.index for page in pages) != tuple(range(len(pages))):
        raise ValueError(
            f"PSP EVE message {message.index} has a non-contiguous payload page"
        )
    return pages


@dataclass(frozen=True)
class EventBankBuild:
    """One fixed-size EVENT member after selective VM/raw-text rebuilding."""

    name: str
    member_index: int
    data: bytes
    message_count: int
    translated_message_count: int
    translated_record_ids: tuple[str, ...]
    raw_message_indices: tuple[int, ...]
    translated_option_message_indices: tuple[int, ...]
    option_descriptor_count: int
    option_slot_count: int
    option_display_override_count: int
    used_body_bytes: int
    body_capacity_bytes: int
    dvlname_table_offset: int | None
    dvlname_table_size: int
    changed_byte_count: int


@dataclass(frozen=True)
class EventCorpusBuild:
    """The same-size eve_files archive and its auditable translation scope."""

    eve_files: bytes
    banks: tuple[EventBankBuild, ...]
    corpus_paths: tuple[str, ...]
    translated_record_ids: tuple[str, ...]
    preserved_record_ids: tuple[str, ...]
    changed_member_indices: tuple[int, ...]
    changed_byte_count: int


@dataclass(frozen=True)
class EventOptionDescriptor:
    """One opcode-3 menu discovered in the PSP script bytecode."""

    script_index: int
    script_start_word: int
    opcode_position: int
    prompt_message: int | None
    label_messages: tuple[int, ...]
    target_scripts: tuple[int, ...]


@dataclass(frozen=True)
class EventOptionDisplayRecord:
    """A shared-owned PSP wording variant for one grid-constrained label."""

    record_id: str
    source_record_id: str
    jp: str
    translation: str
    reviewed: bool


@dataclass(frozen=True)
class EventOptionBankContract:
    """Compact PSP-owned guardrails for one dynamically scanned EVENT bank."""

    name: str
    descriptor_count: int
    slot_count: int
    message_count: int
    descriptor_sha256: str
    display_overrides: tuple[tuple[str, str], ...]
    preserved_prefixes: tuple[tuple[int, tuple[int, ...]], ...]
    required_insert_codes: tuple[tuple[int, tuple[int, ...]], ...]


@dataclass(frozen=True)
class EventOptionContract:
    """Checked PSP option bindings plus shared constrained display records."""

    banks: tuple[EventOptionBankContract, ...]
    display_records: tuple[EventOptionDisplayRecord, ...]

    @property
    def banks_by_name(self) -> dict[str, EventOptionBankContract]:
        return {bank.name: bank for bank in self.banks}

    @property
    def display_records_by_id(self) -> dict[str, EventOptionDisplayRecord]:
        return {record.record_id: record for record in self.display_records}


def _object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _array(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    return value


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{context} must be an integer >= {minimum}")
    return value


def _hex_word(value: object, context: str, *, prefixed: bool) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be hexadecimal text")
    digits = value
    if prefixed:
        if not value.startswith("0x"):
            raise ValueError(f"{context} must use a 0x prefix")
        digits = value[2:]
    elif len(value) != 4:
        raise ValueError(f"{context} must contain four hexadecimal digits")
    try:
        result = int(digits, 16)
    except ValueError as error:
        raise ValueError(f"{context} is not hexadecimal") from error
    if not 0 <= result <= 0xFFFF:
        raise ValueError(f"{context} exceeds one u16 word")
    return result


def _message_code_contracts(
    value: object,
    context: str,
    binding: EveBinding,
    *,
    valid_code: Callable[[int], bool],
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    """Load a small PSP raw-reader ABI exception table."""

    contracts: list[tuple[int, tuple[int, ...]]] = []
    for row_index, row_value in enumerate(_array(value, context)):
        row_context = f"{context} {row_index}"
        row = _object(row_value, row_context)
        if set(row) != {"message_index", "codes"}:
            raise ValueError(f"{row_context}: fields changed")
        message_index = _integer(row["message_index"], f"{row_context}: message")
        codes = tuple(
            _hex_word(code, f"{row_context}: code {position}", prefixed=False)
            for position, code in enumerate(
                _array(row["codes"], f"{row_context}: codes")
            )
        )
        if (
            message_index >= binding.expected_messages
            or not codes
            or any(not valid_code(code) for code in codes)
            or message_index in {index for index, _codes in contracts}
        ):
            raise ValueError(f"{row_context}: invalid message-code contract")
        contracts.append((message_index, codes))
    return tuple(contracts)


def load_event_option_contract(
    config_path: Path = EVENT_OPTION_CONFIG_PATH,
    corpus_path: Path = EVENT_OPTION_CORPUS_PATH,
) -> EventOptionContract:
    """Load compact PSP scan guardrails and constrained shared prose."""

    document = _object(
        json.loads(config_path.read_text(encoding="utf-8")),
        str(config_path),
    )
    if set(document) != {"version", "platform", "corpus", "renderer", "banks"}:
        raise ValueError(f"{config_path}: EVENT option config fields changed")
    if document["version"] != 1 or document["platform"] != "psp":
        raise ValueError(f"{config_path}: unsupported EVENT option config")
    if document["corpus"] != EVENT_OPTION_CORPUS:
        raise ValueError(f"{config_path}: EVENT option corpus path changed")
    renderer = _object(document["renderer"], f"{config_path}: renderer")
    if set(renderer) != {"handle_pool", "grid_width", "stacked_width"}:
        raise ValueError(f"{config_path}: EVENT option renderer fields changed")
    if (
        renderer["handle_pool"] != EVENT_OPTION_HANDLE_POOL
        or renderer["grid_width"] != EVENT_OPTION_GRID_WIDTH
        or renderer["stacked_width"] != EVENT_OPTION_STACKED_WIDTH
    ):
        raise ValueError(f"{config_path}: EVENT option renderer geometry changed")

    bank_values = _array(document["banks"], f"{config_path}: banks")
    if len(bank_values) != len(EVENT_BINDINGS):
        raise ValueError(f"{config_path}: EVENT option bank inventory changed")
    banks = []
    configured_display_pairs: set[tuple[str, str]] = set()
    for bank_index, (value, binding) in enumerate(
        zip(bank_values, EVENT_BINDINGS, strict=True)
    ):
        context = f"{config_path}: bank {bank_index}"
        row = _object(value, context)
        expected_fields = {
            "name",
            "descriptor_count",
            "slot_count",
            "message_count",
            "descriptor_sha256",
            "display_overrides",
            "preserved_prefixes",
            "required_insert_codes",
        }
        if set(row) != expected_fields or row["name"] != binding.name:
            raise ValueError(f"{context}: EVENT option bank identity changed")

        descriptor_count = _integer(
            row["descriptor_count"], f"{context}: descriptor count"
        )
        slot_count = _integer(row["slot_count"], f"{context}: slot count")
        message_count = _integer(row["message_count"], f"{context}: message count")
        descriptor_sha256 = row["descriptor_sha256"]
        if (
            not isinstance(descriptor_sha256, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", descriptor_sha256) is None
        ):
            raise ValueError(f"{context}: invalid EVENT option descriptor digest")
        if not (
            descriptor_count <= slot_count <= descriptor_count * 4
            and 0 <= message_count <= slot_count
            and (descriptor_count == 0) == (message_count == 0)
        ):
            raise ValueError(f"{context}: EVENT option coverage counts changed")

        override_values = _array(
            row["display_overrides"], f"{context}: display overrides"
        )
        display_overrides: list[tuple[str, str]] = []
        for override_index, override_value in enumerate(override_values):
            override_context = f"{context}: display override {override_index}"
            override = _object(override_value, override_context)
            if set(override) != {"source_asset", "display_asset"}:
                raise ValueError(f"{override_context}: fields changed")
            source_record_id = override["source_asset"]
            display_record_id = override["display_asset"]
            if not isinstance(source_record_id, str) or not isinstance(
                display_record_id, str
            ):
                raise ValueError(f"{override_context}: asset identities must be text")
            pair = (source_record_id, display_record_id)
            if (
                source_record_id in {source for source, _display in display_overrides}
                or display_record_id
                in {display for _source, display in display_overrides}
                or pair in configured_display_pairs
            ):
                raise ValueError(f"{override_context}: duplicate display mapping")
            display_overrides.append(pair)
            configured_display_pairs.add(pair)

        preserved_prefixes = _message_code_contracts(
            row["preserved_prefixes"],
            f"{context}: preserved prefix",
            binding,
            valid_code=lambda code: code >= 0x8000 and code != 0x8000,
        )
        required_insert_codes = _message_code_contracts(
            row["required_insert_codes"],
            f"{context}: required insert",
            binding,
            valid_code=_EVENT_INSERT_CODES.__contains__,
        )

        banks.append(
            EventOptionBankContract(
                name=binding.name,
                descriptor_count=descriptor_count,
                slot_count=slot_count,
                message_count=message_count,
                descriptor_sha256=descriptor_sha256,
                display_overrides=tuple(display_overrides),
                preserved_prefixes=preserved_prefixes,
                required_insert_codes=required_insert_codes,
            )
        )

    display_records: list[EventOptionDisplayRecord] = []
    for source_record_id, record_id in sorted(configured_display_pairs):
        source_reference, _source_translation = load_asset_field(source_record_id)
        display_reference, translation = load_asset_field(record_id)
        if source_reference != display_reference or not translation:
            raise ValueError(
                f"{config_path}: option display {record_id!r} lost its source identity"
            )
        display_records.append(
            EventOptionDisplayRecord(
                record_id=record_id,
                source_record_id=source_record_id,
                jp=source_reference,
                translation=translation,
                reviewed=False,
            )
        )
    return EventOptionContract(
        banks=tuple(banks),
        display_records=tuple(display_records),
    )


def _message_bytes(message: PspEveMessage) -> bytes:
    return struct.pack(f">{len(message.words)}H", *message.words)


def _normalize_event_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("PSP EVENT translation must be a string")
    return normalize_ascii(text)


def _append_literal(output: bytearray, literal: str) -> None:
    start = 0
    for index, character in enumerate(literal):
        code = _LITERAL_GLYPH_CODES.get(character)
        if code is None:
            continue
        if index > start:
            output.extend(encode_ascii(literal[start:index]))
        output.extend(encode_logical_word(code))
        start = index + 1
    if start < len(literal):
        output.extend(encode_ascii(literal[start:]))


def _token_code(token: str) -> int:
    named = _NAMED_EVENT_CODES.get(token)
    if named is not None:
        return named
    kind, separator, value = token.partition(":")
    if separator != ":" or kind not in {"GLYPH", "INS", "OP"}:
        raise ValueError(f"unknown PSP EVENT text token {{{token}}}")
    if len(value) != 4:
        raise ValueError(f"PSP EVENT token {{{token}}} needs four hex digits")
    try:
        code = int(value, 16)
    except ValueError as error:
        raise ValueError(f"PSP EVENT token {{{token}}} is not hexadecimal") from error
    if kind == "GLYPH":
        if code & 0x8000:
            raise ValueError(f"PSP EVENT token {{{token}}} is not a glyph")
        try:
            return _SHARED_GLYPH_TO_PSP[code]
        except KeyError as error:
            raise ValueError(
                f"PSP EVENT token {{{token}}} has no checked PSP glyph"
            ) from error
    if kind == "INS" and code not in _EVENT_INSERT_CODES:
        raise ValueError(f"PSP EVENT token {{{token}}} is not an insert")
    if kind == "OP" and (not code & 0x8000 or code in {0x8000, 0x8001, 0x8002, 0x8003}):
        raise ValueError(f"PSP EVENT token {{{token}}} is structural")
    return code


def _token_layout(token: str) -> tuple[int, int]:
    """Return conservative ``(pixels, handles)`` for one inline token."""

    if token == "n":
        raise ValueError("PSP EVENT newline token cannot occur inside a row")
    if token in _ZERO_WIDTH_TOKENS:
        _token_code(token)
        return 0, 0
    if token in _NAMED_GLYPH_TOKENS:
        _token_code(token)
        return 16, 1
    if token in _NAME_INSERT_TOKENS:
        _token_code(token)
        return EVENT_NAME_INSERT_WIDTH, 8
    if token in _NAMED_EVENT_CODES:
        _token_code(token)
        return EVENT_INSERT_WIDTH, 8
    kind, separator, _value = token.partition(":")
    if separator == ":" and kind == "GLYPH":
        _token_code(token)
        return 16, 1
    if separator == ":" and kind == "INS":
        code = _token_code(token)
        width = (
            EVENT_NAME_INSERT_WIDTH
            if code in _NAME_INSERT_CODES
            else EVENT_INSERT_WIDTH
        )
        return width, 8
    if separator == ":" and kind == "OP":
        _token_code(token)
        return 0, 0
    _token_code(token)
    raise AssertionError("checked PSP EVENT token has no layout contract")


def event_row_layout(
    text: str,
    measure_ascii: Callable[[str], int],
) -> tuple[int, int]:
    """Measure one row using PSP Ark widths and raw-reader handle costs."""

    normalized = _normalize_event_text(text)
    if "\n" in normalized or "{n}" in normalized:
        raise ValueError("PSP EVENT row measurement expects one explicit row")
    pixels = 0
    handles = 0
    position = 0
    for match in _TOKEN_PATTERN.finditer(normalized):
        literal = normalized[position : match.start()]
        if "{" in literal or "}" in literal:
            raise ValueError(f"unknown PSP EVENT token in {literal!r}")
        pixels += measure_ascii(literal)
        handles += len(literal)
        token_pixels, token_handles = _token_layout(match.group(1))
        pixels += token_pixels
        handles += token_handles
        position = match.end()
    literal = normalized[position:]
    if "{" in literal or "}" in literal:
        raise ValueError(f"unknown PSP EVENT token in {literal!r}")
    pixels += measure_ascii(literal)
    handles += len(literal)
    return pixels, handles


def wrap_event_translation(
    text: str,
    measure_ascii: Callable[[str], int],
) -> tuple[str, ...]:
    """Wrap one shared page to the shared 300px, three-row dialogue ABI."""

    normalized = _normalize_event_text(text).replace("{n}", "\n")
    lines: list[str] = []
    for explicit_line in normalized.split("\n"):
        words = [word for word in explicit_line.split(" ") if word]
        if not words:
            lines.append("")
            continue
        current: list[str] = []
        for word in words:
            word_pixels, word_handles = event_row_layout(word, measure_ascii)
            if word_pixels > EVENT_DIALOGUE_WIDTH:
                raise ValueError(
                    f"PSP EVENT word {word!r} is {word_pixels}px; "
                    f"dialogue width is {EVENT_DIALOGUE_WIDTH}px"
                )
            if word_handles > EVENT_RUNTIME_GLYPH_CAP:
                raise ValueError(
                    f"PSP EVENT word {word!r} needs {word_handles} handles; "
                    f"runtime cap is {EVENT_RUNTIME_GLYPH_CAP}"
                )
            candidate = " ".join((*current, word))
            candidate_pixels, _candidate_handles = event_row_layout(
                candidate,
                measure_ascii,
            )
            if current and candidate_pixels > EVENT_DIALOGUE_WIDTH:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        lines.append(" ".join(current))

    if not lines:
        lines.append("")
    for line in lines:
        pixels, handles = event_row_layout(line, measure_ascii)
        if pixels > EVENT_DIALOGUE_WIDTH:
            raise ValueError(
                f"PSP EVENT row is {pixels}px; dialogue width is "
                f"{EVENT_DIALOGUE_WIDTH}px"
            )
        if handles > EVENT_RUNTIME_GLYPH_CAP:
            raise ValueError(
                f"PSP EVENT row needs {handles} handles; runtime cap is "
                f"{EVENT_RUNTIME_GLYPH_CAP}"
            )
    return tuple(lines)


def encode_event_translation(text: str) -> bytes:
    """Encode one shared EVENT page into the markerless PSP byte grammar."""

    text = _normalize_event_text(text)
    output = bytearray()
    position = 0
    for match in _TOKEN_PATTERN.finditer(text):
        literal = text[position : match.start()]
        if "{" in literal or "}" in literal:
            raise ValueError(f"unknown PSP EVENT token in {literal!r}")
        _append_literal(output, literal)
        output.extend(encode_logical_word(_token_code(match.group(1))))
        position = match.end()
    literal = text[position:]
    if "{" in literal or "}" in literal:
        raise ValueError(f"unknown PSP EVENT token in {literal!r}")
    _append_literal(output, literal)
    return bytes(output)


def _wrapped_page_boundary(boundary_codes: tuple[int, ...]) -> tuple[int, ...]:
    """Derive a native wait/page-clear separator without copying a terminator."""

    prefix = (0x8003,) if 0x8003 in boundary_codes else ()
    return (*prefix, 0x8002)


def _read_script_pointers(data: bytes, table_offset: int) -> tuple[int, ...]:
    """Read the PSP port's zero-terminated, nondecreasing script table."""

    pointers: list[int] = []
    cursor = SCRIPT_TABLE_OFFSET
    while cursor + 2 <= SCRIPT_BODY_OFFSET:
        pointer = struct.unpack_from(">H", data, cursor)[0]
        cursor += 2
        if pointer == 0:
            break
        if pointers and pointer < pointers[-1]:
            raise ValueError("PSP EVENT script pointers decrease")
        pointers.append(pointer)
    else:
        raise ValueError("PSP EVENT script table has no zero terminator")
    if not pointers:
        raise ValueError("PSP EVENT script table has no entries")
    script_limit = (table_offset - SCRIPT_BODY_OFFSET) // 2
    if pointers[-1] >= script_limit:
        raise ValueError("PSP EVENT script body exceeds its text-pointer table")
    return tuple(pointers)


def _script_menu_descriptors(
    data: bytes,
    binding: EveBinding,
) -> tuple[EventOptionDescriptor, ...]:
    pointers = _read_script_pointers(data, binding.table_offset)
    final_end = (binding.table_offset - SCRIPT_BODY_OFFSET) // 2
    descriptors = []
    for script_index, (start, end) in enumerate(
        zip(pointers, (*pointers[1:], final_end), strict=True)
    ):
        if end <= start:
            continue
        words = struct.unpack_from(
            f">{end - start}H",
            data,
            SCRIPT_BODY_OFFSET + start * 2,
        )
        for position, opcode in enumerate(words):
            if opcode != 3:
                continue
            if position and not (position >= 2 and words[position - 2] == 1):
                continue
            if position + 1 >= len(words):
                continue
            option_count = words[position + 1]
            options_end = position + 2 + option_count * 2
            if not 1 <= option_count <= 4 or options_end > len(words):
                continue
            labels = words[position + 2 : options_end : 2]
            targets = words[position + 3 : options_end : 2]
            if all(target < len(pointers) for target in targets):
                descriptors.append(
                    EventOptionDescriptor(
                        script_index=script_index,
                        script_start_word=start,
                        opcode_position=position,
                        prompt_message=words[position - 1] if position else None,
                        label_messages=labels,
                        target_scripts=targets,
                    )
                )
    return tuple(descriptors)


def _event_option_descriptor_sha256(
    descriptors: tuple[EventOptionDescriptor, ...],
) -> str:
    """Fingerprint scanner output without persisting the PSP script inventory."""

    payload = {
        "version": 1,
        "descriptors": [
            [
                descriptor.script_index,
                descriptor.script_start_word,
                descriptor.opcode_position,
                descriptor.prompt_message,
                list(descriptor.label_messages),
                list(descriptor.target_scripts),
            ]
            for descriptor in descriptors
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _script_menu_messages(data: bytes, binding: EveBinding) -> frozenset[int]:
    return frozenset(
        message
        for descriptor in _script_menu_descriptors(data, binding)
        for message in descriptor.label_messages
    )


def _raw_message_indices(data: bytes, binding: EveBinding) -> tuple[int, ...]:
    values = _script_menu_messages(data, binding) | _FORCED_RAW_MESSAGES.get(
        binding.name,
        frozenset(),
    )
    invalid = sorted(
        index for index in values if not 0 <= index < binding.expected_messages
    )
    if invalid:
        raise ValueError(
            f"PSP {binding.name} raw-reader messages are invalid: {invalid}"
        )
    expected = EXPECTED_RAW_MESSAGE_COUNTS[binding.name]
    if len(values) != expected:
        raise ValueError(
            f"PSP {binding.name} raw-reader inventory has {len(values)} messages; "
            f"expected {expected}"
        )
    return tuple(sorted(values))


def _translated_option_message_indices(
    data: bytes,
    binding: EveBinding,
    contract: EventOptionBankContract | None,
) -> tuple[int, ...]:
    if contract is None:
        return ()
    if contract.name != binding.name:
        raise ValueError(f"PSP {binding.name} EVENT option contract has wrong bank")
    descriptors = _script_menu_descriptors(data, binding)
    message_indices = tuple(
        sorted(
            {
                message
                for descriptor in descriptors
                for message in descriptor.label_messages
            }
        )
    )
    actual_counts = (
        len(descriptors),
        sum(len(descriptor.label_messages) for descriptor in descriptors),
        len(message_indices),
    )
    expected_counts = (
        contract.descriptor_count,
        contract.slot_count,
        contract.message_count,
    )
    actual_sha256 = _event_option_descriptor_sha256(descriptors)
    if actual_counts != expected_counts or actual_sha256 != contract.descriptor_sha256:
        raise ValueError(
            f"PSP {binding.name} EVENT option scan changed: "
            f"found {actual_counts} / {actual_sha256}, "
            f"expected {expected_counts} / {contract.descriptor_sha256}"
        )
    exception_indices = {
        index
        for rows in (contract.preserved_prefixes, contract.required_insert_codes)
        for index, _codes in rows
    }
    invalid_exceptions = sorted(exception_indices - set(message_indices))
    if invalid_exceptions:
        raise ValueError(
            f"PSP {binding.name} EVENT option controls reference non-options "
            f"{invalid_exceptions}"
        )
    return message_indices


def _load_event_binding(
    path: Path,
    binding: EveBinding,
    source: bytes,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Resolve one compact physical-page binding into compiler page rows."""

    document = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    if set(document) != {
        "version",
        "bank",
        "member_index",
        "member_sha256",
        "table_offset",
        "message_count",
        "assets",
    }:
        raise ValueError(f"{path}: PSP EVENT binding fields changed")
    expected_digest = "sha256:" + hashlib.sha256(source).hexdigest()
    if (
        document["version"] != 1
        or document["bank"] != binding.name
        or document["member_index"] != binding.member_index
        or document["member_sha256"] != expected_digest
        or _hex_word(document["table_offset"], f"{path}: table offset", prefixed=True)
        != binding.table_offset
        or document["message_count"] != binding.expected_messages
    ):
        raise ValueError(f"{path}: PSP EVENT physical contract changed")
    bank = PspEveBank.parse(source, binding.table_offset)
    if len(bank.messages) != binding.expected_messages:
        raise ValueError(f"{path}: PSP EVENT source message inventory changed")
    assets = _array(document["assets"], f"{path}: assets")
    if len(assets) != len(bank.messages):
        raise ValueError(f"{path}: PSP EVENT asset-message inventory changed")
    records: dict[str, dict[str, Any]] = {}
    message_rows = []
    for message, raw_assets in zip(bank.messages, assets, strict=True):
        pages = payload_pages(message)
        page_assets = _array(raw_assets, f"{path}: message {message.index}")
        if len(page_assets) != len(pages):
            raise ValueError(
                f"{path}: message {message.index} page binding inventory changed"
            )
        page_rows = []
        for page, identity in zip(pages, page_assets, strict=True):
            if identity is not None and not isinstance(identity, str):
                raise ValueError(
                    f"{path}: message {message.index} page {page.index} has "
                    "an invalid asset identity"
                )
            page_rows.append({"record_id": identity})
            if identity is not None and identity not in records:
                reference, translation = load_asset_field(identity)
                if not reference or not translation:
                    raise ValueError(f"{path}: untranslated EVENT asset {identity!r}")
                records[identity] = {"id": identity, "jp": reference, "tr": translation}
        message_rows.append({"pages": page_rows})
    return {"messages": message_rows}, records


def _encode_raw_option_words(text: str) -> tuple[int, ...]:
    """Encode authoring text as direct-reader u16 words, never packed bytes."""

    normalized = _normalize_event_text(text)
    if "\n" in normalized or "{n}" in normalized:
        raise ValueError("PSP EVENT option must be one literal row")
    words: list[int] = []
    position = 0
    for match in _TOKEN_PATTERN.finditer(normalized):
        literal = normalized[position : match.start()]
        if "{" in literal or "}" in literal:
            raise ValueError(f"unknown PSP EVENT option token in {literal!r}")
        words.extend(glyph_code_for_character(character) for character in literal)
        code = _token_code(match.group(1))
        if code >= 0x8000 and code not in _EVENT_INSERT_CODES:
            raise ValueError(
                f"PSP EVENT option token {{{match.group(1)}}} is not an insert"
            )
        words.append(code)
        position = match.end()
    literal = normalized[position:]
    if "{" in literal or "}" in literal:
        raise ValueError(f"unknown PSP EVENT option token in {literal!r}")
    words.extend(glyph_code_for_character(character) for character in literal)
    return tuple(words)


def _encode_raw_option_translation(
    binding: EveBinding,
    message: PspEveMessage,
    message_row: dict[str, Any],
    records: dict[str, dict[str, Any]],
    measure_ascii: Callable[[str], int],
    option_contract: EventOptionBankContract | None = None,
    display_records: dict[str, EventOptionDisplayRecord] | None = None,
) -> tuple[bytes, tuple[str, ...]]:
    """Encode one checked batch-menu label as raw Ark/insert u16 words."""

    pages = payload_pages(message)
    page_rows = _array(
        message_row.get("pages"),
        f"PSP {binding.name} option message {message.index} pages",
    )
    if len(pages) != 1 or len(page_rows) != 1:
        raise ValueError(
            f"PSP {binding.name} option message {message.index} must have one page"
        )
    page = pages[0]
    prefix_codes = (
        dict(option_contract.preserved_prefixes).get(message.index, ())
        if option_contract
        else ()
    )
    if tuple(page.words[: len(prefix_codes)]) != prefix_codes:
        raise ValueError(
            f"PSP {binding.name} option message {message.index} control prefix changed"
        )
    source_content = page.words[len(prefix_codes) :]
    unsupported_controls = tuple(
        word
        for word in source_content
        if word >= 0x8000 and word not in _EVENT_INSERT_CODES
    )
    if unsupported_controls:
        raise ValueError(
            f"PSP {binding.name} option message {message.index} has unsupported "
            f"inline controls {unsupported_controls}"
        )
    page_row = _object(
        page_rows[0],
        f"PSP {binding.name} option message {message.index} page 0",
    )
    record_id = page_row.get("record_id")
    if not isinstance(record_id, str):
        raise ValueError(
            f"PSP {binding.name} option message {message.index} has no shared record"
        )
    try:
        source_record = records[record_id]
    except KeyError as error:
        raise ValueError(
            f"PSP {binding.name} option references unknown record {record_id!r}"
        ) from error
    override_id = (
        dict(option_contract.display_overrides).get(record_id)
        if option_contract is not None
        else None
    )
    if override_id is None:
        translation = _normalize_event_text(source_record["tr"])
    else:
        try:
            display = (display_records or {})[override_id]
        except KeyError as error:
            raise ValueError(
                f"PSP {binding.name} option display record {override_id!r} vanished"
            ) from error
        if display.source_record_id != record_id or display.jp != source_record.get(
            "jp"
        ):
            raise ValueError(
                f"PSP {binding.name} option display record {override_id!r} "
                "lost its source identity"
            )
        translation = _normalize_event_text(display.translation)
    pixels, handles = event_row_layout(translation, measure_ascii)
    if handles > EVENT_OPTION_HANDLE_POOL:
        raise ValueError(
            f"PSP {binding.name} option {record_id!r} needs {handles} "
            f"handles; batch pool is {EVENT_OPTION_HANDLE_POOL}"
        )
    if pixels > EVENT_OPTION_STACKED_WIDTH:
        raise ValueError(
            f"PSP {binding.name} option {record_id!r} is {pixels}px; "
            f"stacked width is {EVENT_OPTION_STACKED_WIDTH}px"
        )
    translation_words = _encode_raw_option_words(translation)
    actual_insert_codes = tuple(
        word for word in translation_words if word in _EVENT_INSERT_CODES
    )
    required_insert_codes = (
        dict(option_contract.required_insert_codes).get(message.index, ())
        if option_contract is not None
        else ()
    )
    if actual_insert_codes != required_insert_codes:
        raise ValueError(
            f"PSP {binding.name} option message {message.index} insert ABI changed: "
            f"found {actual_insert_codes}, expected {required_insert_codes}"
        )
    words = (
        *prefix_codes,
        *translation_words,
        *page.boundary_codes,
    )
    if 0x8000 not in page.boundary_codes:
        raise ValueError(
            f"PSP {binding.name} option message {message.index} lost its terminator"
        )
    return struct.pack(f">{len(words)}H", *words), (record_id,)


def _validate_event_option_layouts(
    data: bytes,
    binding: EveBinding,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
    measure_ascii: Callable[[str], int],
    option_contract: EventOptionBankContract,
    display_records: dict[str, EventOptionDisplayRecord],
) -> None:
    """Check each menu against its real grid geometry and shared handle pool."""

    messages = _array(manifest.get("messages"), f"PSP {binding.name} messages")
    overrides = dict(option_contract.display_overrides)
    for descriptor in _script_menu_descriptors(data, binding):
        width = (
            EVENT_OPTION_STACKED_WIDTH
            if len(descriptor.label_messages) <= 2
            else EVENT_OPTION_GRID_WIDTH
        )
        total_handles = 0
        for message_index in descriptor.label_messages:
            message = _object(
                messages[message_index],
                f"PSP {binding.name} option message {message_index}",
            )
            pages = _array(
                message.get("pages"),
                f"PSP {binding.name} option message {message_index} pages",
            )
            if len(pages) != 1:
                raise ValueError(
                    f"PSP {binding.name} option message {message_index} "
                    "must own exactly one page"
                )
            page = _object(
                pages[0],
                f"PSP {binding.name} option message {message_index} page",
            )
            record_id = page.get("record_id")
            if not isinstance(record_id, str) or record_id not in records:
                raise ValueError(
                    f"PSP {binding.name} option message {message_index} "
                    "has no shared record"
                )
            translation = records[record_id]["tr"]
            override_id = overrides.get(record_id)
            if override_id is not None:
                translation = display_records[override_id].translation
            pixels, handles = event_row_layout(translation, measure_ascii)
            if pixels > width:
                raise ValueError(
                    f"PSP {binding.name} option {record_id!r} is {pixels}px; "
                    f"{len(descriptor.label_messages)}-choice width is {width}px"
                )
            total_handles += handles
        if total_handles > EVENT_OPTION_HANDLE_POOL:
            raise ValueError(
                f"PSP {binding.name} script {descriptor.script_index} options "
                f"need {total_handles} handles; batch pool is "
                f"{EVENT_OPTION_HANDLE_POOL}"
            )


def _repack_message(
    binding: EveBinding,
    message: PspEveMessage,
    message_row: dict[str, Any],
    records: dict[str, dict[str, Any]],
    raw_messages: frozenset[int],
    measure_ascii: Callable[[str], int],
    translated_option_messages: frozenset[int] = frozenset(),
    option_contract: EventOptionBankContract | None = None,
    display_records: dict[str, EventOptionDisplayRecord] | None = None,
) -> tuple[bytes, tuple[str, ...]]:
    source = _message_bytes(message)
    if message.index in translated_option_messages:
        return _encode_raw_option_translation(
            binding,
            message,
            message_row,
            records,
            measure_ascii,
            option_contract,
            display_records,
        )
    if message.index in raw_messages:
        return source, ()

    pages = payload_pages(message)
    page_rows = _array(
        message_row.get("pages"),
        f"PSP {binding.name} message {message.index} pages",
    )
    if not pages:
        if page_rows:
            raise ValueError(f"PSP {binding.name} empty message has bound pages")
        return source, ()
    if len(page_rows) != len(pages):
        raise ValueError(f"PSP {binding.name} message page inventory changed")
    checked_page_rows = tuple(
        _object(
            page_value,
            f"PSP {binding.name} message {message.index} page {page.index}",
        )
        for page, page_value in zip(pages, page_rows, strict=True)
    )
    page_record_ids = tuple(page_row.get("record_id") for page_row in checked_page_rows)
    if any(record_id is None for record_id in page_record_ids) and any(
        record_id is not None for record_id in page_record_ids
    ):
        raise ValueError(
            f"PSP {binding.name} message {message.index} mixes packed and native pages"
        )

    output = bytearray()
    translated = []
    for page, page_row in zip(pages, checked_page_rows, strict=True):
        record_id = page_row.get("record_id")
        if record_id is None:
            for word in (*page.words, *page.boundary_codes):
                output.extend(encode_logical_word(word))
            continue
        if not isinstance(record_id, str):
            raise ValueError(
                f"PSP {binding.name} message {message.index} page {page.index} "
                "has an invalid shared record ID"
            )
        try:
            record = records[record_id]
        except KeyError as error:
            raise ValueError(
                f"PSP {binding.name} page references unknown record {record_id!r}"
            ) from error
        source_text_sha256 = page_row.get("source_text_sha256")
        if source_text_sha256 is not None:
            actual_source_text_sha256 = (
                "sha256:" + hashlib.sha256(record["jp"].encode("utf-8")).hexdigest()
            )
            if actual_source_text_sha256 != source_text_sha256:
                raise ValueError(
                    f"PSP {binding.name} message {message.index} page {page.index} "
                    f"record {record_id!r} lost its PSP source identity"
                )
        translation = record["tr"]
        lines = wrap_event_translation(translation, measure_ascii)
        subpage_count = max(
            1,
            -(-len(lines) // EVENT_LINES_PER_PAGE),
        )
        line_position = 0
        for subpage_index in range(subpage_count):
            remaining = len(lines) - line_position
            pages_left = subpage_count - subpage_index
            line_count = -(-remaining // pages_left)
            if not 1 <= line_count <= EVENT_LINES_PER_PAGE:
                raise ValueError("PSP EVENT page exceeds its three-row capacity")
            page_lines = lines[line_position : line_position + line_count]
            line_position += line_count
            for line_index, line in enumerate(page_lines):
                if line_index:
                    output.extend(encode_logical_word(0x8001))
                output.extend(encode_event_translation(line))
            if subpage_index < subpage_count - 1:
                for boundary in _wrapped_page_boundary(page.boundary_codes):
                    output.extend(encode_logical_word(boundary))
        for boundary in page.boundary_codes:
            output.extend(encode_logical_word(boundary))
        translated.append(record_id)

    logical = bytes(output)
    if b"\x80\x00" not in logical:
        raise ValueError(
            f"PSP {binding.name} message {message.index} lost its terminator"
        )
    if len(logical) & 1:
        logical += b"\x00"
    return logical, tuple(translated)


def _build_bank(
    source: bytes,
    binding: EveBinding,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
    measure_ascii: Callable[[str], int],
    option_contract: EventOptionBankContract | None = None,
    display_records: dict[str, EventOptionDisplayRecord] | None = None,
    dvlname_table: bytes | None = None,
) -> EventBankBuild:
    bank = PspEveBank.parse(source, binding.table_offset)
    original_end = MESSAGE_BODY_OFFSET + bank.messages[-1].end_word * 2
    if any(source[original_end:]):
        raise ValueError(
            f"PSP {binding.name} has nonzero bytes after its final EVENT message"
        )
    message_rows = _array(manifest.get("messages"), f"PSP {binding.name} messages")
    if len(message_rows) != len(bank.messages):
        raise ValueError(f"PSP {binding.name} checked message inventory changed")
    raw_indices = _raw_message_indices(source, binding)
    raw_messages = frozenset(raw_indices)
    translated_option_indices = _translated_option_message_indices(
        source,
        binding,
        option_contract,
    )
    translated_option_messages = frozenset(translated_option_indices)
    if not translated_option_messages <= raw_messages:
        raise ValueError(
            f"PSP {binding.name} translated options escaped the raw-reader inventory"
        )
    if option_contract is not None:
        option_record_ids = set()
        for message_index in translated_option_indices:
            option_row = _object(
                message_rows[message_index],
                f"PSP {binding.name} option message {message_index}",
            )
            option_pages = _array(
                option_row.get("pages"),
                f"PSP {binding.name} option message {message_index} pages",
            )
            if len(option_pages) != 1:
                raise ValueError(
                    f"PSP {binding.name} option message {message_index} "
                    "must bind one shared record"
                )
            option_page = _object(
                option_pages[0],
                f"PSP {binding.name} option message {message_index} page 0",
            )
            option_record_id = option_page.get("record_id")
            if not isinstance(option_record_id, str):
                raise ValueError(
                    f"PSP {binding.name} option message {message_index} "
                    "lost its shared record"
                )
            option_record_ids.add(option_record_id)
        override_sources = {
            source_record_id
            for source_record_id, _display_record_id in option_contract.display_overrides
        }
        if not override_sources <= option_record_ids:
            raise ValueError(
                f"PSP {binding.name} EVENT option display override is not an option"
            )
        if display_records is None:
            raise ValueError(
                f"PSP {binding.name} EVENT option displays are unavailable"
            )
        _validate_event_option_layouts(
            source,
            binding,
            manifest,
            records,
            measure_ascii,
            option_contract,
            display_records,
        )

    payloads = []
    translated_record_ids: list[str] = []
    translated_messages = 0
    for message, value in zip(bank.messages, message_rows, strict=True):
        message_row = _object(value, f"PSP {binding.name} message {message.index}")
        payload, translated = _repack_message(
            binding,
            message,
            message_row,
            records,
            raw_messages,
            measure_ascii,
            translated_option_messages,
            option_contract,
            display_records,
        )
        if len(payload) & 1:
            raise ValueError(
                f"PSP {binding.name} message {message.index} is not word-aligned"
            )
        if (
            message.index in raw_messages
            and message.index not in translated_option_messages
            and payload != _message_bytes(message)
        ):
            raise ValueError(f"PSP {binding.name} raw message {message.index} changed")
        payloads.append(payload)
        if translated:
            translated_messages += 1
            translated_record_ids.extend(translated)

    pointers = []
    cursor_words = 0
    for payload in payloads:
        if cursor_words > 0xFFFF:
            raise ValueError(f"PSP {binding.name} message pointer exceeds u16 capacity")
        pointers.append(cursor_words)
        cursor_words += len(payload) // 2
    body_capacity = len(source) - MESSAGE_BODY_OFFSET
    used_body_bytes = cursor_words * 2
    dvlname_table_offset = None
    if dvlname_table is not None:
        if not isinstance(dvlname_table, bytes) or not dvlname_table:
            raise ValueError("PSP EVENT DVLNAME runtime table must be nonempty bytes")
        header_offset = body_capacity - DVLNAME_RUNTIME_HEADER_SIZE
        dvlname_table_offset = (header_offset - len(dvlname_table)) & ~3
        if dvlname_table_offset < used_body_bytes:
            raise ValueError(
                f"PSP {binding.name} DVLNAME table at {dvlname_table_offset} "
                f"overlaps {used_body_bytes} message bytes"
            )
    if used_body_bytes > body_capacity:
        raise ValueError(
            f"PSP {binding.name} packed body uses {used_body_bytes} bytes; "
            f"capacity is {body_capacity}"
        )

    output = bytearray(source)
    struct.pack_into(
        f">{len(pointers) + 1}H",
        output,
        binding.table_offset,
        *pointers,
        0,
    )
    body = b"".join(payloads)
    output[MESSAGE_BODY_OFFSET:] = body + bytes(body_capacity - len(body))
    if dvlname_table_offset is not None:
        assert dvlname_table is not None
        table_start = MESSAGE_BODY_OFFSET + dvlname_table_offset
        output[table_start : table_start + len(dvlname_table)] = dvlname_table
        header_start = MESSAGE_BODY_OFFSET + body_capacity - DVLNAME_RUNTIME_HEADER_SIZE
        struct.pack_into(
            "<II",
            output,
            header_start,
            DVLNAME_RUNTIME_MAGIC,
            dvlname_table_offset,
        )
    rebuilt = bytes(output)

    for index, (start_word, payload) in enumerate(zip(pointers, payloads, strict=True)):
        start = MESSAGE_BODY_OFFSET + start_word * 2
        if rebuilt[start : start + len(payload)] != payload:
            raise ValueError(f"PSP {binding.name} message {index} failed readback")
    tail_start = MESSAGE_BODY_OFFSET + used_body_bytes
    if dvlname_table_offset is None:
        if any(rebuilt[tail_start:]):
            raise ValueError(f"PSP {binding.name} packed body tail is not zero-filled")
    else:
        assert dvlname_table is not None
        table_start = MESSAGE_BODY_OFFSET + dvlname_table_offset
        header_start = MESSAGE_BODY_OFFSET + body_capacity - DVLNAME_RUNTIME_HEADER_SIZE
        if any(rebuilt[tail_start:table_start]):
            raise ValueError(
                f"PSP {binding.name} DVLNAME prefix gap is not zero-filled"
            )
        if rebuilt[table_start : table_start + len(dvlname_table)] != dvlname_table:
            raise ValueError(f"PSP {binding.name} DVLNAME table failed readback")
        if any(rebuilt[table_start + len(dvlname_table) : header_start]):
            raise ValueError(
                f"PSP {binding.name} DVLNAME suffix gap is not zero-filled"
            )
    changed_byte_count = sum(
        before != after for before, after in zip(source, rebuilt, strict=True)
    )
    return EventBankBuild(
        name=binding.name,
        member_index=binding.member_index,
        data=rebuilt,
        message_count=len(payloads),
        translated_message_count=translated_messages,
        translated_record_ids=tuple(translated_record_ids),
        raw_message_indices=raw_indices,
        translated_option_message_indices=translated_option_indices,
        option_descriptor_count=(
            option_contract.descriptor_count if option_contract is not None else 0
        ),
        option_slot_count=(
            option_contract.slot_count if option_contract is not None else 0
        ),
        option_display_override_count=(
            len(option_contract.display_overrides) if option_contract is not None else 0
        ),
        used_body_bytes=used_body_bytes,
        body_capacity_bytes=body_capacity,
        dvlname_table_offset=dvlname_table_offset,
        dvlname_table_size=len(dvlname_table) if dvlname_table is not None else 0,
        changed_byte_count=changed_byte_count,
    )


def build_event_corpus(
    source_eve_files: bytes,
    *,
    measure_ascii: Callable[[str], int],
    bindings_root: Path = EVENT_BINDINGS_ROOT,
    option_config_path: Path = EVENT_OPTION_CONFIG_PATH,
    option_corpus_path: Path | None = None,
) -> EventCorpusBuild:
    """Build the five standard EVENT banks from canonical semantic assets."""

    if not isinstance(source_eve_files, bytes):
        raise TypeError("PSP EVENT repack source must be bytes")
    option_corpus_path = (
        EVENT_OPTION_CORPUS_PATH
        if option_corpus_path is None
        else Path(option_corpus_path)
    )
    option_contract = load_event_option_contract(
        option_config_path,
        option_corpus_path,
    )
    option_banks = option_contract.banks_by_name
    display_records = option_contract.display_records_by_id
    archive = PspEveFiles.parse(source_eve_files).archive
    dvlname_table = build_psp_dvlname_runtime_table(load_psp_dvlname_text())
    replacements = {}
    banks = []
    corpus_paths: set[str] = set()
    all_bound_record_ids: set[str] = set()
    translated_record_ids: set[str] = set()
    for binding in EVENT_BINDINGS:
        manifest_path = bindings_root / f"{binding.name}.EVE.json"
        source_member = archive.members[binding.member_index].data
        manifest, records = _load_event_binding(
            manifest_path,
            binding,
            source_member,
        )
        corpus_paths.update(identity.partition("#")[0] for identity in records)
        all_bound_record_ids.update(records)
        result = _build_bank(
            source_member,
            binding,
            manifest,
            records,
            measure_ascii,
            option_banks[binding.name],
            display_records,
            dvlname_table,
        )
        replacements[binding.member_index] = result.data
        banks.append(result)
        translated_record_ids.update(result.translated_record_ids)

    rebuilt = archive.rebuild(replacements)
    if len(rebuilt) != len(source_eve_files):
        raise ValueError("PSP EVENT repack changed eve_files.bin size")
    checked = PspPack.parse(rebuilt)
    changed_members = tuple(
        before.index
        for before, after in zip(archive.members, checked.members, strict=True)
        if before.data != after.data
    )
    expected_members = tuple(binding.member_index for binding in EVENT_BINDINGS)
    if changed_members != expected_members:
        raise ValueError(
            f"PSP EVENT repack changed members {changed_members}; "
            f"expected {expected_members}"
        )
    changed_byte_count = sum(
        before != after for before, after in zip(source_eve_files, rebuilt, strict=True)
    )
    translated = tuple(sorted(translated_record_ids))
    preserved = tuple(sorted(all_bound_record_ids - translated_record_ids))
    return EventCorpusBuild(
        eve_files=rebuilt,
        banks=tuple(banks),
        corpus_paths=tuple(sorted(corpus_paths)),
        translated_record_ids=translated,
        preserved_record_ids=preserved,
        changed_member_indices=changed_members,
        changed_byte_count=changed_byte_count,
    )


__all__ = [
    "DVLNAME_RUNTIME_HEADER_SIZE",
    "EVENT_BINDINGS",
    "EVENT_DIALOGUE_WIDTH",
    "EVENT_LINES_PER_PAGE",
    "EVENT_BINDINGS_ROOT",
    "EVENT_OPTION_CONFIG_PATH",
    "EVENT_OPTION_CORPUS_PATH",
    "EVENT_OPTION_GRID_WIDTH",
    "EVENT_OPTION_HANDLE_POOL",
    "EVENT_OPTION_STACKED_WIDTH",
    "EVENT_RUNTIME_GLYPH_CAP",
    "EXPECTED_RAW_MESSAGE_COUNTS",
    "EventBankBuild",
    "EventCorpusBuild",
    "EventOptionBankContract",
    "EventOptionContract",
    "EventOptionDescriptor",
    "EventOptionDisplayRecord",
    "build_event_corpus",
    "encode_event_translation",
    "event_row_layout",
    "load_event_option_contract",
    "wrap_event_translation",
]
