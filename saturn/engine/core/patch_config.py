"""Strict loader for surface-scoped Saturn binary patch configurations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from engine.core.patching import Patch


_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_HEX_RE = re.compile(r"0x[0-9a-f]+\Z")


@dataclass(frozen=True, slots=True)
class TargetContract:
    load_address: int
    size: int
    stock_sha256: str


@dataclass(frozen=True, slots=True)
class PatchConfiguration:
    surface: str
    targets: dict[str, TargetContract]
    inputs: dict[str, str]
    patches: dict[str, tuple[Patch, ...]]


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def read_json(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing build input: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error


def object_value(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _hash(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase hexadecimal text")
    return int(value, 16)


def _bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def load_patch_configuration(
    path: Path,
    *,
    surface: str,
    target_names: set[str],
    input_names: set[str],
) -> PatchConfiguration:
    document = object_value(read_json(path), str(path))
    if set(document) != {"version", "surface", "targets", "inputs", "groups"}:
        raise ValueError(f"{path}: invalid root fields")
    if document["version"] != 1 or document["surface"] != surface:
        raise ValueError(f"{path}: unsupported patch configuration")

    raw_targets = object_value(document["targets"], f"{path}.targets")
    if set(raw_targets) != target_names:
        raise ValueError(f"{path}: invalid target set")
    targets: dict[str, TargetContract] = {}
    for name, raw_target in raw_targets.items():
        target = object_value(raw_target, f"{path}.targets.{name}")
        if set(target) != {"load_address", "size", "stock_sha256"}:
            raise ValueError(f"{path}: invalid {name} target")
        if type(target["size"]) is not int or target["size"] <= 0:
            raise ValueError(f"{path}: invalid {name} size")
        targets[name] = TargetContract(
            _hex(target["load_address"], f"{name}.load_address"),
            target["size"],
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
    patches: dict[str, list[Patch]] = {name: [] for name in targets}
    for group_index, raw_group in enumerate(raw_groups):
        context = f"{path}.groups[{group_index}]"
        group = object_value(raw_group, context)
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
        for index, raw_row in enumerate(rows):
            row_context = f"{context}.patches[{index}]"
            row = object_value(raw_row, row_context)
            expected_keys = set(row) & {"expected", "expected_zero_bytes"}
            replacement_keys = set(row) & {"replacement", "replacement_zero_bytes"}
            if (
                set(row) != {"name", "address"} | expected_keys | replacement_keys
                or len(expected_keys) != 1
                or len(replacement_keys) != 1
                or not isinstance(row["name"], str)
                or not row["name"]
            ):
                raise ValueError(f"{row_context}: invalid patch row")
            if "expected" in row:
                expected = _bytes(row["expected"], f"{row_context}.expected")
            else:
                size = row["expected_zero_bytes"]
                if type(size) is not int or size <= 0:
                    raise ValueError(f"{row_context}: invalid expected zero size")
                expected = bytes(size)
            if "replacement" in row:
                replacement = _bytes(
                    row["replacement"], f"{row_context}.replacement"
                )
            else:
                size = row["replacement_zero_bytes"]
                if type(size) is not int or size <= 0:
                    raise ValueError(f"{row_context}: invalid replacement zero size")
                replacement = bytes(size)
            patches[target_name].append(
                Patch(
                    capability,
                    row["name"],
                    _hex(row["address"], f"{row_context}.address"),
                    expected,
                    replacement,
                )
            )
    return PatchConfiguration(
        surface,
        targets,
        inputs,
        {name: tuple(rows) for name, rows in patches.items()},
    )
