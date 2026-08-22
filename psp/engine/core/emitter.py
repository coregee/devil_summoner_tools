"""Dependency-free Allegrex assembler primitives and patch-write contracts."""

from __future__ import annotations

import struct
from dataclasses import dataclass

ELF_LOAD_FILE_OFFSET = 0x80

# MIPS register numbers used by the runtime patch builders.
ZERO = 0
V0 = 2
V1 = 3
A0 = 4
A1 = 5
A2 = 6
A3 = 7
T0 = 8
T1 = 9
T2 = 10
T3 = 11
T4 = 12
T5 = 13
T6 = 14
T7 = 15
S0 = 16
S1 = 17
S2 = 18
S3 = 19
S4 = 20
S5 = 21
S6 = 22
S7 = 23
T8 = 24
T9 = 25
SP = 29
RA = 31


@dataclass(frozen=True)
class AssembledCode:
    """One deterministic code blob and its resolved label addresses."""

    address: int
    data: bytes
    labels: tuple[tuple[str, int], ...]

    @property
    def end_address(self) -> int:
        return self.address + len(self.data)

    @property
    def words(self) -> tuple[int, ...]:
        if len(self.data) % 4:
            raise ValueError("Allegrex code size is not word-aligned")
        return struct.unpack(f"<{len(self.data) // 4}I", self.data)

    def label_address(self, name: str) -> int:
        try:
            return dict(self.labels)[name]
        except KeyError as error:
            raise KeyError(f"unknown Allegrex label: {name}") from error


@dataclass(frozen=True)
class PatchWrite:
    """A checked write at one module-relative virtual address."""

    name: str
    address: int
    data: bytes

    @property
    def end_address(self) -> int:
        return self.address + len(self.data)

    @property
    def file_offset(self) -> int:
        return self.address + ELF_LOAD_FILE_OFFSET


@dataclass(frozen=True)
class _LabelFixup:
    index: int
    label: str


