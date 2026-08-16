"""Build the Saturn runtime patches required by configured text surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from engine.patching import Patch, apply_patches  # noqa: E402
from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from text.util.event_codec import load_event_dictionary  # noqa: E402
from text.util.surfaces import load_surfaces  # noqa: E402


CONFIG_PATH = ENGINE_ROOT / "config" / "event_dialogue.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
OUTPUT_PATH = GENERATED_ROOT / "EVENT.BIN"
BUILD_MANIFEST_PATH = GENERATED_ROOT / "event_dialogue_build.json"
TEXT_ROOT = SATURN_ROOT / "text"
TEXT_GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
TEXT_BUILD_PATH = TEXT_GENERATED_ROOT / "event_build.json"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT_ROOT = SATURN_ROOT / "font" / "generated" / "game"
FONT16_METRICS_PATH = FONT_ROOT / "FONT16_metrics.json"
FONT12_METRICS_PATH = FONT_ROOT / "FONT12_metrics.json"
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_HEX_RE = re.compile(r"0x[0-9a-f]+\Z")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_json(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
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


def _hash(value: object, context: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _hex_integer(value: object, context: str) -> int:
    if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{context} must be lowercase hexadecimal text")
    return int(value, 16)


def _hex_bytes(value: object, context: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ValueError(f"{context} must be nonempty even-length hexadecimal")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{context} contains invalid hexadecimal") from error


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return _sha256(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"missing generated input: {path}") from error


def _stock_event() -> bytes:
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
    expected_names = {"MESFILE.EVE", "EVFILE_0.EVE", "EVFILE_1.EVE", "EVFILE_2.EVE"}
    if set(outputs) != expected_names:
        raise ValueError("general EVENT text build has the wrong output set")
    for name, raw_row in outputs.items():
        row = _object(raw_row, f"{TEXT_BUILD_PATH}.outputs.{name}")
        if _file_sha256(TEXT_GENERATED_ROOT / name) != _hash(
            row.get("sha256"), f"{TEXT_BUILD_PATH}.outputs.{name}.sha256"
        ):
            raise ValueError(f"generated {name} does not match its text build")


def _load_patch_config() -> tuple[int, int, str, tuple[Patch, ...], dict[str, str]]:
    document = _object(_read_json(CONFIG_PATH), str(CONFIG_PATH))
    _fields(document, {"version", "surface", "target", "inputs", "groups"}, str(CONFIG_PATH))
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
    validated_inputs = {key: _hash(value, f"{CONFIG_PATH}.inputs.{key}") for key, value in inputs.items()}
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
            if set(row) not in (common | {"expected"}, common | {"expected_zero_bytes"}):
                raise ValueError(f"{patch_context}: invalid fields")
            name = row["name"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"{patch_context}.name must be nonempty")
            replacement = _hex_bytes(row["replacement"], f"{patch_context}.replacement")
            if "expected" in row:
                expected = _hex_bytes(row["expected"], f"{patch_context}.expected")
            else:
                count = row["expected_zero_bytes"]
                if type(count) is not int or count <= 0:
                    raise ValueError(f"{patch_context}.expected_zero_bytes is invalid")
                expected = bytes(count)
            patches.append(
                Patch(
                    group_id,
                    name,
                    _hex_integer(row["address"], f"{patch_context}.address"),
                    expected,
                    replacement,
                )
            )
    return (
        _hex_integer(target["load_address"], f"{CONFIG_PATH}.target.load_address"),
        target["size"],
        _hash(target["stock_sha256"], f"{CONFIG_PATH}.target.stock_sha256"),
        tuple(patches),
        {**validated_inputs, "patched_sha256": _hash(target["patched_sha256"], f"{CONFIG_PATH}.target.patched_sha256")},
    )


def build_event_dialogue() -> dict[Path, bytes]:
    _validate_surface()
    load_address, size, stock_digest, patches, inputs = _load_patch_config()
    codec_digest = _file_sha256(CODEC_PATH)
    _validate_text_build(codec_digest)
    actual_inputs = {
        "font16_metrics_sha256": _file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": _file_sha256(FONT12_METRICS_PATH),
        "event_runtime_table_sha256": _sha256(
            load_event_dictionary(CODEC_PATH).runtime_table()
        ),
    }
    for key, actual in actual_inputs.items():
        if inputs[key] != actual:
            raise ValueError(
                f"event.dialogue patch input {key} is {actual}, expected {inputs[key]}"
            )
    stock = _stock_event()
    if len(stock) != size or _sha256(stock) != stock_digest:
        raise ValueError("stock EVENT.BIN does not match the patch target")
    patched = apply_patches(stock, load_address, patches)
    if _sha256(patched) != inputs["patched_sha256"]:
        raise ValueError("event.dialogue patch output digest is not the proven build")
    manifest = {
        "version": 1,
        "surface": "event.dialogue",
        "patch_config_sha256": _file_sha256(CONFIG_PATH),
        "text_build_sha256": _file_sha256(TEXT_BUILD_PATH),
        "output_sha256": _sha256(patched),
        "patch_groups": list(dict.fromkeys(patch.group for patch in patches)),
        "patches": len(patches),
    }
    return {
        OUTPUT_PATH: patched,
        BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def _atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _publish(outputs: dict[Path, bytes], *, check: bool) -> None:
    stale = [path for path, value in outputs.items() if not path.is_file() or path.read_bytes() != value]
    if check:
        if stale:
            raise ValueError(
                "stale EVENT engine outputs: "
                + ", ".join(str(path.relative_to(SATURN_ROOT)) for path in stale)
            )
        return
    for path, value in outputs.items():
        if not path.is_file() or path.read_bytes() != value:
            _atomic_write(path, value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surface", nargs="?", default="event.dialogue", choices=("event.dialogue",))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        outputs = build_event_dialogue()
        _publish(outputs, check=arguments.check)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(f"{'verified' if arguments.check else 'built'} event.dialogue engine patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
