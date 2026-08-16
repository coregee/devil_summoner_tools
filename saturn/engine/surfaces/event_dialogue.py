"""Build the general Saturn EVENT dialogue runtime."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from engine.core.patching import Patch, apply_patches
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.event_codec import load_event_dictionary
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "event_dialogue.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "event_dialogue" / "EVENT.BIN"
BUILD_PATH = GENERATED_ROOT / "event_dialogue_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "event_build.json"
SHOPSMP_TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "shopsmp_build.json"
SHOPSMP_TEXT_PATH = TEXT_GENERATED_ROOT / "SHOPSMP.EVE"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
FONT8_METRICS_PATH = FONT_ROOT / "FONT8_metrics.json"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_HEX = re.compile(r"0x[0-9a-f]+\Z")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_json(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates
        )
    except FileNotFoundError as error:
        raise ValueError(f"missing build input: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON") from error


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _fields(value: dict[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{context} fields are {sorted(value)}, expected {sorted(expected)}"
        )


def _digest(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _address(value: object, context: str) -> int:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase hexadecimal text")
    return int(value, 16)


def _bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def stock_event() -> bytes:
    validated = validate_source(load_catalog()["game"])
    return read_source_files(validated, ("EVENT.BIN",))["EVENT.BIN"]


def _validate_surface() -> None:
    surface = load_surfaces().surface("event.dialogue")
    if (
        surface.en.font != "font16"
        or surface.en.rows != 3
        or surface.en.width.unit != "pixels"
        or surface.en.width.value != 300
    ):
        raise ValueError(
            "event.dialogue engine patch requires font16, three rows, and 300 pixels"
        )


def _validate_text_build(codec_digest: str) -> None:
    document = _object(_read_json(TEXT_BUILD_PATH), str(TEXT_BUILD_PATH))
    _fields(
        document,
        {
            "version",
            "surface",
            "codec_sha256",
            "runtime_table_sha256",
            "font16_metrics_sha256",
            "records",
            "outputs",
        },
        str(TEXT_BUILD_PATH),
    )
    if (
        document["version"] != 1
        or document["surface"] != "event.dialogue"
        or document["codec_sha256"] != codec_digest
    ):
        raise ValueError("general EVENT text build does not match this surface/codec")
    outputs = _object(document["outputs"], f"{TEXT_BUILD_PATH}.outputs")
    expected_names = {
        "MESFILE.EVE",
        "EVFILE_0.EVE",
        "EVFILE_1.EVE",
        "EVFILE_2.EVE",
    }
    if set(outputs) != expected_names:
        raise ValueError("general EVENT text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if file_sha256(TEXT_GENERATED_ROOT / name) != _digest(
            row.get("sha256"), f"{TEXT_BUILD_PATH}.outputs.{name}.sha256"
        ):
            raise ValueError(f"generated {name} does not match its text build")


def validate_shopsmp_text_build(codec_digest: str) -> None:
    document = _object(
        _read_json(SHOPSMP_TEXT_BUILD_PATH), str(SHOPSMP_TEXT_BUILD_PATH)
    )
    _fields(
        document,
        {
            "version",
            "surface",
            "source",
            "codec_sha256",
            "runtime_table_sha256",
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "records",
            "deferred",
            "outputs",
        },
        str(SHOPSMP_TEXT_BUILD_PATH),
    )
    if (
        document["version"] != 1
        or document["surface"] != "event.dialogue"
        or document["source"] != "SHOPSMP.EVE"
        or document["codec_sha256"] != codec_digest
        or document["deferred"] is not None
    ):
        raise ValueError("SHOPSMP text build does not match the Fusion surface")
    records = _object(document["records"], f"{SHOPSMP_TEXT_BUILD_PATH}.records")
    if records != {"translated": 763, "deferred": 0, "total": 763}:
        raise ValueError("SHOPSMP text build is not the complete translated bank")
    expected_inputs = {
        "runtime_table_sha256": sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
    }
    for key, expected in expected_inputs.items():
        if document[key] != expected:
            raise ValueError(f"SHOPSMP text build has stale {key}")
    outputs = _object(document["outputs"], f"{SHOPSMP_TEXT_BUILD_PATH}.outputs")
    if set(outputs) != {"SHOPSMP.EVE"}:
        raise ValueError("SHOPSMP text build has the wrong output set")
    row = _object(
        outputs["SHOPSMP.EVE"],
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE",
    )
    _fields(
        row,
        {"sha256", "messages", "pages", "body_bytes"},
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE",
    )
    if file_sha256(SHOPSMP_TEXT_PATH) != _digest(
        row.get("sha256"),
        f"{SHOPSMP_TEXT_BUILD_PATH}.outputs.SHOPSMP.EVE.sha256",
    ):
        raise ValueError("generated SHOPSMP.EVE does not match its text build")


def _load_patch_config() -> tuple[int, int, str, tuple[Patch, ...], dict[str, str]]:
    document = _object(_read_json(CONFIG_PATH), str(CONFIG_PATH))
    _fields(
        document,
        {"version", "surface", "target", "inputs", "groups"},
        str(CONFIG_PATH),
    )
    if document["version"] != 1 or document["surface"] != "event.dialogue":
        raise ValueError(f"{CONFIG_PATH}: unsupported patch configuration")
    target = _object(document["target"], f"{CONFIG_PATH}.target")
    _fields(
        target,
        {"path", "load_address", "size", "stock_sha256", "patched_sha256"},
        f"{CONFIG_PATH}.target",
    )
    if target["path"] != "EVENT.BIN" or type(target["size"]) is not int:
        raise ValueError(f"{CONFIG_PATH}: invalid EVENT target")
    inputs = _object(document["inputs"], f"{CONFIG_PATH}.inputs")
    _fields(
        inputs,
        {
            "font16_metrics_sha256",
            "font12_metrics_sha256",
            "event_runtime_table_sha256",
        },
        f"{CONFIG_PATH}.inputs",
    )
    validated_inputs = {
        key: _digest(value, f"{CONFIG_PATH}.inputs.{key}")
        for key, value in inputs.items()
    }
    groups = document["groups"]
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"{CONFIG_PATH}.groups must be a nonempty array")
    patches: list[Patch] = []
    seen_groups: set[str] = set()
    for group_index, raw_group in enumerate(groups):
        group_context = f"{CONFIG_PATH}.groups[{group_index}]"
        group = _object(raw_group, group_context)
        _fields(group, {"id", "patches"}, group_context)
        group_id = group["id"]
        if not isinstance(group_id, str) or not group_id or group_id in seen_groups:
            raise ValueError(f"{group_context}.id is invalid or duplicated")
        seen_groups.add(group_id)
        rows = group["patches"]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{group_context}.patches must be nonempty")
        for patch_index, raw_patch in enumerate(rows):
            patch_context = f"{group_context}.patches[{patch_index}]"
            row = _object(raw_patch, patch_context)
            common = {"name", "address", "replacement"}
            if set(row) not in (
                common | {"expected"},
                common | {"expected_zero_bytes"},
            ):
                raise ValueError(f"{patch_context}: invalid fields")
            name = row["name"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"{patch_context}.name must be nonempty")
            replacement = _bytes(row["replacement"], f"{patch_context}.replacement")
            if "expected" in row:
                expected = _bytes(row["expected"], f"{patch_context}.expected")
            else:
                count = row["expected_zero_bytes"]
                if type(count) is not int or count <= 0:
                    raise ValueError(
                        f"{patch_context}.expected_zero_bytes is invalid"
                    )
                expected = bytes(count)
            patches.append(
                Patch(
                    group_id,
                    name,
                    _address(row["address"], f"{patch_context}.address"),
                    expected,
                    replacement,
                )
            )
    return (
        _address(target["load_address"], f"{CONFIG_PATH}.target.load_address"),
        target["size"],
        _digest(target["stock_sha256"], f"{CONFIG_PATH}.target.stock_sha256"),
        tuple(patches),
        {
            **validated_inputs,
            "patched_sha256": _digest(
                target["patched_sha256"],
                f"{CONFIG_PATH}.target.patched_sha256",
            ),
        },
    )


def build_event_dialogue() -> dict[Path, bytes]:
    _validate_surface()
    load_address, size, stock_digest, patches, inputs = _load_patch_config()
    codec_digest = file_sha256(CODEC_PATH)
    _validate_text_build(codec_digest)
    actual_inputs = {
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
        "event_runtime_table_sha256": sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
    }
    for key, actual in actual_inputs.items():
        if inputs[key] != actual:
            raise ValueError(
                f"event.dialogue patch input {key} is {actual}, expected {inputs[key]}"
            )
    stock = stock_event()
    if len(stock) != size or sha256(stock) != stock_digest:
        raise ValueError("stock EVENT.BIN does not match the patch target")
    patched = apply_patches(stock, load_address, patches)
    if sha256(patched) != inputs["patched_sha256"]:
        raise ValueError("event.dialogue patch output digest is not the proven build")
    manifest = {
        "version": 1,
        "surface": "event.dialogue",
        "patch_config_sha256": file_sha256(CONFIG_PATH),
        "text_build_sha256": file_sha256(TEXT_BUILD_PATH),
        "output_sha256": sha256(patched),
        "patch_groups": list(dict.fromkeys(patch.group for patch in patches)),
        "patches": len(patches),
    }
    return {
        OUTPUT_PATH: patched,
        BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
