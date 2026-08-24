"""Build or verify the canonical PSP EVENT and boss-combat text banks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath

if __package__ in {None, ""}:
    import sys

    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)

from psp.font.util.eve_ascii import glyph_code
from psp.text.util.assets import ASSET_ROOT
from psp.text.util.combat_dialogue import (
    COMBAT_DIALOGUE_CONFIG_PATH,
    build_bosstalk_dialogue,
)
from psp.text.util.event_corpus import (
    EVENT_BINDINGS_ROOT,
    EVENT_OPTION_CONFIG_PATH,
    build_event_corpus,
)
from psp.text.util.event_dvlname import CONFIG_PATH as DVLNAME_CONFIG_PATH


PSP_ROOT = Path(__file__).resolve().parents[1]
TEXT_ROOT = Path(__file__).resolve().parent
ENCODING_CODEC_PATH = TEXT_ROOT / "util" / "event_packed.py"
FONT_ROOT = PSP_ROOT / "font"
FONT_GENERATED = FONT_ROOT / "generated" / "game"
FONT_EVE_PATH = FONT_GENERATED / "eve_files.bin"
FONT_MANIFEST_PATH = FONT_GENERATED / "psp.fonts.json"
OUTPUT_ROOT = TEXT_ROOT / "generated" / "game"
OUTPUT_PATH = OUTPUT_ROOT / "eve_files.bin"
MANIFEST_PATH = OUTPUT_ROOT / "psp.events.json"
EXPECTED_OUTPUT_SHA256 = (
    "eb373f15d3bdd2e350d9680d91fb344d54272cb5f4c08b2ef6879b3835e2d89d"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _publish(path: Path, data: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"generated PSP EVENT output is missing or stale: {path}")
        print(f"verified {path.relative_to(TEXT_ROOT).as_posix()}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"generated {path.relative_to(TEXT_ROOT).as_posix()}")


def _font_input() -> tuple[bytes, bytes]:
    if not FONT_MANIFEST_PATH.is_file() or not FONT_EVE_PATH.is_file():
        raise ValueError("PSP EVENT text requires generated EVE font inputs")
    manifest_data = FONT_MANIFEST_PATH.read_bytes()
    try:
        document = json.loads(manifest_data)
    except json.JSONDecodeError as error:
        raise ValueError("invalid PSP font manifest") from error
    outputs = document.get("outputs") if isinstance(document, dict) else None
    contract = outputs.get(FONT_EVE_PATH.name) if isinstance(outputs, dict) else None
    if (
        document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
        or set(contract) != {"size", "sha256"}
    ):
        raise ValueError("PSP font manifest has no valid EVE output")
    source = FONT_EVE_PATH.read_bytes()
    if len(source) != contract["size"] or _sha(source) != contract["sha256"]:
        raise ValueError("generated PSP EVE font archive violates its manifest")
    return source, manifest_data


def _advance_table(manifest_data: bytes) -> bytes:
    document = json.loads(manifest_data)
    table = document.get("eve_ascii", {}).get("advance_table")
    try:
        widths = bytes(table)
    except (TypeError, ValueError) as error:
        raise ValueError("PSP font manifest has no valid EVE advance table") from error
    if len(widths) != 95 or any(width == 0 for width in widths):
        raise ValueError("PSP EVE advance table must contain 95 positive bytes")
    return widths


def _asset_path(relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe EVENT asset path: {relative!r}")
    return ASSET_ROOT / Path(*path.parts)


def build(*, check: bool) -> None:
    source, font_manifest_data = _font_input()
    widths = _advance_table(font_manifest_data)

    def measure_ascii(text: str) -> int:
        return sum(widths[glyph_code(character) - 0x1E20] for character in text)

    result = build_event_corpus(source, measure_ascii=measure_ascii)
    combat = build_bosstalk_dialogue(
        result.eve_files,
        measure_ascii=measure_ascii,
    )
    digest = _sha(combat.eve_files)
    if digest != EXPECTED_OUTPUT_SHA256:
        raise ValueError(
            f"composed PSP EVENT archive contract changed: {digest}"
        )
    asset_paths = tuple(
        sorted(
            {
                _asset_path(relative)
                for relative in (*result.corpus_paths, *combat.corpus_paths)
            }
            | {ASSET_ROOT / "demons.json"}
        )
    )
    binding_paths = tuple(sorted(EVENT_BINDINGS_ROOT.glob("*.EVE.json")))
    manifest = {
        "version": 1,
        "surface": "psp.event_text",
        "components": [
            "event_dialogue.packed_text",
            "event_options.raw_text",
            "event_inserts.dvlname",
            "boss_combat_dialogue.packed_text",
        ],
        "inputs": {
            "font_manifest_sha256": _sha(font_manifest_data),
            "font_eve_sha256": _sha(source),
            "encoding_codec_sha256": _sha(ENCODING_CODEC_PATH.read_bytes()),
            "option_config_sha256": _sha(EVENT_OPTION_CONFIG_PATH.read_bytes()),
            "dvlname_config_sha256": _sha(DVLNAME_CONFIG_PATH.read_bytes()),
            "combat_dialogue_config_sha256": _sha(
                COMBAT_DIALOGUE_CONFIG_PATH.read_bytes()
            ),
            "bindings": {
                path.name: _sha(path.read_bytes()) for path in binding_paths
            },
            "assets": {
                path.relative_to(ASSET_ROOT.parent.parent).as_posix(): _sha(
                    path.read_bytes()
                )
                for path in asset_paths
            },
        },
        "outputs": {
            OUTPUT_PATH.name: {
                "size": len(combat.eve_files),
                "sha256": digest,
            }
        },
        "changed_members": [*result.changed_member_indices, combat.bank.member_index],
        "changed_byte_count": result.changed_byte_count + combat.changed_byte_count,
        "translated_assets": len(result.translated_record_ids)
        + len(combat.translated_record_ids),
        "preserved_assets": len(result.preserved_record_ids),
        "banks": [
            {
                "name": bank.name,
                "member_index": bank.member_index,
                "message_count": bank.message_count,
                "translated_message_count": bank.translated_message_count,
                "translated_page_count": len(bank.translated_record_ids),
                "raw_message_count": len(bank.raw_message_indices),
                "translated_option_count": len(bank.translated_option_message_indices),
                "used_body_bytes": bank.used_body_bytes,
                "body_capacity_bytes": bank.body_capacity_bytes,
                "dvlname_table_offset": bank.dvlname_table_offset,
                "dvlname_table_size": bank.dvlname_table_size,
                "changed_byte_count": bank.changed_byte_count,
                "sha256": _sha(bank.data),
            }
            for bank in result.banks
        ]
        + [
            {
                "name": combat.bank.name,
                "member_index": combat.bank.member_index,
                "message_count": combat.bank.message_count,
                "translated_message_count": combat.bank.message_count,
                "translated_page_count": len(combat.bank.translated_record_ids),
                "raw_message_count": 0,
                "translated_option_count": 0,
                "used_body_bytes": combat.bank.used_body_bytes,
                "body_capacity_bytes": combat.bank.body_capacity_bytes,
                "dvlname_table_offset": None,
                "dvlname_table_size": 0,
                "changed_byte_count": combat.bank.changed_byte_count,
                "sha256": _sha(combat.bank.data),
            }
        ],
    }
    manifest_data = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _publish(OUTPUT_PATH, combat.eve_files, check=check)
    _publish(MANIFEST_PATH, manifest_data, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("all",), nargs="?", default="all")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
