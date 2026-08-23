"""Build or verify generated PSP font runtime inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)

from psp.font.util.metrics import build_title_help_metrics, metric_bytes
from psp.font.util.config_menu import (
    CONFIG_PATH as CONFIG_FONT16_PATH,
    build_config_font16,
)
from psp.font.util.fmv_subtitles import (
    CONFIG_PATH as FMV_FONT16_PATH,
    build_fmv_subtitle_font16,
)
from psp.font.util.eve_ascii import (
    CONFIG_PATH as EVE_ASCII_CONFIG_PATH,
    build_eve_ascii,
)
from psp.font.util.title_help import (
    CONFIG_PATH as FONT16_CONFIG_PATH,
    build_title_help_font16,
    load_config as load_font16_config,
)
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import TITLE_ASSET_PATH
from psp.text.util.title_help import CONFIG_PATH as TITLE_TEXT_CONFIG_PATH


FONT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = FONT_ROOT / "generated" / "game" / "title_help_metrics.json"
DATAPACK_PATH = FONT_ROOT / "generated" / "game" / "datapack.bin"
EVE_FILES_PATH = FONT_ROOT / "generated" / "game" / "eve_files.bin"
MANIFEST_PATH = FONT_ROOT / "generated" / "game" / "psp.fonts.json"
ENCODING_CODEC_PATH = FONT_ROOT.parent / "text" / "util" / "event_packed.py"


def publish(path: Path, data: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"generated PSP font input is missing or stale: {path}")
        print(f"verified {path.relative_to(FONT_ROOT).as_posix()}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
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
    print(f"generated {path.relative_to(FONT_ROOT).as_posix()}")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_fonts(*, check: bool) -> None:
    metrics = build_title_help_metrics()
    metrics_data = metric_bytes(metrics)
    disc = load_catalog()["game"]
    source_iso = validate_source(disc, verify_hash=True)
    config = load_font16_config()
    extent, source = read_iso9660_file(source_iso, config.iso_path)
    contract = disc.entries.get("datapack")
    if (
        contract is None
        or extent.size != contract.size
        or len(source) != contract.size
        or _sha(source) != contract.sha256
    ):
        raise ValueError("PSP datapack disc contract changed")
    title_result = build_title_help_font16(source, config)
    fmv_result = build_fmv_subtitle_font16(source)
    result = build_config_font16(source, title_result, fmv_result)
    eve_config = json.loads(EVE_ASCII_CONFIG_PATH.read_text(encoding="utf-8"))
    eve_contract = disc.entries.get("eve_files")
    if eve_contract is None:
        raise ValueError("PSP disc catalogue has no eve_files contract")
    eve_extent, eve_source = read_iso9660_file(source_iso, eve_config["iso_path"])
    if (
        eve_extent.size != eve_contract.size
        or len(eve_source) != eve_contract.size
        or _sha(eve_source) != eve_contract.sha256
    ):
        raise ValueError("PSP eve_files disc contract changed")
    eve_result = build_eve_ascii(eve_source)
    manifest = {
        "version": 1,
        "surface": "psp.fonts",
        "components": [
            "title_help.font16",
            "fmv_subtitles.font16",
            "config_menu.font16",
            "command_menu_help.eve_ascii",
        ],
        "inputs": {
            "asset_sha256": _sha(TITLE_ASSET_PATH.read_bytes()),
            "config_sha256": _sha(FONT16_CONFIG_PATH.read_bytes()),
            "title_text_config_sha256": _sha(TITLE_TEXT_CONFIG_PATH.read_bytes()),
            "encoding_codec_sha256": _sha(ENCODING_CODEC_PATH.read_bytes()),
            "config_menu_config_sha256": _sha(CONFIG_FONT16_PATH.read_bytes()),
            "fmv_subtitle_config_sha256": _sha(FMV_FONT16_PATH.read_bytes()),
            "eve_ascii_config_sha256": _sha(EVE_ASCII_CONFIG_PATH.read_bytes()),
            "metrics_sha256": _sha(metrics_data),
            "source_sha256": _sha(source),
            "eve_source_sha256": _sha(eve_source),
        },
        "outputs": {
            DATAPACK_PATH.name: {
                "size": len(result.data),
                "sha256": _sha(result.data),
            },
            EVE_FILES_PATH.name: {
                "size": len(eve_result.data),
                "sha256": _sha(eve_result.data),
            },
        },
        "changed_members": [9, 15],
        "changed_byte_count": result.changed_byte_count,
        "eve_ascii": {
            "first_code": 0x1E20,
            "last_code": 0x1E7E,
            "changed_codes": list(eve_result.changed_codes),
            "changed_byte_count": eve_result.changed_byte_count,
            "advance_table": list(eve_result.advance_table),
            "characters": [
                {"character": character, "code": code, "advance": advance}
                for character, code, advance in eve_result.mappings
            ],
        },
        "fmv_subtitles": {
            "first_code": fmv_result.changed_codes[0],
            "required_draw_code_limit": fmv_result.changed_codes[-1] + 1,
            "changed_codes": list(fmv_result.changed_codes),
            "characters": [
                {"character": character, "code": code, "advance": advance}
                for character, code, advance in fmv_result.mappings
            ],
        },
        "config_menu": {
            "required_draw_code_limit": result.required_limit,
            "ark16_advance_first_code": 0x0672,
            "ark16_advance_table": list(result.advance_table),
            "ark12": [
                {"character": character, "code": code, "advance": advance}
                for character, code, advance in result.ark12
            ],
            "ark16": [
                {"character": character, "code": code, "advance": advance}
                for character, code, advance in result.ark16
            ],
        },
    }
    manifest_data = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    for path, data in (
        (OUTPUT_PATH, metrics_data),
        (DATAPACK_PATH, result.data),
        (EVE_FILES_PATH, eve_result.data),
        (MANIFEST_PATH, manifest_data),
    ):
        publish(path, data, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        choices=("all",),
        nargs="?",
        default="all",
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build_fonts(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
