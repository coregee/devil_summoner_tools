"""Build the first source-pinned PSP combat-dialogue publication tranche.

Combat talk uses the same packed byte cursor and Ark/VWF renderer as standard
EVENT dialogue, but it does not use the standard EVENT control vocabulary.
This module therefore owns a deliberately separate codec for the combat VM and
publishes only ``BOSSTALK.EVE`` member 22.  Combat menu opcodes and their raw
u16 label reader are outside this tranche.
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
from psp.text.util.assets import load_asset_field

from .event_corpus import payload_pages
from .event_bank import MESSAGE_BODY_OFFSET, EveBinding, PspEveBank, PspEveMessage
from .event_packed import decode_token, encode_ascii, encode_logical_word

COMBAT_DIALOGUE_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "combat_dialogue.json"
)
COMBAT_DIALOGUE_WIDTH = 300
COMBAT_LINES_PER_PAGE = 3
COMBAT_RUNTIME_GLYPH_CAP = 120
COMBAT_INSERT_WIDTH = 80
COMBAT_INSERT_HANDLE_COST = 8
SCRIPT_TABLE_OFFSET = 0x22
SCRIPT_BODY_OFFSET = 0x800

COMBAT_STRUCTURAL_CODES = frozenset(range(0x8000, 0x8005))
COMBAT_INSERT_CODES = frozenset(range(0x8010, 0x8018))
COMBAT_COLOR_CODES = frozenset(range(0x8020, 0x8027))
COMBAT_CONTROL_CODES = (
    COMBAT_STRUCTURAL_CODES | COMBAT_INSERT_CODES | COMBAT_COLOR_CODES
)

_STRUCTURAL_TOKENS = {
    "n": 0x8001,
    "PAGE": 0x8002,
    "WAIT": 0x8003,
    "BEAT": 0x8004,
}
_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
_NORMALIZE_CHARACTERS = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2014": "-",
    "\u2013": "-",
    "\u2026": "...",
    "\u00e9": "e",
    "\u3000": " ",
    "\u00a0": " ",
}

BOSSTALK_BINDING = EveBinding(22, "BOSSTALK", 16)
BOSSTALK_CORPUS = "battle/boss_dialogue.json"


@dataclass(frozen=True)
class CombatOrdinaryReference:
    """One combat-VM opcode-0 message reference."""

    script_index: int
    script_start_word: int
    message_index: int
    continuation_mode: int


@dataclass(frozen=True)
class CombatBankContract:
    """Checked source and ownership contract for one combat bank."""

    name: str
    member_index: int
    member_sha256: str
    table_offset: int
    body_offset: int
    message_count: int
    source_used_body_bytes: int
    body_capacity_bytes: int
    script_profile: str
    ordinary_reference_count: int
    ordinary_reference_sha256: str
    dvlname_tail: bool
    assets: tuple[str, ...]


@dataclass(frozen=True)
class CombatDialogueContract:
    """Top-level packed-renderer and combat-dialect contract."""

    bank: CombatBankContract


@dataclass(frozen=True)
class CombatBankBuild:
    """One fixed-size translated combat EVE member."""

    name: str
    member_index: int
    data: bytes
    message_count: int
    translated_record_ids: tuple[str, ...]
    ordinary_references: tuple[CombatOrdinaryReference, ...]
    used_body_bytes: int
    body_capacity_bytes: int
    changed_byte_count: int


@dataclass(frozen=True)
class CombatDialogueBuild:
    """Same-size ``eve_files.bin`` with only the BOSSTALK member published."""

    eve_files: bytes
    bank: CombatBankBuild
    corpus_paths: tuple[str, ...]
    translated_record_ids: tuple[str, ...]
    changed_member_indices: tuple[int, ...]
    changed_byte_count: int


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


def _digest(value: object, context: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
    ):
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _hex_offset(value: object, context: str) -> int:
    if not isinstance(value, str) or re.fullmatch(r"0x[0-9a-f]+", value) is None:
        raise ValueError(f"{context} must be a lowercase hexadecimal offset")
    return int(value, 16)


def _hex_codes(value: object, context: str) -> frozenset[int]:
    result = []
    for index, code in enumerate(_array(value, context)):
        if not isinstance(code, str) or re.fullmatch(r"[0-9a-f]{4}", code) is None:
            raise ValueError(
                f"{context} code {index} must be four lowercase hex digits"
            )
        result.append(int(code, 16))
    if len(result) != len(set(result)):
        raise ValueError(f"{context} contains duplicate controls")
    return frozenset(result)


def load_combat_dialogue_contract(
    path: Path = COMBAT_DIALOGUE_CONFIG_PATH,
) -> CombatDialogueContract:
    """Load the narrow canonical BOSSTALK renderer/source contract."""

    document = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    if set(document) != {"version", "platform", "renderer", "dialect", "bank"}:
        raise ValueError(f"{path}: combat-dialogue fields changed")
    if document["version"] != 1 or document["platform"] != "psp":
        raise ValueError(f"{path}: unsupported combat-dialogue contract")
    renderer = _object(document["renderer"], f"{path}: renderer")
    if renderer != {
        "profile": "common_event_packed_byte_v1",
        "dialogue_width": COMBAT_DIALOGUE_WIDTH,
        "lines_per_page": COMBAT_LINES_PER_PAGE,
        "runtime_glyph_cap": COMBAT_RUNTIME_GLYPH_CAP,
    }:
        raise ValueError(f"{path}: packed combat renderer contract changed")
    dialect = _object(document["dialect"], f"{path}: dialect")
    if set(dialect) != {"structural_codes", "insert_codes", "color_codes"}:
        raise ValueError(f"{path}: combat control-dialect fields changed")
    actual_dialect = (
        _hex_codes(dialect["structural_codes"], f"{path}: structural controls"),
        _hex_codes(dialect["insert_codes"], f"{path}: inserts"),
        _hex_codes(dialect["color_codes"], f"{path}: colors"),
    )
    if actual_dialect != (
        COMBAT_STRUCTURAL_CODES,
        COMBAT_INSERT_CODES,
        COMBAT_COLOR_CODES,
    ):
        raise ValueError(f"{path}: combat control dialect changed")
    row = _object(document["bank"], f"{path}: BOSSTALK")
    expected_fields = {
        "name",
        "member_index",
        "member_sha256",
        "table_offset",
        "body_offset",
        "message_count",
        "source_used_body_bytes",
        "body_capacity_bytes",
        "script_profile",
        "ordinary_reference_count",
        "ordinary_reference_sha256",
        "dvlname_tail",
        "assets",
    }
    if set(row) != expected_fields:
        raise ValueError(f"{path}: BOSSTALK fields changed")
    assets = tuple(_array(row["assets"], f"{path}: BOSSTALK assets"))
    if len(assets) != BOSSTALK_BINDING.expected_messages or any(
        not isinstance(identity, str) for identity in assets
    ):
        raise ValueError(f"{path}: BOSSTALK asset inventory changed")
    bank = CombatBankContract(
        name=row["name"],
        member_index=row["member_index"],
        member_sha256=_digest(row["member_sha256"], f"{path}: member digest"),
        table_offset=_hex_offset(row["table_offset"], f"{path}: table offset"),
        body_offset=_hex_offset(row["body_offset"], f"{path}: body offset"),
        message_count=_integer(row["message_count"], f"{path}: message count"),
        source_used_body_bytes=_integer(
            row["source_used_body_bytes"], f"{path}: used body bytes"
        ),
        body_capacity_bytes=_integer(
            row["body_capacity_bytes"], f"{path}: body capacity"
        ),
        script_profile=row["script_profile"],
        ordinary_reference_count=_integer(
            row["ordinary_reference_count"], f"{path}: reference count"
        ),
        ordinary_reference_sha256=_digest(
            row["ordinary_reference_sha256"], f"{path}: reference digest"
        ),
        dvlname_tail=row["dvlname_tail"],
        assets=assets,
    )
    if (
        bank.name != BOSSTALK_BINDING.name
        or bank.member_index != BOSSTALK_BINDING.member_index
        or bank.table_offset != BOSSTALK_BINDING.table_offset
        or bank.body_offset != MESSAGE_BODY_OFFSET
        or bank.message_count != BOSSTALK_BINDING.expected_messages
        or bank.script_profile != "ordinary_opcode_0"
        or bank.dvlname_tail is not False
    ):
        raise ValueError(f"{path}: BOSSTALK ownership changed")
    return CombatDialogueContract(bank=bank)


def _normalize_combat_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("PSP combat translation must be a string")
    for source, replacement in _NORMALIZE_CHARACTERS.items():
        text = text.replace(source, replacement)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def combat_token_code(token: str) -> int:
    """Resolve one token in the deliberately narrow combat control dialect."""

    named = _STRUCTURAL_TOKENS.get(token)
    if named is not None:
        return named
    kind, separator, value = token.partition(":")
    if separator != ":" or kind not in {"INS", "OP"}:
        raise ValueError(f"unknown PSP combat text token {{{token}}}")
    if re.fullmatch(r"[0-9A-Fa-f]{4}", value) is None:
        raise ValueError(f"PSP combat token {{{token}}} needs four hex digits")
    code = int(value, 16)
    if kind == "INS" and code not in COMBAT_INSERT_CODES:
        raise ValueError(f"PSP combat token {{{token}}} is not an insert")
    if kind == "OP" and code not in COMBAT_COLOR_CODES:
        raise ValueError(f"PSP combat token {{{token}}} is not a color control")
    return code


def _append_combat_literal(output: bytearray, literal: str) -> None:
    start = 0
    for index, character in enumerate(literal):
        if character != "\n":
            continue
        output.extend(encode_ascii(literal[start:index]))
        output.extend(encode_logical_word(0x8001))
        start = index + 1
    output.extend(encode_ascii(literal[start:]))


def encode_combat_translation(text: str) -> bytes:
    """Encode combat prose without admitting standard-EVENT-only controls."""

    normalized = _normalize_combat_text(text).replace("{n}", "\n")
    output = bytearray()
    position = 0
    for match in _TOKEN_PATTERN.finditer(normalized):
        literal = normalized[position : match.start()]
        if "{" in literal or "}" in literal:
            raise ValueError(f"unknown PSP combat token in {literal!r}")
        _append_combat_literal(output, literal)
        output.extend(encode_logical_word(combat_token_code(match.group(1))))
        position = match.end()
    literal = normalized[position:]
    if "{" in literal or "}" in literal:
        raise ValueError(f"unknown PSP combat token in {literal!r}")
    _append_combat_literal(output, literal)
    return bytes(output)


def _token_layout(token: str) -> tuple[int, int]:
    if token == "n":
        raise ValueError("PSP combat newline token cannot occur inside a row")
    code = combat_token_code(token)
    if code in COMBAT_INSERT_CODES:
        return COMBAT_INSERT_WIDTH, COMBAT_INSERT_HANDLE_COST
    return 0, 0


def combat_row_layout(
    text: str,
    measure_ascii: Callable[[str], int],
) -> tuple[int, int]:
    """Measure one row using the common renderer and combat token costs."""

    normalized = _normalize_combat_text(text)
    if "\n" in normalized or "{n}" in normalized:
        raise ValueError("PSP combat row measurement expects one explicit row")
    pixels = 0
    handles = 0
    position = 0
    for match in _TOKEN_PATTERN.finditer(normalized):
        literal = normalized[position : match.start()]
        if "{" in literal or "}" in literal:
            raise ValueError(f"unknown PSP combat token in {literal!r}")
        pixels += measure_ascii(literal)
        handles += len(literal)
        token_pixels, token_handles = _token_layout(match.group(1))
        pixels += token_pixels
        handles += token_handles
        position = match.end()
    literal = normalized[position:]
    if "{" in literal or "}" in literal:
        raise ValueError(f"unknown PSP combat token in {literal!r}")
    pixels += measure_ascii(literal)
    handles += len(literal)
    return pixels, handles


def wrap_combat_translation(
    text: str,
    measure_ascii: Callable[[str], int],
) -> tuple[str, ...]:
    """Wrap one BOSSTALK page to the common 300px/three-row ABI."""

    normalized = _normalize_combat_text(text).replace("{n}", "\n")
    lines: list[str] = []
    for explicit_line in normalized.split("\n"):
        words = [word for word in explicit_line.split(" ") if word]
        if not words:
            lines.append("")
            continue
        current: list[str] = []
        for word in words:
            word_pixels, word_handles = combat_row_layout(word, measure_ascii)
            if word_pixels > COMBAT_DIALOGUE_WIDTH:
                raise ValueError(
                    f"PSP combat word {word!r} is {word_pixels}px; "
                    f"dialogue width is {COMBAT_DIALOGUE_WIDTH}px"
                )
            if word_handles > COMBAT_RUNTIME_GLYPH_CAP:
                raise ValueError(
                    f"PSP combat word {word!r} needs {word_handles} handles; "
                    f"runtime cap is {COMBAT_RUNTIME_GLYPH_CAP}"
                )
            candidate = " ".join((*current, word))
            candidate_pixels, _candidate_handles = combat_row_layout(
                candidate, measure_ascii
            )
            if current and candidate_pixels > COMBAT_DIALOGUE_WIDTH:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        lines.append(" ".join(current))

    if not lines:
        lines.append("")
    if len(lines) > COMBAT_LINES_PER_PAGE:
        raise ValueError(
            f"PSP BOSSTALK page needs {len(lines)} rows; "
            f"capacity is {COMBAT_LINES_PER_PAGE}"
        )
    for line in lines:
        pixels, handles = combat_row_layout(line, measure_ascii)
        if pixels > COMBAT_DIALOGUE_WIDTH:
            raise ValueError(
                f"PSP combat row is {pixels}px; dialogue width is "
                f"{COMBAT_DIALOGUE_WIDTH}px"
            )
        if handles > COMBAT_RUNTIME_GLYPH_CAP:
            raise ValueError(
                f"PSP combat row needs {handles} handles; runtime cap is "
                f"{COMBAT_RUNTIME_GLYPH_CAP}"
            )
    return tuple(lines)


def packed_control_codes(data: bytes) -> tuple[int, ...]:
    """Return logical controls from one source-authorable packed byte stream."""

    controls = []
    cursor = 0
    while cursor < len(data):
        token = decode_token(data, cursor)
        if not token.is_glyph:
            controls.append(token.runtime_code)
        cursor += token.size
    return tuple(controls)


def _read_script_pointers(data: bytes, table_offset: int) -> tuple[int, ...]:
    pointers: list[int] = []
    cursor = SCRIPT_TABLE_OFFSET
    while cursor + 2 <= SCRIPT_BODY_OFFSET:
        pointer = struct.unpack_from(">H", data, cursor)[0]
        cursor += 2
        if pointer == 0:
            break
        if pointers and pointer < pointers[-1]:
            raise ValueError("PSP combat script pointers decrease")
        pointers.append(pointer)
    else:
        raise ValueError("PSP combat script table has no zero terminator")
    if not pointers:
        raise ValueError("PSP combat script table has no entries")
    script_limit = (table_offset - SCRIPT_BODY_OFFSET) // 2
    if pointers[-1] >= script_limit:
        raise ValueError("PSP combat script body exceeds its text-pointer table")
    return tuple(pointers)


def scan_ordinary_combat_references(
    data: bytes,
    binding: EveBinding = BOSSTALK_BINDING,
) -> tuple[CombatOrdinaryReference, ...]:
    """Scan only the proved four-word combat opcode-0 message form."""

    pointers = _read_script_pointers(data, binding.table_offset)
    final_end = (binding.table_offset - SCRIPT_BODY_OFFSET) // 2
    references = []
    menu_script_indices = []
    for script_index, (start, end) in enumerate(
        zip(pointers, (*pointers[1:], final_end), strict=True)
    ):
        if end <= start:
            continue
        words = list(
            struct.unpack_from(
                f">{end - start}H",
                data,
                SCRIPT_BODY_OFFSET + start * 2,
            )
        )
        if script_index == len(pointers) - 1:
            while words and words[-1] == 0:
                words.pop()
        if words and words[0] in {3, *range(10, 16)}:
            menu_script_indices.append(script_index)
        if (
            len(words) == 4
            and words[0] == 0
            and words[2] == 1
            and words[3] in {0x0080, 0x0083}
        ):
            references.append(
                CombatOrdinaryReference(
                    script_index=script_index,
                    script_start_word=start,
                    message_index=words[1],
                    continuation_mode=words[3],
                )
            )
    if menu_script_indices:
        raise ValueError(
            f"PSP {binding.name} unexpectedly owns combat menu scripts "
            f"{menu_script_indices}"
        )
    return tuple(references)


def _ordinary_reference_sha256(
    references: tuple[CombatOrdinaryReference, ...],
) -> str:
    payload = [
        [
            reference.script_index,
            reference.script_start_word,
            reference.message_index,
            reference.continuation_mode,
        ]
        for reference in references
    ]
    return _sha256(json.dumps(payload, separators=(",", ":")).encode("ascii"))


def _load_checked_inputs(
    source_member: bytes,
    contract: CombatDialogueContract,
) -> tuple[PspEveBank, tuple[dict[str, str], ...]]:
    """Resolve the 16 checked physical messages through canonical assets."""

    bank_contract = contract.bank
    bank = PspEveBank.parse(source_member, bank_contract.table_offset)
    if len(bank.messages) != bank_contract.message_count:
        raise ValueError("PSP BOSSTALK source message count changed")
    records = []
    for message, identity in zip(bank.messages, bank_contract.assets, strict=True):
        pages = payload_pages(message)
        if len(pages) != 1 or pages[0].boundary_codes != (0x8000,):
            raise ValueError(
                f"PSP BOSSTALK message {message.index} physical page changed"
            )
        reference, translation = load_asset_field(identity)
        if not reference or not translation:
            raise ValueError(f"PSP BOSSTALK asset {identity!r} is incomplete")
        records.append({"id": identity, "jp": reference, "tr": translation})
    return bank, tuple(records)


def _encode_message(
    message: PspEveMessage,
    translation: str,
    measure_ascii: Callable[[str], int],
) -> bytes:
    pages = payload_pages(message)
    if len(pages) != 1:
        raise ValueError(f"PSP BOSSTALK message {message.index} page count changed")
    page = pages[0]
    if page.boundary_codes != (0x8000,):
        raise ValueError(
            f"PSP BOSSTALK message {message.index} boundary controls changed"
        )
    lines = wrap_combat_translation(translation, measure_ascii)
    encoded = encode_combat_translation("\n".join(lines))
    unsupported_source_controls = tuple(
        word
        for word in page.words
        if word >= 0x8000 and word not in COMBAT_CONTROL_CODES
    )
    if unsupported_source_controls:
        raise ValueError(
            f"PSP BOSSTALK message {message.index} has unsupported combat "
            f"controls {unsupported_source_controls}"
        )
    source_controls = tuple(word for word in page.words if word in COMBAT_CONTROL_CODES)
    translated_controls = packed_control_codes(encoded)
    if translated_controls != source_controls:
        raise ValueError(
            f"PSP BOSSTALK message {message.index} control ABI changed: "
            f"found {translated_controls}, expected {source_controls}"
        )
    logical = encoded + encode_logical_word(0x8000)
    if len(logical) & 1:
        logical += b"\x00"
    return logical


def build_bosstalk_member(
    source_member: bytes,
    *,
    measure_ascii: Callable[[str], int],
    contract: CombatDialogueContract | None = None,
) -> CombatBankBuild:
    """Build the checked BOSSTALK member without mutating any other EVE bank."""

    if not isinstance(source_member, bytes):
        raise TypeError("PSP BOSSTALK source member must be bytes")
    contract = load_combat_dialogue_contract() if contract is None else contract
    bank_contract = contract.bank
    if _sha256(source_member) != bank_contract.member_sha256:
        raise ValueError("PSP BOSSTALK source member digest changed")
    bank, records = _load_checked_inputs(source_member, contract)
    source_used_body_bytes = bank.messages[-1].end_word * 2
    body_capacity = len(source_member) - MESSAGE_BODY_OFFSET
    if (
        source_used_body_bytes != bank_contract.source_used_body_bytes
        or body_capacity != bank_contract.body_capacity_bytes
    ):
        raise ValueError("PSP BOSSTALK source body geometry changed")
    source_tail_start = MESSAGE_BODY_OFFSET + source_used_body_bytes
    if any(source_member[source_tail_start:]):
        raise ValueError("PSP BOSSTALK source has a nonzero post-message tail")

    references = scan_ordinary_combat_references(source_member)
    if (
        len(references) != bank_contract.ordinary_reference_count
        or _ordinary_reference_sha256(references)
        != bank_contract.ordinary_reference_sha256
        or tuple(sorted(reference.message_index for reference in references))
        != tuple(range(bank_contract.message_count))
    ):
        raise ValueError("PSP BOSSTALK ordinary opcode-0 ownership changed")

    payloads = tuple(
        _encode_message(message, record["tr"], measure_ascii)
        for message, record in zip(bank.messages, records, strict=True)
    )
    pointers: list[int] = []
    cursor_words = 0
    for payload in payloads:
        if not payload or len(payload) & 1:
            raise ValueError("PSP BOSSTALK packed payload is not word-aligned")
        if cursor_words > 0xFFFF:
            raise ValueError("PSP BOSSTALK message pointer exceeds u16 capacity")
        pointers.append(cursor_words)
        cursor_words += len(payload) // 2
    used_body_bytes = cursor_words * 2
    if used_body_bytes > body_capacity:
        raise ValueError(
            f"PSP BOSSTALK packed body uses {used_body_bytes} bytes; "
            f"capacity is {body_capacity}"
        )

    output = bytearray(source_member)
    struct.pack_into(
        f">{len(pointers) + 1}H",
        output,
        bank_contract.table_offset,
        *pointers,
        0,
    )
    body = b"".join(payloads)
    output[MESSAGE_BODY_OFFSET:] = body + bytes(body_capacity - len(body))
    rebuilt = bytes(output)

    output_pointers = struct.unpack_from(
        f">{len(pointers) + 1}H", rebuilt, bank_contract.table_offset
    )
    if output_pointers != (*pointers, 0):
        raise ValueError("PSP BOSSTALK pointer table failed readback")
    for index, (start_word, payload) in enumerate(zip(pointers, payloads, strict=True)):
        start = MESSAGE_BODY_OFFSET + start_word * 2
        if rebuilt[start : start + len(payload)] != payload:
            raise ValueError(f"PSP BOSSTALK message {index} failed readback")
    if any(rebuilt[MESSAGE_BODY_OFFSET + used_body_bytes :]):
        raise ValueError("PSP BOSSTALK packed body tail is not zero-filled")

    source_inserts = {
        word
        for message in bank.messages
        for word in message.words
        if word in COMBAT_INSERT_CODES
    }
    if source_inserts or bank_contract.dvlname_tail:
        raise ValueError("PSP BOSSTALK unexpectedly requires a DVLNAME runtime tail")

    return CombatBankBuild(
        name=bank_contract.name,
        member_index=bank_contract.member_index,
        data=rebuilt,
        message_count=len(payloads),
        translated_record_ids=tuple(record["id"] for record in records),
        ordinary_references=references,
        used_body_bytes=used_body_bytes,
        body_capacity_bytes=body_capacity,
        changed_byte_count=sum(
            before != after
            for before, after in zip(source_member, rebuilt, strict=True)
        ),
    )


def build_bosstalk_dialogue(
    source_eve_files: bytes,
    *,
    measure_ascii: Callable[[str], int],
    config_path: Path = COMBAT_DIALOGUE_CONFIG_PATH,
) -> CombatDialogueBuild:
    """Publish BOSSTALK alone into a same-size, source-pinned EVE archive."""

    if not isinstance(source_eve_files, bytes):
        raise TypeError("PSP combat-dialogue source must be bytes")
    contract = load_combat_dialogue_contract(config_path)
    archive = PspPack.parse(source_eve_files)
    source_member = archive.members[contract.bank.member_index].data
    bank = build_bosstalk_member(
        source_member,
        measure_ascii=measure_ascii,
        contract=contract,
    )
    rebuilt = archive.rebuild({bank.member_index: bank.data})
    if len(rebuilt) != len(source_eve_files):
        raise ValueError("PSP BOSSTALK publication changed eve_files.bin size")
    checked = PspPack.parse(rebuilt)
    changed_members = tuple(
        before.index
        for before, after in zip(archive.members, checked.members, strict=True)
        if before.data != after.data
    )
    if changed_members != (bank.member_index,):
        raise ValueError(
            f"PSP BOSSTALK publication changed members {changed_members}; "
            f"expected {(bank.member_index,)}"
        )
    return CombatDialogueBuild(
        eve_files=rebuilt,
        bank=bank,
        corpus_paths=(BOSSTALK_CORPUS,),
        translated_record_ids=bank.translated_record_ids,
        changed_member_indices=changed_members,
        changed_byte_count=sum(
            before != after
            for before, after in zip(source_eve_files, rebuilt, strict=True)
        ),
    )


__all__ = [
    "BOSSTALK_BINDING",
    "BOSSTALK_CORPUS",
    "COMBAT_COLOR_CODES",
    "COMBAT_CONTROL_CODES",
    "COMBAT_DIALOGUE_CONFIG_PATH",
    "COMBAT_DIALOGUE_WIDTH",
    "COMBAT_INSERT_CODES",
    "COMBAT_LINES_PER_PAGE",
    "COMBAT_RUNTIME_GLYPH_CAP",
    "COMBAT_STRUCTURAL_CODES",
    "CombatBankBuild",
    "CombatDialogueBuild",
    "CombatDialogueContract",
    "CombatOrdinaryReference",
    "build_bosstalk_dialogue",
    "build_bosstalk_member",
    "combat_row_layout",
    "combat_token_code",
    "encode_combat_translation",
    "load_combat_dialogue_contract",
    "packed_control_codes",
    "scan_ordinary_combat_references",
    "wrap_combat_translation",
]
