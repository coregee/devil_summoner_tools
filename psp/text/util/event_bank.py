"""Structural PSP `eve_files.bin` and EVE-bank parsing."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

from psp.archive.pack import PspPack

POINTER_TABLE_OFFSET = 0x4800
MESSAGE_BODY_OFFSET = 0x5000
MESSAGE_TERMINATOR = 0x8000
PAGE_CLEAR_OP = 0x8002
PAGE_EDGE_OPS = frozenset({0x8002, 0x8003})
PAYLOAD_OPS = frozenset(
    {
        0x8006,
        0x8007,
        *range(0x8010, 0x8024),
    }
)


@dataclass(frozen=True)
class EveBinding:
    member_index: int
    name: str
    expected_messages: int
    table_offset: int = POINTER_TABLE_OFFSET


KNOWN_BANKS = (
    EveBinding(0, "SHOPSMP", 816, 0x47FE),
    EveBinding(1, "EVFILE_0", 472),
    EveBinding(2, "EVFILE_1", 329),
    EveBinding(3, "MESFILE", 240),
    EveBinding(4, "EVFILE_2", 90),
    EveBinding(7, "TLK_BST", 581),
    EveBinding(8, "KEMO", 543),
    EveBinding(9, "TLK_KOFU", 552),
    EveBinding(10, "NBL_M", 524),
    EveBinding(11, "TLK_HIRK", 579),
    EveBinding(12, "TLK_YNGM", 600),
    EveBinding(13, "GRL", 554),
    EveBinding(14, "TLK_BOY", 559),
    EveBinding(15, "CLD_F", 540),
    EveBinding(16, "TLK_LADY", 595),
    EveBinding(17, "TLK_CRZY", 569),
    EveBinding(18, "JIJY", 543),
    EveBinding(19, "CYNI", 553),
    EveBinding(20, "TLK_WEST", 565),
    EveBinding(21, "SLM", 384),
    EveBinding(22, "BOSSTALK", 16),
)


@dataclass(frozen=True)
class PspEveMessage:
    index: int
    start_word: int
    end_word: int
    words: tuple[int, ...]


@dataclass(frozen=True)
class PspEvePage:
    index: int
    content_start_word: int
    content_end_word: int
    boundary_codes: tuple[int, ...]
    words: tuple[int, ...]


def has_payload(words: tuple[int, ...]) -> bool:
    """Return whether a page contains text or a runtime substitution."""

    return any(not (word & 0x8000) or word in PAYLOAD_OPS for word in words)


def split_pages(message: PspEveMessage) -> tuple[PspEvePage, ...]:
    """Split one PSP message losslessly at its verified EVE page controls."""

    words = message.words
    try:
        text_end = words.index(MESSAGE_TERMINATOR)
    except ValueError:
        text_end = len(words)
    pages: list[PspEvePage] = []
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
        page_positions = [
            offset for offset, word in enumerate(run) if word in PAGE_EDGE_OPS
        ]
        if PAGE_CLEAR_OP not in run:
            continue

        first_page_op = run_start + page_positions[0]
        after_last_page_op = run_start + page_positions[-1] + 1
        later_payload = has_payload(words[after_last_page_op:text_end])

        if later_payload:
            if not has_payload(words[page_start:first_page_op]):
                continue
            pages.append(
                PspEvePage(
                    index=len(pages),
                    content_start_word=page_start,
                    content_end_word=first_page_op,
                    boundary_codes=words[first_page_op:after_last_page_op],
                    words=words[page_start:first_page_op],
                )
            )
            page_start = after_last_page_op
        else:
            pages.append(
                PspEvePage(
                    index=len(pages),
                    content_start_word=page_start,
                    content_end_word=first_page_op,
                    boundary_codes=words[first_page_op:],
                    words=words[page_start:first_page_op],
                )
            )
            page_start = len(words)
            break

    if page_start < len(words) or not pages:
        content_end = text_end
        while content_end > page_start and words[content_end - 1] == 0x8003:
            content_end -= 1
        pages.append(
            PspEvePage(
                index=len(pages),
                content_start_word=page_start,
                content_end_word=content_end,
                boundary_codes=words[content_end:],
                words=words[page_start:content_end],
            )
        )

    reconstructed = tuple(
        word
        for page in pages
        for segment in (page.words, page.boundary_codes)
        for word in segment
    )
    if reconstructed != words:
        raise ValueError(f"PSP EVE message {message.index} page split is not lossless")
    return tuple(pages)


@dataclass(frozen=True)
class PspEveBank:
    source_data: bytes
    table_offset: int
    pointers: tuple[int, ...]
    messages: tuple[PspEveMessage, ...]

    @classmethod
    def parse(
        cls,
        data: bytes,
        table_offset: int = POINTER_TABLE_OFFSET,
    ) -> "PspEveBank":
        if len(data) <= MESSAGE_BODY_OFFSET:
            raise ValueError("PSP EVE bank is shorter than its message body offset")
        if not 0 <= table_offset < MESSAGE_BODY_OFFSET:
            raise ValueError("PSP EVE pointer table offset is outside the bank")

        first = struct.unpack_from(">H", data, table_offset)[0]
        if first != 0:
            raise ValueError(f"PSP EVE first pointer is {first:#x}, expected zero")
        pointers = [first]
        cursor = table_offset + 2
        while cursor + 2 <= MESSAGE_BODY_OFFSET:
            pointer = struct.unpack_from(">H", data, cursor)[0]
            cursor += 2
            if pointer == 0:
                break
            if pointer <= pointers[-1]:
                raise ValueError("PSP EVE pointers are not strictly increasing")
            pointers.append(pointer)
        else:
            raise ValueError("PSP EVE pointer table has no zero sentinel")

        final_start = MESSAGE_BODY_OFFSET + pointers[-1] * 2
        if final_start + 2 > len(data):
            raise ValueError("PSP EVE final message begins outside the bank")
        final_end = None
        for offset in range(final_start, len(data) - 1, 2):
            if struct.unpack_from(">H", data, offset)[0] == MESSAGE_TERMINATOR:
                final_end = offset + 2
                break
        if final_end is None:
            raise ValueError("PSP EVE final message has no 0x8000 terminator")

        final_end_word = (final_end - MESSAGE_BODY_OFFSET) // 2
        end_words = (*pointers[1:], final_end_word)
        messages = []
        for index, (start_word, end_word) in enumerate(zip(pointers, end_words)):
            start = MESSAGE_BODY_OFFSET + start_word * 2
            count = end_word - start_word
            words = struct.unpack_from(f">{count}H", data, start)
            messages.append(PspEveMessage(index, start_word, end_word, words))
        return cls(data, table_offset, tuple(pointers), tuple(messages))

    def rebuild(
        self,
        replacements: Mapping[int, tuple[int, ...]] | None = None,
    ) -> bytes:
        """Rebuild this fixed-size bank with replacement message word streams."""

        replacements = {} if replacements is None else dict(replacements)
        invalid = sorted(set(replacements) - set(range(len(self.messages))))
        if invalid:
            raise ValueError(f"PSP EVE replacement indices are invalid: {invalid}")

        payloads: list[tuple[int, ...]] = []
        for message in self.messages:
            words = replacements.get(message.index, message.words)
            if not isinstance(words, tuple):
                raise TypeError("PSP EVE replacements must be tuples of u16 words")
            if any(
                not isinstance(word, int)
                or isinstance(word, bool)
                or not 0 <= word <= 0xFFFF
                for word in words
            ):
                raise ValueError("PSP EVE replacement words must be u16 integers")
            if not words:
                raise ValueError("PSP EVE messages cannot be empty")
            payloads.append(words)

        if not payloads or not payloads[-1] or payloads[-1][-1] != MESSAGE_TERMINATOR:
            raise ValueError("PSP EVE final message must end with 0x8000")

        table_size = (len(payloads) + 1) * 2
        if self.table_offset + table_size > MESSAGE_BODY_OFFSET:
            raise ValueError("PSP EVE pointer table exceeds the message body")

        pointers = []
        cursor_words = 0
        for words in payloads:
            if cursor_words > 0xFFFF:
                raise ValueError("PSP EVE message pointer exceeds u16 capacity")
            pointers.append(cursor_words)
            cursor_words += len(words)

        body_capacity_words = (len(self.source_data) - MESSAGE_BODY_OFFSET) // 2
        if cursor_words > body_capacity_words:
            raise ValueError(
                "PSP EVE message body overflow: "
                f"{cursor_words} words exceed {body_capacity_words}"
            )

        original_end = MESSAGE_BODY_OFFSET + self.messages[-1].end_word * 2
        if any(self.source_data[original_end:]):
            raise ValueError("PSP EVE bank has a non-zero post-message tail")

        output = bytearray(self.source_data)
        struct.pack_into(
            f">{len(pointers) + 1}H",
            output,
            self.table_offset,
            *pointers,
            0,
        )
        body = b"".join(
            struct.pack(f">{len(words)}H", *words) if words else b""
            for words in payloads
        )
        output[MESSAGE_BODY_OFFSET:] = body + b"\x00" * (
            len(output) - MESSAGE_BODY_OFFSET - len(body)
        )

        rebuilt = bytes(output)
        parsed = type(self).parse(rebuilt, self.table_offset)
        if len(parsed.messages) != len(self.messages):
            raise ValueError("rebuilt PSP EVE message count changed")
        if tuple(message.words for message in parsed.messages) != tuple(payloads):
            raise ValueError("rebuilt PSP EVE message words changed during validation")
        return rebuilt


@dataclass(frozen=True)
class EveAuditResult:
    member_index: int
    name: str
    message_count: int


@dataclass(frozen=True)
class PspEveFiles:
    archive: PspPack

    @classmethod
    def parse(cls, data: bytes) -> "PspEveFiles":
        archive = PspPack.parse(data)
        if len(archive.members) != 30:
            raise ValueError(
                f"PSP eve_files.bin has {len(archive.members)} members; expected 30"
            )
        return cls(archive)

    def audit_known_banks(self) -> tuple[EveAuditResult, ...]:
        results = []
        for binding in KNOWN_BANKS:
            bank = PspEveBank.parse(
                self.archive.members[binding.member_index].data,
                binding.table_offset,
            )
            count = len(bank.messages)
            if count != binding.expected_messages:
                raise ValueError(
                    f"PSP EVE member {binding.member_index} ({binding.name}) has "
                    f"{count} messages; expected {binding.expected_messages}"
                )
            results.append(EveAuditResult(binding.member_index, binding.name, count))
        return tuple(results)

