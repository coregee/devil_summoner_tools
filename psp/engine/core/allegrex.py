"""Fail-closed assembler for the readable Allegrex subset used by PSP patches."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path


class AssemblyError(ValueError):
    """An Allegrex source cannot be represented by the supported subset."""


@dataclass(frozen=True, slots=True)
class Assembly:
    data: bytes
    base_address: int
    labels: dict[str, int]


@dataclass(frozen=True, slots=True)
class _Instruction:
    address: int
    line: int
    mnemonic: str
    operands: tuple[str, ...]


_IDENTIFIER = re.compile(r"[A-Za-z_.][A-Za-z0-9_.]*")
_NUMBER = re.compile(r"0[xX][0-9a-fA-F]+|[0-9]+")
_LABEL = re.compile(r"^([A-Za-z_.][A-Za-z0-9_.]*)\s*:\s*(.*)$")
_MEMORY = re.compile(r"^(.+)\(([^()]+)\)$")
_REGISTERS = {
    "zero": 0,
    "v0": 2,
    "v1": 3,
    "a0": 4,
    "a1": 5,
    "a2": 6,
    "a3": 7,
    "t0": 8,
    "t1": 9,
    "t2": 10,
    "t3": 11,
    "t4": 12,
    "t5": 13,
    "t6": 14,
    "t7": 15,
    "s0": 16,
    "s1": 17,
    "s2": 18,
    "s3": 19,
    "s4": 20,
    "s5": 21,
    "s6": 22,
    "s7": 23,
    "t8": 24,
    "t9": 25,
    "sp": 29,
    "ra": 31,
}
_CONTROL = {"b", "bal", "beq", "jr", "jal"}


def _split_operands(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    output: list[str] = []
    depth = start = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise AssemblyError("unbalanced ')' in operands")
        elif character == "," and depth == 0:
            output.append(value[start:index].strip())
            start = index + 1
    if depth:
        raise AssemblyError("unbalanced '(' in operands")
    output.append(value[start:].strip())
    if any(not item for item in output):
        raise AssemblyError("empty Allegrex operand")
    return tuple(output)


def _register(value: str, context: str) -> int:
    name = value.strip().lower().removeprefix("$")
    if name in _REGISTERS:
        return _REGISTERS[name]
    if re.fullmatch(r"r(?:[0-9]|[12][0-9]|3[01])", name):
        return int(name[1:])
    raise AssemblyError(f"{context}: invalid register {value!r}")


def _evaluate(text: str, symbols: dict[str, int], context: str) -> int:
    source = text.strip()
    position = 0

    def skip() -> None:
        nonlocal position
        while position < len(source) and source[position].isspace():
            position += 1

    def atom() -> int:
        nonlocal position
        skip()
        sign = 1
        if position < len(source) and source[position] in "+-":
            if source[position] == "-":
                sign = -1
            position += 1
            skip()
        if source.startswith("%hi(", position) or source.startswith("%lo(", position):
            high = source.startswith("%hi(", position)
            position += 4
            value = expression()
            skip()
            if position >= len(source) or source[position] != ")":
                raise AssemblyError(f"{context}: missing ')' in {text!r}")
            position += 1
            value = ((value & 0xFFFFFFFF) >> 16) if high else (value & 0xFFFF)
            return sign * value
        if position < len(source) and source[position] == "(":
            position += 1
            value = expression()
            skip()
            if position >= len(source) or source[position] != ")":
                raise AssemblyError(f"{context}: missing ')' in {text!r}")
            position += 1
            return sign * value
        number = _NUMBER.match(source, position)
        if number:
            position = number.end()
            return sign * int(number.group(0), 0)
        identifier = _IDENTIFIER.match(source, position)
        if identifier:
            position = identifier.end()
            name = identifier.group(0)
            if name not in symbols:
                raise AssemblyError(f"{context}: undefined symbol {name!r}")
            return sign * symbols[name]
        raise AssemblyError(f"{context}: malformed expression {text!r}")

    def expression() -> int:
        nonlocal position
        value = atom()
        while True:
            skip()
            if position >= len(source) or source[position] not in "+-":
                return value
            operator = source[position]
            position += 1
            right = atom()
            value = value + right if operator == "+" else value - right

    result = expression()
    skip()
    if position != len(source):
        raise AssemblyError(f"{context}: trailing expression data in {text!r}")
    return result


def _signed(value: int, bits: int, context: str) -> int:
    low = -(1 << (bits - 1))
    high = (1 << (bits - 1)) - 1
    if not low <= value <= high:
        raise AssemblyError(f"{context}: signed {bits}-bit value out of range")
    return value & ((1 << bits) - 1)


def _unsigned(value: int, bits: int, context: str) -> int:
    if not 0 <= value < (1 << bits):
        raise AssemblyError(f"{context}: unsigned {bits}-bit value out of range")
    return value


def _r_type(rs: int, rt: int, rd: int, shift: int, function: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | (shift << 6) | function


def _i_type(opcode: int, rs: int, rt: int, immediate: int) -> int:
    return (opcode << 26) | (rs << 21) | (rt << 16) | (immediate & 0xFFFF)


def _branch(target: int, address: int, context: str) -> int:
    delta = target - (address + 4)
    if delta % 4:
        raise AssemblyError(f"{context}: branch target is not word-aligned")
    return _signed(delta // 4, 16, context)


def _encode(item: _Instruction, symbols: dict[str, int]) -> int:
    op = item.operands
    context = f"line {item.line}"
    mnemonic = item.mnemonic
    if mnemonic == "nop" and not op:
        return 0
    if mnemonic == "move" and len(op) == 2:
        rd, rs = _register(op[0], context), _register(op[1], context)
        return _r_type(rs, 0, rd, 0, 0x21)
    if mnemonic == "addu" and len(op) == 3:
        rd, rs, rt = (_register(value, context) for value in op)
        return _r_type(rs, rt, rd, 0, 0x21)
    if mnemonic in {"addiu", "sltiu"} and len(op) == 3:
        rt, rs = _register(op[0], context), _register(op[1], context)
        immediate = _signed(_evaluate(op[2], symbols, context), 16, context)
        return _i_type(0x09 if mnemonic == "addiu" else 0x0B, rs, rt, immediate)
    if mnemonic in {"lui", "ori"}:
        if mnemonic == "lui" and len(op) == 2:
            rt, rs, expression = _register(op[0], context), 0, op[1]
        elif mnemonic == "ori" and len(op) == 3:
            rt, rs, expression = (
                _register(op[0], context),
                _register(op[1], context),
                op[2],
            )
        else:
            raise AssemblyError(f"{context}: invalid {mnemonic} operands")
        immediate = _unsigned(_evaluate(expression, symbols, context), 16, context)
        return _i_type(0x0F if mnemonic == "lui" else 0x0D, rs, rt, immediate)
    if mnemonic == "lbu" and len(op) == 2:
        match = _MEMORY.fullmatch(op[1].strip())
        if match is None:
            raise AssemblyError(f"{context}: invalid lbu address")
        rt = _register(op[0], context)
        base = _register(match.group(2), context)
        offset = _signed(_evaluate(match.group(1), symbols, context), 16, context)
        return _i_type(0x24, base, rt, offset)
    if mnemonic == "beq" and len(op) == 3:
        rs, rt = _register(op[0], context), _register(op[1], context)
        target = _evaluate(op[2], symbols, context)
        return _i_type(0x04, rs, rt, _branch(target, item.address, context))
    if mnemonic == "b" and len(op) == 1:
        target = _evaluate(op[0], symbols, context)
        return _i_type(0x04, 0, 0, _branch(target, item.address, context))
    if mnemonic == "bal" and len(op) == 1:
        target = _evaluate(op[0], symbols, context)
        return _i_type(0x01, 0, 0x11, _branch(target, item.address, context))
    if mnemonic == "jr" and len(op) == 1:
        return _r_type(_register(op[0], context), 0, 0, 0, 0x08)
    if mnemonic == "jal" and len(op) == 1:
        target = _evaluate(op[0], symbols, context)
        if target % 4 or (target >> 28) != ((item.address + 4) >> 28):
            raise AssemblyError(f"{context}: JAL target is outside its region")
        return (0x03 << 26) | ((target >> 2) & 0x03FFFFFF)
    raise AssemblyError(f"{context}: unsupported instruction {mnemonic!r}")


def assemble(
    source: str,
    base_address: int,
    *,
    symbols: dict[str, int] | None = None,
) -> Assembly:
    if base_address < 0 or base_address % 4:
        raise AssemblyError("Allegrex base address must be a nonnegative word address")
    resolved = dict(symbols or {})
    instructions: list[_Instruction] = []
    cursor = base_address
    labels: dict[str, int] = {}

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        match = _LABEL.fullmatch(line)
        if match:
            name, line = match.group(1), match.group(2).strip()
            if name in resolved or name in labels:
                raise AssemblyError(f"line {line_number}: duplicate symbol {name!r}")
            labels[name] = cursor
            if not line:
                continue
        fields = line.split(None, 1)
        mnemonic = fields[0].lower()
        operands = _split_operands(fields[1] if len(fields) == 2 else "")
        instructions.append(_Instruction(cursor, line_number, mnemonic, operands))
        cursor += 4

    resolved.update(labels)
    for index, instruction in enumerate(instructions):
        if instruction.mnemonic not in _CONTROL:
            continue
        if index + 1 == len(instructions):
            raise AssemblyError(
                f"line {instruction.line}: control transfer has no delay slot"
            )
        if instructions[index + 1].mnemonic in _CONTROL:
            raise AssemblyError(
                f"line {instruction.line}: control transfer in a delay slot"
            )
    words = tuple(_encode(item, resolved) for item in instructions)
    return Assembly(
        struct.pack(f"<{len(words)}I", *words),
        base_address,
        labels,
    )


def assemble_file(
    path: Path,
    base_address: int,
    *,
    symbols: dict[str, int] | None = None,
) -> Assembly:
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise AssemblyError(f"missing Allegrex source: {path}") from error
    return assemble(source, base_address, symbols=symbols)


def encode_instruction(
    instruction: str,
    address: int,
    *,
    symbols: dict[str, int] | None = None,
) -> bytes:
    line = instruction.strip()
    if not line or "\n" in line or "\r" in line or ":" in line:
        raise AssemblyError("an inline instruction must be one unlabeled word")
    fields = line.split(None, 1)
    item = _Instruction(
        address,
        1,
        fields[0].lower(),
        _split_operands(fields[1] if len(fields) == 2 else ""),
    )
    return struct.pack("<I", _encode(item, dict(symbols or {})))
