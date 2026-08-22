"""Typed, readable patch-site contracts for PSP engine surfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config_io import TargetContract, object_value, read_json


ENGINE_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_HEX = re.compile(r"0x[0-9a-f]+\Z")
_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class ReplacementRecipe:
    kind: str
    sources: tuple[Path, ...] = ()
    link: str | None = None
    instruction: str | None = None
    generator: str | None = None


@dataclass(frozen=True, slots=True)
class PatchRecipe:
    group: str
    name: str
    address: int
    expected: bytes
    replacement: ReplacementRecipe


@dataclass(frozen=True, slots=True)
class GuardRecipe:
    name: str
    file_offset: int
    expected: bytes


@dataclass(frozen=True, slots=True)
class PatchRecipeConfiguration:
    surface: str
    targets: dict[str, TargetContract]
    guards: dict[str, tuple[GuardRecipe, ...]]
    patches: dict[str, tuple[PatchRecipe, ...]]


def _address(value: object, context: str) -> int:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase 0x hexadecimal")
    return int(value, 16)


def _hash(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def _assembly_sources(value: object, context: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context} must be a nonempty source list")
    root = ASSEMBLY_ROOT.resolve()
    output: list[Path] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item or "\\" in item:
            raise ValueError(f"{context}[{index}] must be a POSIX relative path")
        relative = Path(item)
        path = (ASSEMBLY_ROOT / relative).resolve()
        if relative.is_absolute() or relative.suffix != ".s":
            raise ValueError(f"{context}[{index}] must name an .s file")
        if path.parent != root and root not in path.parents:
            raise ValueError(f"{context}[{index}] escapes the assembly root")
        if path in output or not path.is_file():
            raise ValueError(f"{context}[{index}] is missing or repeated")
        output.append(path)
    return tuple(output)


def load_patch_recipe_configuration(
    path: Path,
    *,
    surface: str,
    target_names: set[str],
) -> PatchRecipeConfiguration:
    document = object_value(read_json(path), str(path))
    if set(document) != {"version", "surface", "targets", "groups"}:
        raise ValueError(f"{path}: invalid root fields")
    if document["version"] != 2 or document["surface"] != surface:
        raise ValueError(f"{path}: unsupported patch recipe")

    raw_targets = object_value(document["targets"], f"{path}.targets")
    if set(raw_targets) != target_names:
        raise ValueError(f"{path}: invalid target set")
    targets: dict[str, TargetContract] = {}
    guards: dict[str, tuple[GuardRecipe, ...]] = {}
    for name, raw_value in raw_targets.items():
        target = object_value(raw_value, f"{path}.targets.{name}")
        if set(target) != {"address_bias", "size", "stock_sha256", "guards"}:
            raise ValueError(f"{path}: invalid {name} target")
        size = target["size"]
        if type(size) is not int or size <= 0:
            raise ValueError(f"{path}: invalid {name} size")
        targets[name] = TargetContract(
            _address(target["address_bias"], f"{name}.address_bias"),
            size,
            _hash(target["stock_sha256"], f"{name}.stock_sha256"),
        )
        raw_guards = target["guards"]
        if not isinstance(raw_guards, list):
            raise ValueError(f"{path}: {name}.guards must be an array")
        parsed_guards: list[GuardRecipe] = []
        for index, raw_guard in enumerate(raw_guards):
            context = f"{path}.targets.{name}.guards[{index}]"
            guard = object_value(raw_guard, context)
            if set(guard) != {"name", "file_offset", "expected"}:
                raise ValueError(f"{context}: invalid guard")
            guard_name = guard["name"]
            if not isinstance(guard_name, str) or _NAME.fullmatch(guard_name) is None:
                raise ValueError(f"{context}: invalid name")
            parsed_guards.append(
                GuardRecipe(
                    guard_name,
                    _address(guard["file_offset"], f"{context}.file_offset"),
                    _bytes(guard["expected"], f"{context}.expected"),
                )
            )
        guards[name] = tuple(parsed_guards)

    raw_groups = document["groups"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(f"{path}: groups must be a nonempty array")
    patches: dict[str, list[PatchRecipe]] = {name: [] for name in target_names}
    for group_index, raw_value in enumerate(raw_groups):
        context = f"{path}.groups[{group_index}]"
        group = object_value(raw_value, context)
        if set(group) != {"capability", "target", "address_bias", "patches"}:
            raise ValueError(f"{context}: invalid fields")
        capability, target_name = group["capability"], group["target"]
        if not isinstance(capability, str) or not capability:
            raise ValueError(f"{context}: invalid capability")
        if (
            not isinstance(target_name, str)
            or target_name not in targets
            or group["address_bias"] != targets[target_name].address_bias
        ):
            raise ValueError(f"{context}: invalid target")
        rows = group["patches"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{context}: patches must be nonempty")
        for row_index, raw_row in enumerate(rows):
            row_context = f"{context}.patches[{row_index}]"
            row = object_value(raw_row, row_context)
            expected_keys = set(row) & {"expected", "expected_zero_bytes"}
            replacement_keys = set(row) & {
                "assembly",
                "linked_call",
                "instruction",
                "generated",
            }
            if (
                set(row) != {"name", "address"} | expected_keys | replacement_keys
                or expected_keys not in ({"expected"}, {"expected_zero_bytes"})
                or len(replacement_keys) != 1
                or not isinstance(row["name"], str)
                or _NAME.fullmatch(row["name"]) is None
            ):
                raise ValueError(f"{row_context}: invalid patch row")
            if "expected" in row:
                expected = _bytes(row["expected"], f"{row_context}.expected")
            else:
                count = row["expected_zero_bytes"]
                if type(count) is not int or count <= 0:
                    raise ValueError(f"{row_context}: invalid zero-byte count")
                expected = bytes(count)

            if "assembly" in row:
                replacement = ReplacementRecipe(
                    "assembly",
                    sources=_assembly_sources(
                        row["assembly"], f"{row_context}.assembly"
                    ),
                )
            elif "linked_call" in row:
                link = row["linked_call"]
                if (
                    len(expected) != 4
                    or not isinstance(link, str)
                    or _NAME.fullmatch(link) is None
                ):
                    raise ValueError(f"{row_context}.linked_call is invalid")
                replacement = ReplacementRecipe("linked_call", link=link)
            elif "generated" in row:
                generator = row["generated"]
                if (
                    not isinstance(generator, str)
                    or _NAME.fullmatch(generator) is None
                ):
                    raise ValueError(f"{row_context}.generated is invalid")
                replacement = ReplacementRecipe("generated", generator=generator)
            else:
                instruction = row["instruction"]
                if (
                    not isinstance(instruction, str)
                    or not instruction.strip()
                    or "\n" in instruction
                    or "\r" in instruction
                ):
                    raise ValueError(f"{row_context}.instruction must be one line")
                replacement = ReplacementRecipe("instruction", instruction=instruction)
            patches[target_name].append(
                PatchRecipe(
                    capability,
                    row["name"],
                    _address(row["address"], f"{row_context}.address"),
                    expected,
                    replacement,
                )
            )
    return PatchRecipeConfiguration(
        surface,
        targets,
        guards,
        {name: tuple(rows) for name, rows in patches.items()},
    )