def _register(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 32:
        raise ValueError(f"invalid MIPS register: {value!r}")
    return value


def _signed_immediate(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("MIPS immediate must be an integer")
    if not -0x8000 <= value <= 0x7FFF:
        raise ValueError(f"MIPS signed immediate is out of range: {value:#x}")
    return value & 0xFFFF


def _unsigned_immediate(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("MIPS immediate must be an integer")
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"MIPS unsigned immediate is out of range: {value:#x}")
    return value


def _r_type(rs: int, rt: int, rd: int, shift: int, function: int) -> int:
    if not 0 <= shift < 32:
        raise ValueError(f"invalid MIPS shift: {shift}")
    return (
        (_register(rs) << 21)
        | (_register(rt) << 16)
        | (_register(rd) << 11)
        | (shift << 6)
        | function
    )


def _i_type(opcode: int, rs: int, rt: int, immediate: int) -> int:
    return (
        (opcode << 26)
        | (_register(rs) << 21)
        | (_register(rt) << 16)
        | (immediate & 0xFFFF)
    )


class _Assembler:
    """Tiny exact MIPS32 assembler with labels and enforced delay slots."""

    def __init__(self, address: int) -> None:
        if address % 4:
            raise ValueError("Allegrex code address must be word-aligned")
        self.address = address
        self._words: list[int] = []
        self._labels: dict[str, int] = {}
        self._fixups: list[_LabelFixup] = []
        self._delay_slot_pending = False

    @property
    def cursor(self) -> int:
        return self.address + len(self._words) * 4

    def label(self, name: str) -> None:
        if self._delay_slot_pending:
            raise ValueError("a control transfer still needs an explicit delay slot")
        if name in self._labels:
            raise ValueError(f"duplicate Allegrex label: {name}")
        self._labels[name] = self.cursor

    def _emit(self, word: int) -> None:
        if self._delay_slot_pending:
            raise ValueError("use delay_nop() after an Allegrex control transfer")
        self._words.append(word & 0xFFFFFFFF)

    def _control(self, word: int, label: str | None = None) -> None:
        if self._delay_slot_pending:
            raise ValueError("nested Allegrex control transfers have no delay slot")
        index = len(self._words)
        self._words.append(word & 0xFFFFFFFF)
        if label is not None:
            self._fixups.append(_LabelFixup(index, label))
        self._delay_slot_pending = True

    def delay_nop(self) -> None:
        if not self._delay_slot_pending:
            raise ValueError("Allegrex NOP is not filling a pending delay slot")
        self._words.append(0)
        self._delay_slot_pending = False

    def addu(self, rd: int, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, rd, 0, 0x21))

    def subu(self, rd: int, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, rd, 0, 0x23))

    def sltu(self, rd: int, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, rd, 0, 0x2B))

    def or_(self, rd: int, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, rd, 0, 0x25))

    def sll(self, rd: int, rt: int, shift: int) -> None:
        self._emit(_r_type(ZERO, rt, rd, shift, 0x00))

    def srl(self, rd: int, rt: int, shift: int) -> None:
        self._emit(_r_type(ZERO, rt, rd, shift, 0x02))

    def mult(self, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, ZERO, 0, 0x18))

    def divu(self, rs: int, rt: int) -> None:
        self._emit(_r_type(rs, rt, ZERO, 0, 0x1B))

    def mfhi(self, rd: int) -> None:
        self._emit(_r_type(ZERO, ZERO, rd, 0, 0x10))

    def mflo(self, rd: int) -> None:
        self._emit(_r_type(ZERO, ZERO, rd, 0, 0x12))

    def addiu(self, rt: int, rs: int, immediate: int) -> None:
        self._emit(_i_type(0x09, rs, rt, _signed_immediate(immediate)))

    def sltiu(self, rt: int, rs: int, immediate: int) -> None:
        self._emit(_i_type(0x0B, rs, rt, _signed_immediate(immediate)))

    def ori(self, rt: int, rs: int, immediate: int) -> None:
        self._emit(_i_type(0x0D, rs, rt, _unsigned_immediate(immediate)))

    def andi(self, rt: int, rs: int, immediate: int) -> None:
        self._emit(_i_type(0x0C, rs, rt, _unsigned_immediate(immediate)))

    def xori(self, rt: int, rs: int, immediate: int) -> None:
        self._emit(_i_type(0x0E, rs, rt, _unsigned_immediate(immediate)))

    def lui(self, rt: int, immediate: int) -> None:
        self._emit(_i_type(0x0F, ZERO, rt, _unsigned_immediate(immediate)))

    def lb(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x20, base, rt, _signed_immediate(offset)))

    def lbu(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x24, base, rt, _signed_immediate(offset)))

    def lhu(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x25, base, rt, _signed_immediate(offset)))

    def lw(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x23, base, rt, _signed_immediate(offset)))

    def sw(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x2B, base, rt, _signed_immediate(offset)))

    def sb(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x28, base, rt, _signed_immediate(offset)))

    def sh(self, rt: int, offset: int, base: int) -> None:
        self._emit(_i_type(0x29, base, rt, _signed_immediate(offset)))

    def beq(self, rs: int, rt: int, label: str) -> None:
        self._control(_i_type(0x04, rs, rt, 0), label)

    def bne(self, rs: int, rt: int, label: str) -> None:
        self._control(_i_type(0x05, rs, rt, 0), label)

    def bltz(self, rs: int, label: str) -> None:
        self._control(_i_type(0x01, rs, ZERO, 0), label)

    def bal(self, label: str) -> None:
        # `bal label` is the MIPS alias for `bgezal $zero, label`.
        self._control(_i_type(0x01, ZERO, 0x11, 0), label)

    def bal_address(self, target: int) -> None:
        """Branch-and-link to one fixed nearby address without relocation."""

        if not isinstance(target, int) or isinstance(target, bool) or target % 4:
            raise ValueError("Allegrex BAL target must be a word-aligned integer")
        displacement = target - (self.cursor + 4)
        if displacement % 4:
            raise ValueError("Allegrex BAL target has an unaligned displacement")
        branch_words = displacement // 4
        if not -0x8000 <= branch_words <= 0x7FFF:
            raise ValueError("Allegrex BAL target is out of range")
        self._control(_i_type(0x01, ZERO, 0x11, branch_words))

    def jr(self, register: int) -> None:
        self._control(_r_type(register, ZERO, ZERO, 0, 0x08))

    def jalr(self, register: int) -> None:
        self._control(_r_type(register, ZERO, RA, 0, 0x09))

    def finish(self) -> AssembledCode:
        if self._delay_slot_pending:
            raise ValueError("Allegrex code ends before a required delay slot")
        words = list(self._words)
        for fixup in self._fixups:
            try:
                target = self._labels[fixup.label]
            except KeyError as error:
                raise ValueError(f"undefined Allegrex label: {fixup.label}") from error
            instruction = self.address + fixup.index * 4
            displacement = target - (instruction + 4)
            if displacement % 4:
                raise ValueError(f"unaligned Allegrex branch target: {fixup.label}")
            branch_words = displacement // 4
            if not -0x8000 <= branch_words <= 0x7FFF:
                raise ValueError(
                    f"Allegrex branch target is out of range: {fixup.label}"
                )
            words[fixup.index] |= branch_words & 0xFFFF
        data = struct.pack(f"<{len(words)}I", *words)
        return AssembledCode(
            address=self.address,
            data=data,
            labels=tuple(self._labels.items()),
        )


def _jal_word(site: int, target: int) -> int:
    if site % 4 or target % 4:
        raise ValueError("Allegrex JAL site and target must be word-aligned")
    if ((site + 4) ^ target) & 0xF0000000:
        raise ValueError("Allegrex JAL target is outside the caller region")
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def _j_word(site: int, target: int) -> int:
    if site % 4 or target % 4:
        raise ValueError("Allegrex J site and target must be word-aligned")
    if ((site + 4) ^ target) & 0xF0000000:
        raise ValueError("Allegrex J target is outside the caller region")
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def _branch_word(site: int, target: int) -> int:
    """Encode one relocation-free unconditional PC-relative branch."""

    if site % 4 or target % 4:
        raise ValueError("Allegrex branch site and target must be word-aligned")
    displacement = target - (site + 4)
    if displacement % 4:
        raise ValueError("Allegrex branch target has an unaligned displacement")
    branch_words = displacement // 4
    if not -0x8000 <= branch_words <= 0x7FFF:
        raise ValueError("Allegrex branch target is out of range")
    return _i_type(0x04, ZERO, ZERO, branch_words)


def _word_bytes(*words: int) -> bytes:
    return struct.pack(f"<{len(words)}I", *words)


def _load_pc_relative_target(
    code: _Assembler,
    destination: int,
    pc_register: int,
    *,
    pc_address: int,
    target_address: int,
) -> None:
    """Load a module-relative target without requiring a new ELF relocation."""

    delta = (target_address - pc_address) & 0xFFFFFFFF
    code.lui(destination, delta >> 16)
    code.ori(destination, destination, delta & 0xFFFF)
    code.addu(destination, destination, pc_register)


