"""Small fail-closed SH-2 assembler for readable Saturn engine patches.

The patch sources in ``engine/asm`` are authoritative.  This module supports
only the instruction forms and data directives used by those sources; unknown
syntax is an error rather than a request to preserve preassembled bytes.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path


class AssemblyError(ValueError):
    """A source file cannot be represented by the supported SH-2 subset."""


@dataclass(frozen=True, slots=True)
class Assembly:
    data: bytes
    base_address: int
    labels: dict[str, int]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Item:
    kind: str
    offset: int
    size: int
    line: int | None
    value: object


_NUMBER = re.compile(r"0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+")
_IDENTIFIER = re.compile(r"[A-Za-z_.][A-Za-z0-9_.]*")
_LABEL = re.compile(r"^([A-Za-z_.][A-Za-z0-9_.]*)\s*:\s*(.*)$")
_REGISTER = re.compile(r"[rR]([0-9]|1[0-5])")


def _evaluate(text: str, symbols: dict[str, int], context: str) -> int:
    tokens: list[int | str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character.isdigit():
            match = _NUMBER.match(text, index)
            assert match is not None
            token = match.group(0)
            base = 16 if token[:2].lower() == "0x" else 2 if token[:2].lower() == "0b" else 10
            tokens.append(int(token, base))
            index = match.end()
            continue
        match = _IDENTIFIER.match(text, index)
        if match:
            name = match.group(0)
            if name not in symbols:
                raise AssemblyError(f"{context}: undefined symbol {name!r}")
            tokens.append(symbols[name])
            index = match.end()
            continue
        if character in "+-*()":
            tokens.append(character)
            index += 1
            continue
        raise AssemblyError(f"{context}: invalid character {character!r} in {text!r}")

    position = 0

    def peek() -> int | str | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> int | str:
        nonlocal position
        value = tokens[position]
        position += 1
        return value

    def atom() -> int:
        token = peek()
        if token == "(":
            take()
            value = add_subtract()
            if peek() != ")":
                raise AssemblyError(f"{context}: missing ')' in {text!r}")
            take()
            return value
        if token == "-":
            take()
            return -atom()
        if token == "+":
            take()
            return atom()
        if isinstance(token, int):
            return int(take())
        raise AssemblyError(f"{context}: malformed expression {text!r}")

    def multiply() -> int:
        value = atom()
        while peek() == "*":
            take()
            value *= atom()
        return value

    def add_subtract() -> int:
        value = multiply()
        while peek() in ("+", "-"):
            operator = take()
            value = value + multiply() if operator == "+" else value - multiply()
        return value

    if not tokens:
        raise AssemblyError(f"{context}: empty expression")
    result = add_subtract()
    if position != len(tokens):
        raise AssemblyError(f"{context}: trailing expression data in {text!r}")
    return result


def _strip_comment(line: str) -> str:
    quoted = escaped = False
    for index, character in enumerate(line):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character == ";":
            return line[:index]
    return line


def _register(value: str) -> int | None:
    value = value.strip()
    match = _REGISTER.fullmatch(value)
    if match:
        return int(match.group(1))
    return 15 if value.lower() == "sp" else None


def _split_commas(value: str) -> list[str]:
    parts: list[str] = []
    depth = start = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return parts


def _operand(value: str, context: str) -> tuple[object, ...]:
    text = value.strip()
    if not text:
        raise AssemblyError(f"{context}: empty operand")
    if text.startswith("#"):
        return ("immediate", text[1:].strip())
    if text.startswith("="):
        return ("pool", text[1:].strip())
    lowered = text.lower()
    if lowered in ("pr", "macl", "mach"):
        return (lowered,)
    register = _register(text)
    if register is not None:
        return ("register", register)
    if not text.startswith("@"):
        return ("expression", text)

    indirect = text[1:].strip()
    if indirect.startswith("-"):
        register = _register(indirect[1:])
        if register is None:
            raise AssemblyError(f"{context}: invalid pre-decrement operand {text!r}")
        return ("pre_decrement", register)
    if indirect.endswith("+"):
        register = _register(indirect[:-1])
        if register is None:
            raise AssemblyError(f"{context}: invalid post-increment operand {text!r}")
        return ("post_increment", register)
    if indirect.startswith("("):
        if not indirect.endswith(")"):
            raise AssemblyError(f"{context}: unbalanced operand {text!r}")
        parts = _split_commas(indirect[1:-1])
        if len(parts) != 2:
            raise AssemblyError(f"{context}: invalid indexed operand {text!r}")
        first, second = parts
        if second.lower() == "pc":
            return ("pc_displacement", first)
        base = _register(second)
        if base is None:
            raise AssemblyError(f"{context}: invalid base register in {text!r}")
        index = _register(first)
        if index == 0:
            return ("r0_index", base)
        if index is not None:
            raise AssemblyError(f"{context}: SH-2 indexed operands require r0")
        return ("displacement", first, base)
    register = _register(indirect)
    if register is None:
        raise AssemblyError(f"{context}: invalid memory operand {text!r}")
    return ("indirect", register)


_ZERO = {
    "rts": 0x000B,
    "nop": 0x0009,
    "rte": 0x002B,
    "clrt": 0x0008,
    "sett": 0x0018,
    "clrmac": 0x0028,
    "div0u": 0x0019,
    "sleep": 0x001B,
}
_ONE_REGISTER = {
    "dt": 0x10,
    "cmp/pz": 0x11,
    "cmp/pl": 0x15,
    "shll": 0x00,
    "shlr": 0x01,
    "shll2": 0x08,
    "shlr2": 0x09,
    "shll8": 0x18,
    "shlr8": 0x19,
    "shll16": 0x28,
    "shlr16": 0x29,
    "shal": 0x20,
    "shar": 0x21,
    "rotl": 0x04,
    "rotr": 0x05,
    "rotcl": 0x24,
    "rotcr": 0x25,
}
_TWO_REGISTER = {
    "add": (0x3, 0xC),
    "addc": (0x3, 0xE),
    "sub": (0x3, 0x8),
    "subc": (0x3, 0xA),
    "neg": (0x6, 0xB),
    "negc": (0x6, 0xA),
    "not": (0x6, 0x7),
    "and": (0x2, 0x9),
    "or": (0x2, 0xB),
    "xor": (0x2, 0xA),
    "tst": (0x2, 0x8),
    "cmp/eq": (0x3, 0x0),
    "cmp/hs": (0x3, 0x2),
    "cmp/ge": (0x3, 0x3),
    "cmp/hi": (0x3, 0x6),
    "cmp/gt": (0x3, 0x7),
    "extu.b": (0x6, 0xC),
    "extu.w": (0x6, 0xD),
    "exts.b": (0x6, 0xE),
    "exts.w": (0x6, 0xF),
    "swap.b": (0x6, 0x8),
    "swap.w": (0x6, 0x9),
    "mulu.w": (0x2, 0xE),
    "muls.w": (0x2, 0xF),
    "dmulu.l": (0x3, 0x5),
    "dmuls.l": (0x3, 0xD),
    "mul.l": (0x0, 0x7),
}
_IMMEDIATE_R0 = {"and": 0xC9, "or": 0xCB, "xor": 0xCA, "tst": 0xC8, "cmp/eq": 0x88}
_BRANCH_8 = {"bt": 0x8900, "bf": 0x8B00, "bt.s": 0x8D00, "bf.s": 0x8F00}
_STS = {"mach": 0x0A, "macl": 0x1A, "pr": 0x2A}
_STS_LONG = {"mach": 0x02, "macl": 0x12, "pr": 0x22}
_LDS = {"mach": 0x0A, "macl": 0x1A, "pr": 0x2A}
_LDS_LONG = {"mach": 0x06, "macl": 0x16, "pr": 0x26}
_DELAY_BRANCHES = {"bra", "bsr", "jsr", "jmp", "rts", "braf", "bsrf", "rte", "bt.s", "bf.s"}
_ALL_BRANCHES = _DELAY_BRANCHES | {"bt", "bf"}


def _immediate8(expression: str, symbols: dict[str, int], context: str) -> int:
    value = _evaluate(expression, symbols, context)
    if not -128 <= value <= 255:
        raise AssemblyError(f"{context}: immediate {value} is outside -128..255")
    return value & 0xFF


def _displacement(value: int, scale: int, maximum: int, context: str) -> int:
    if value % scale or not 0 <= value // scale <= maximum:
        raise AssemblyError(f"{context}: invalid displacement {value}")
    return value // scale


def _encode(
    mnemonic: str,
    operands: list[tuple[object, ...]],
    address: int,
    symbols: dict[str, int],
    pool_sequence: int,
    pool_offsets: dict[tuple[int, str, str], int],
    base_address: int,
    context: str,
) -> int:
    kinds = tuple(operand[0] for operand in operands)

    def invalid() -> None:
        raise AssemblyError(f"{context}: invalid operands for {mnemonic!r}")

    if mnemonic in _ZERO:
        if operands:
            invalid()
        return _ZERO[mnemonic]

    if mnemonic in ("mov", "mov.b", "mov.w", "mov.l"):
        if len(operands) != 2:
            invalid()
        source, destination = operands
        size = None if mnemonic == "mov" else {"b": 0, "w": 1, "l": 2}[mnemonic[-1]]
        if source[0] == "immediate" and destination[0] == "register":
            if size is not None:
                invalid()
            return 0xE000 | int(destination[1]) << 8 | _immediate8(str(source[1]), symbols, context)
        if source[0] == "register" and destination[0] == "register":
            if size is not None:
                invalid()
            return 0x6003 | int(destination[1]) << 8 | int(source[1]) << 4
        if size is None:
            invalid()
        assert size is not None
        if source[0] == "pool" and destination[0] == "register":
            if size == 0:
                invalid()
            expression = re.sub(r"\s+", "", str(source[1]))
            key = (pool_sequence, "l" if size == 2 else "w", expression)
            if key not in pool_offsets:
                raise AssemblyError(f"{context}: unresolved literal {expression!r}")
            literal = base_address + pool_offsets[key]
            pc = (address + 4) & ~3 if size == 2 else address + 4
            scale = 4 if size == 2 else 2
            displacement = literal - pc
            if displacement < 0 or displacement % scale or displacement // scale > 255:
                raise AssemblyError(f"{context}: literal pool is out of range")
            opcode = 0xD000 if size == 2 else 0x9000
            return opcode | int(destination[1]) << 8 | displacement // scale
        if source[0] in ("expression", "pc_displacement") and destination[0] == "register":
            if size == 0:
                invalid()
            if source[0] == "expression":
                target = _evaluate(str(source[1]), symbols, context)
                pc = (address + 4) & ~3 if size == 2 else address + 4
                displacement = target - pc
                scale = 4 if size == 2 else 2
                if displacement < 0:
                    raise AssemblyError(f"{context}: PC-relative source precedes instruction")
                encoded = _displacement(displacement, scale, 255, context)
            else:
                encoded = _displacement(
                    _evaluate(str(source[1]), symbols, context),
                    4 if size == 2 else 2,
                    255,
                    context,
                )
            opcode = 0xD000 if size == 2 else 0x9000
            return opcode | int(destination[1]) << 8 | encoded
        if source[0] == "indirect" and destination[0] == "register":
            return 0x6000 | int(destination[1]) << 8 | int(source[1]) << 4 | size
        if source[0] == "register" and destination[0] == "indirect":
            return 0x2000 | int(destination[1]) << 8 | int(source[1]) << 4 | size
        if source[0] == "post_increment" and destination[0] == "register":
            return 0x6004 | int(destination[1]) << 8 | int(source[1]) << 4 | size
        if source[0] == "register" and destination[0] == "pre_decrement":
            return 0x2004 | int(destination[1]) << 8 | int(source[1]) << 4 | size
        if source[0] == "r0_index" and destination[0] == "register":
            return 0x000C | size | int(destination[1]) << 8 | int(source[1]) << 4
        if source[0] == "register" and destination[0] == "r0_index":
            return 0x0004 | size | int(destination[1]) << 8 | int(source[1]) << 4
        if source[0] == "displacement" and destination[0] == "register":
            displacement = _evaluate(str(source[1]), symbols, context)
            if size == 2:
                return 0x5000 | int(destination[1]) << 8 | int(source[2]) << 4 | _displacement(displacement, 4, 15, context)
            if destination[1] != 0:
                invalid()
            return 0x8400 | size << 8 | int(source[2]) << 4 | _displacement(displacement, size + 1, 15, context)
        if source[0] == "register" and destination[0] == "displacement":
            displacement = _evaluate(str(destination[1]), symbols, context)
            if size == 2:
                return 0x1000 | int(destination[2]) << 8 | int(source[1]) << 4 | _displacement(displacement, 4, 15, context)
            if source[1] != 0:
                invalid()
            return 0x8000 | size << 8 | int(destination[2]) << 4 | _displacement(displacement, size + 1, 15, context)
        invalid()

    if mnemonic == "add" and kinds and kinds[0] == "immediate":
        if len(operands) != 2 or operands[1][0] != "register":
            invalid()
        return 0x7000 | int(operands[1][1]) << 8 | _immediate8(str(operands[0][1]), symbols, context)
    if mnemonic in _IMMEDIATE_R0 and kinds and kinds[0] == "immediate":
        if len(operands) != 2 or operands[1] != ("register", 0):
            invalid()
        return _IMMEDIATE_R0[mnemonic] << 8 | _immediate8(str(operands[0][1]), symbols, context)
    if mnemonic in _TWO_REGISTER:
        if kinds != ("register", "register"):
            invalid()
        top, low = _TWO_REGISTER[mnemonic]
        return top << 12 | int(operands[1][1]) << 8 | int(operands[0][1]) << 4 | low
    if mnemonic in _ONE_REGISTER:
        if kinds != ("register",):
            invalid()
        return 0x4000 | int(operands[0][1]) << 8 | _ONE_REGISTER[mnemonic]
    if mnemonic in ("jsr", "jmp"):
        if kinds != ("indirect",):
            invalid()
        return 0x4000 | int(operands[0][1]) << 8 | (0x0B if mnemonic == "jsr" else 0x2B)
    if mnemonic in ("bra", "bsr") or mnemonic in _BRANCH_8:
        if kinds != ("expression",):
            invalid()
        target = _evaluate(str(operands[0][1]), symbols, context)
        delta = target - (address + 4)
        if delta % 2:
            raise AssemblyError(f"{context}: branch target is odd")
        displacement = delta // 2
        if mnemonic in ("bra", "bsr"):
            if not -2048 <= displacement <= 2047:
                raise AssemblyError(f"{context}: branch is out of range")
            return (0xA000 if mnemonic == "bra" else 0xB000) | displacement & 0xFFF
        if not -128 <= displacement <= 127:
            raise AssemblyError(f"{context}: conditional branch is out of range")
        return _BRANCH_8[mnemonic] | displacement & 0xFF
    if mnemonic == "sts" and len(operands) == 2 and kinds[0] in _STS and operands[1][0] == "register":
        return int(operands[1][1]) << 8 | _STS[str(kinds[0])]
    if mnemonic == "sts.l" and len(operands) == 2 and kinds[0] in _STS_LONG and operands[1][0] == "pre_decrement":
        return 0x4000 | int(operands[1][1]) << 8 | _STS_LONG[str(kinds[0])]
    if mnemonic == "lds" and len(operands) == 2 and operands[0][0] == "register" and kinds[1] in _LDS:
        return 0x4000 | int(operands[0][1]) << 8 | _LDS[str(kinds[1])]
    if mnemonic == "lds.l" and len(operands) == 2 and operands[0][0] == "post_increment" and kinds[1] in _LDS_LONG:
        return 0x4000 | int(operands[0][1]) << 8 | _LDS_LONG[str(kinds[1])]
    raise AssemblyError(f"{context}: unknown or unsupported instruction {mnemonic!r}")


def assemble(source: str, base_address: int, symbols: dict[str, int] | None = None) -> Assembly:
    """Assemble a source string to big-endian SH-2 code and data."""
    external = dict(symbols or {})
    items: list[_Item] = []
    labels: dict[str, int] = {}
    pending: list[tuple[str, str]] = []
    pending_seen: set[tuple[str, str]] = set()
    pending_lines: dict[tuple[str, str], int] = {}
    pool_offsets: dict[tuple[int, str, str], int] = {}
    pool_sequence = 0
    offset = 0

    def flush_pool(line: int | None) -> None:
        nonlocal offset, pool_sequence, pending, pending_seen
        if any(size == "l" for size, _expression in pending):
            padding = (-(base_address + offset)) % 4
        elif pending and offset % 2:
            padding = 1
        else:
            padding = 0
        if padding:
            items.append(_Item("padding", offset, padding, line, None))
            offset += padding
        ordered = [row for row in pending if row[0] == "l"] + [row for row in pending if row[0] == "w"]
        for size_name, expression in ordered:
            size = 4 if size_name == "l" else 2
            pool_offsets[(pool_sequence, size_name, expression)] = offset
            items.append(_Item("literal", offset, size, pending_lines[(size_name, expression)], (size_name, expression)))
            offset += size
        pool_sequence += 1
        pending = []
        pending_seen = set()

    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = _strip_comment(raw_line).strip()
        context = f"line {line_number}"
        while True:
            match = _LABEL.match(line)
            if not match:
                break
            name = match.group(1)
            if name in labels or name in external:
                raise AssemblyError(f"{context}: duplicate or colliding label {name!r}")
            labels[name] = offset
            line = match.group(2).strip()
        if not line:
            continue
        if line.startswith("."):
            parts = line.split(None, 1)
            directive = parts[0].lower()
            argument = parts[1].strip() if len(parts) > 1 else ""
            if directive == ".pool":
                flush_pool(line_number)
            elif directive == ".align":
                try:
                    alignment = int(argument, 0)
                except ValueError as error:
                    raise AssemblyError(f"{context}: .align requires a number") from error
                if alignment not in (2, 4, 8, 16):
                    raise AssemblyError(f"{context}: unsupported alignment {alignment}")
                padding = (-offset) % alignment
                if padding:
                    items.append(_Item("padding", offset, padding, line_number, None))
                    offset += padding
            elif directive in (".byte", ".word", ".long"):
                expressions = _split_commas(argument) if argument else []
                if not expressions:
                    raise AssemblyError(f"{context}: {directive} requires data")
                unit = {".byte": 1, ".word": 2, ".long": 4}[directive]
                if offset % unit:
                    raise AssemblyError(f"{context}: misaligned {directive}")
                items.append(_Item(directive[1:], offset, unit * len(expressions), line_number, expressions))
                offset += unit * len(expressions)
            else:
                raise AssemblyError(f"{context}: unsupported directive {directive!r}")
            continue

        parts = line.split(None, 1)
        mnemonic = {"bt/s": "bt.s", "bf/s": "bf.s"}.get(parts[0].lower(), parts[0].lower())
        operand_text = parts[1].strip() if len(parts) > 1 else ""
        operands = [_operand(value, context) for value in _split_commas(operand_text)] if operand_text else []
        if offset % 2:
            raise AssemblyError(f"{context}: instruction is not aligned")
        if mnemonic in ("mov.l", "mov.w"):
            for operand in operands:
                if operand[0] == "pool":
                    key = (mnemonic[-1], re.sub(r"\s+", "", str(operand[1])))
                    if key not in pending_seen:
                        pending_seen.add(key)
                        pending.append(key)
                        pending_lines[key] = line_number
        items.append(_Item("code", offset, 2, line_number, (mnemonic, operands, pool_sequence)))
        offset += 2
    flush_pool(None)

    environment = dict(external)
    environment.update({name: base_address + value for name, value in labels.items()})
    output = bytearray()
    for item in items:
        assert len(output) == item.offset
        context = f"line {item.line}" if item.line is not None else "literal pool"
        if item.kind == "padding":
            output.extend(bytes(item.size))
        elif item.kind in ("byte", "word", "long"):
            bits = {"byte": 8, "word": 16, "long": 32}[item.kind]
            format_name = {"word": ">H", "long": ">I"}.get(item.kind)
            for expression in item.value:  # type: ignore[union-attr]
                value = _evaluate(str(expression), environment, context)
                lower = -(1 << (bits - 1))
                upper = (1 << bits) - 1
                if not lower <= value <= upper:
                    raise AssemblyError(f"{context}: data value is out of range")
                if format_name:
                    output.extend(struct.pack(format_name, value & upper))
                else:
                    output.append(value & upper)
        elif item.kind == "literal":
            size_name, expression = item.value  # type: ignore[misc]
            value = _evaluate(str(expression), environment, context)
            if size_name == "l":
                if not -(1 << 31) <= value <= 0xFFFFFFFF:
                    raise AssemblyError(f"{context}: long literal is out of range")
                output.extend(struct.pack(">I", value & 0xFFFFFFFF))
            else:
                if not -32768 <= value <= 0xFFFF:
                    raise AssemblyError(f"{context}: word literal is out of range")
                output.extend(struct.pack(">H", value & 0xFFFF))
        else:
            mnemonic, operands, sequence = item.value  # type: ignore[misc]
            word = _encode(
                mnemonic,
                operands,
                base_address + item.offset,
                environment,
                sequence,
                pool_offsets,
                base_address,
                context,
            )
            output.extend(struct.pack(">H", word))

    warnings: list[str] = []
    for index, item in enumerate(items):
        if item.kind != "code" or item.value[0] not in _DELAY_BRANCHES:  # type: ignore[index]
            continue
        next_item = items[index + 1] if index + 1 < len(items) else None
        if next_item is None or next_item.kind != "code":
            warnings.append(f"line {item.line}: delay slot does not contain an instruction")
        elif next_item.value[0] in _ALL_BRANCHES:  # type: ignore[index]
            warnings.append(f"line {next_item.line}: branch occupies another branch's delay slot")
    return Assembly(bytes(output), base_address, {name: base_address + value for name, value in labels.items()}, tuple(warnings))


def assemble_file(path: Path, base_address: int, symbols: dict[str, int] | None = None) -> Assembly:
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise AssemblyError(f"missing assembly source: {path}") from error
    return assemble(source, base_address, symbols)
