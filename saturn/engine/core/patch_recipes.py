"""Typed, readable patch-site contracts for assembly-first engine surfaces."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from engine.core.config_io import TargetContract, object_value, read_json


ENGINE_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_HEX = re.compile(r"0x[0-9a-f]+\Z")
_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class ReplacementRecipe:
    kind: str
    sources: tuple[Path, ...] = ()
    pointer: int | None = None
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
    expected_sha256: str | None = None
    expected_size: int | None = None


@dataclass(frozen=True, slots=True)
class PatchRecipeConfiguration:
    surface: str
    targets: dict[str, TargetContract]
    inputs: dict[str, str]
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
    sources: list[Path] = []
    seen: set[Path] = set()
    root = ASSEMBLY_ROOT.resolve()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item or "\\" in item:
            raise ValueError(f"{context}[{index}] must be a POSIX relative path")
        relative = Path(item)
        if relative.is_absolute() or relative.suffix != ".s":
            raise ValueError(f"{context}[{index}] must name an .s file")
        path = (ASSEMBLY_ROOT / relative).resolve()
        if path.parent != root and root not in path.parents:
            raise ValueError(f"{context}[{index}] escapes the assembly root")
        if path in seen:
            raise ValueError(f"{context} repeats {item!r}")
        if not path.is_file():
            raise ValueError(f"{context}[{index}] does not exist: {item}")
        seen.add(path)
        sources.append(path)
    return tuple(sources)


def load_patch_recipe_configuration(
    path: Path,
    *,
    surface: str,
    target_names: set[str],
    input_names: set[str],
) -> PatchRecipeConfiguration:
    document = object_value(read_json(path), str(path))
    if set(document) != {"version", "surface", "targets", "inputs", "groups"}:
        raise ValueError(f"{path}: invalid root fields")
    if document["version"] != 2 or document["surface"] != surface:
        raise ValueError(f"{path}: unsupported patch recipe")

    raw_targets = object_value(document["targets"], f"{path}.targets")
    if set(raw_targets) != target_names:
        raise ValueError(f"{path}: invalid target set")
    targets: dict[str, TargetContract] = {}
    for name, raw_value in raw_targets.items():
        target = object_value(raw_value, f"{path}.targets.{name}")
        if set(target) != {"load_address", "size", "stock_sha256"}:
            raise ValueError(f"{path}: invalid {name} target")
        size = target["size"]
        if type(size) is not int or size <= 0:
            raise ValueError(f"{path}: invalid {name} size")
        targets[name] = TargetContract(
            _address(target["load_address"], f"{name}.load_address"),
            size,
            _hash(target["stock_sha256"], f"{name}.stock_sha256"),
        )

    raw_inputs = object_value(document["inputs"], f"{path}.inputs")
    if set(raw_inputs) != input_names:
        raise ValueError(f"{path}: invalid input set")
    inputs = {
        name: _hash(value, f"{path}.inputs.{name}")
        for name, value in raw_inputs.items()
    }

    raw_groups = document["groups"]
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError(f"{path}: groups must be a nonempty array")
    patches: dict[str, list[PatchRecipe]] = {name: [] for name in target_names}
    for group_index, raw_value in enumerate(raw_groups):
        context = f"{path}.groups[{group_index}]"
        group = object_value(raw_value, context)
        if set(group) != {"capability", "target", "load_address", "patches"}:
            raise ValueError(f"{context}: invalid fields")
        capability = group["capability"]
        target_name = group["target"]
        if not isinstance(capability, str) or not capability:
            raise ValueError(f"{context}: invalid capability")
        if (
            not isinstance(target_name, str)
            or target_name not in targets
            or group["load_address"] != targets[target_name].load_address
        ):
            raise ValueError(f"{context}: invalid target")
        rows = group["patches"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{context}: patches must be nonempty")
        for row_index, raw_row in enumerate(rows):
            row_context = f"{context}.patches[{row_index}]"
            row = object_value(raw_row, row_context)
            expected_keys = set(row) & {
                "expected",
                "expected_zero_bytes",
                "expected_sha256",
                "expected_size",
            }
            replacement_keys = set(row) & {
                "assembly",
                "pointer",
                "linked_pointer",
                "instruction",
                "generated",
            }
            if (
                set(row) != {"name", "address"} | expected_keys | replacement_keys
                or expected_keys
                not in (
                    {"expected"},
                    {"expected_zero_bytes"},
                    {"expected_sha256", "expected_size"},
                )
                or len(replacement_keys) != 1
                or not isinstance(row["name"], str)
                or not row["name"]
            ):
                raise ValueError(f"{row_context}: invalid patch row")
            expected_sha256 = None
            expected_size = None
            if "expected" in row:
                expected = _bytes(row["expected"], f"{row_context}.expected")
            elif "expected_zero_bytes" in row:
                count = row["expected_zero_bytes"]
                if type(count) is not int or count <= 0:
                    raise ValueError(f"{row_context}: invalid zero-byte count")
                expected = bytes(count)
            else:
                expected = b""
                expected_sha256 = _hash(
                    row["expected_sha256"], f"{row_context}.expected_sha256"
                )
                expected_size = row["expected_size"]
                if type(expected_size) is not int or expected_size <= 0:
                    raise ValueError(f"{row_context}: invalid expected size")

            if "assembly" in row:
                replacement = ReplacementRecipe(
                    "assembly",
                    sources=_assembly_sources(row["assembly"], f"{row_context}.assembly"),
                )
            elif "pointer" in row:
                if len(expected) != 4:
                    raise ValueError(f"{row_context}: a pointer patch must own four bytes")
                replacement = ReplacementRecipe(
                    "pointer", pointer=_address(row["pointer"], f"{row_context}.pointer")
                )
            elif "linked_pointer" in row:
                link = row["linked_pointer"]
                if (
                    len(expected) != 4
                    or not isinstance(link, str)
                    or _NAME.fullmatch(link) is None
                ):
                    raise ValueError(
                        f"{row_context}.linked_pointer must name a four-byte link"
                    )
                replacement = ReplacementRecipe("linked_pointer", link=link)
            elif "generated" in row:
                generator = row["generated"]
                if (
                    not isinstance(generator, str)
                    or _NAME.fullmatch(generator) is None
                ):
                    raise ValueError(
                        f"{row_context}.generated must be a lowercase generator name"
                    )
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
                    expected_sha256,
                    expected_size,
                )
            )
    return PatchRecipeConfiguration(
        surface,
        targets,
        inputs,
        {name: tuple(rows) for name, rows in patches.items()},
    )


def resolve_recipe_expected(
    recipe: PatchRecipe,
    source: bytes,
    load_address: int,
) -> bytes:
    """Resolve an exact or digest-sized guard against one composition base."""
    if recipe.expected:
        return recipe.expected
    if recipe.expected_sha256 is None or recipe.expected_size is None:
        raise ValueError(f"{recipe.group}/{recipe.name}: missing expected guard")
    start = recipe.address - load_address
    end = start + recipe.expected_size
    if start < 0 or end > len(source):
        raise ValueError(
            f"{recipe.group}/{recipe.name}: digest guard lies outside the target"
        )
    expected = source[start:end]
    actual = hashlib.sha256(expected).hexdigest()
    if actual != recipe.expected_sha256:
        raise ValueError(
            f"{recipe.group}/{recipe.name}: expected SHA-256 "
            f"{recipe.expected_sha256}, found {actual}"
        )
    return expected
