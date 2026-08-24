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
from psp.font.util.comp_party_ark10 import (
    CONFIG_PATH as COMP_PARTY_ARK10_CONFIG_PATH,
    build_comp_party_ark10,
)
from psp.font.util.dungeon_locations import (
    CONFIG_PATH as DUNGEON_LOCATION_FONT16_PATH,
    build_dungeon_location_font16,
)
from psp.font.util.fmv_subtitles import (
    CONFIG_PATH as FMV_FONT16_PATH,
    build_fmv_subtitle_font16,
)
from psp.font.util.map2d import (
    CONFIG_PATH as MAP2D_CONFIG_PATH,
    build_map2d_fonts,
)
from psp.text.util.map2d import (
    CONFIG_PATH as MAP2D_TEXT_CONFIG_PATH,
    FIELD_ASSET_PATH as MAP2D_FIELD_ASSET_PATH,
    LOCATION_ASSET_PATH as MAP2D_LOCATION_ASSET_PATH,
    UI_ASSET_PATH as MAP2D_UI_ASSET_PATH,
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
from psp.text.util.event_dvlname import CONFIG_PATH as DVLNAME_CONFIG_PATH
from psp.text.util.name_entry import (
    ASSET_PATH as NAME_ENTRY_ASSET_PATH,
    CONFIG_PATH as NAME_ENTRY_CONFIG_PATH,
)
from psp.text.util.title_help import CONFIG_PATH as TITLE_TEXT_CONFIG_PATH


FONT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = FONT_ROOT / "generated" / "game" / "title_help_metrics.json"
DATAPACK_PATH = FONT_ROOT / "generated" / "game" / "datapack.bin"
EVE_FILES_PATH = FONT_ROOT / "generated" / "game" / "eve_files.bin"
MANIFEST_PATH = FONT_ROOT / "generated" / "game" / "psp.fonts.json"
ENCODING_CODEC_PATH = FONT_ROOT.parent / "text" / "util" / "event_packed.py"
DEMON_ASSET_PATH = FONT_ROOT.parent.parent / "assets" / "text" / "demons.json"
ITEM_ASSET_PATH = FONT_ROOT.parent.parent / "assets" / "text" / "items.json"


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
    dungeon_result = build_dungeon_location_font16(source, result)
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
    comp_party_ark10 = build_comp_party_ark10(eve_source, eve_result.data)
    map2d = build_map2d_fonts(
        source,
        dungeon_result.data,
        eve_source,
        comp_party_ark10.data,
    )
    manifest = {
        "version": 1,
        "surface": "psp.fonts",
        "components": [
            "title_help.font16",
            "fmv_subtitles.font16",
            "config_menu.font16",
            "battle_names.font16",
            "dungeon_locations.font16",
            "command_menu_help.eve_ascii",
            "comp_party_panel.ark10",
            "map_2d.font16",
            "map_2d.eve",
        ],
        "inputs": {
            "asset_sha256": _sha(TITLE_ASSET_PATH.read_bytes()),
            "config_sha256": _sha(FONT16_CONFIG_PATH.read_bytes()),
            "title_text_config_sha256": _sha(TITLE_TEXT_CONFIG_PATH.read_bytes()),
            "encoding_codec_sha256": _sha(ENCODING_CODEC_PATH.read_bytes()),
            "config_menu_config_sha256": _sha(CONFIG_FONT16_PATH.read_bytes()),
            "battle_name_dvl_binding_sha256": _sha(DVLNAME_CONFIG_PATH.read_bytes()),
            "battle_name_demon_asset_sha256": _sha(DEMON_ASSET_PATH.read_bytes()),
            "battle_name_item_asset_sha256": _sha(ITEM_ASSET_PATH.read_bytes()),
            "battle_name_profile_asset_sha256": _sha(NAME_ENTRY_ASSET_PATH.read_bytes()),
            "battle_name_profile_config_sha256": _sha(NAME_ENTRY_CONFIG_PATH.read_bytes()),
            "dungeon_location_config_sha256": _sha(
                DUNGEON_LOCATION_FONT16_PATH.read_bytes()
            ),
            "fmv_subtitle_config_sha256": _sha(FMV_FONT16_PATH.read_bytes()),
            "eve_ascii_config_sha256": _sha(EVE_ASCII_CONFIG_PATH.read_bytes()),
            "comp_party_ark10_config_sha256": _sha(
                COMP_PARTY_ARK10_CONFIG_PATH.read_bytes()
            ),
            "map2d_config_sha256": _sha(MAP2D_CONFIG_PATH.read_bytes()),
            "map2d_text_config_sha256": _sha(MAP2D_TEXT_CONFIG_PATH.read_bytes()),
            "map2d_ui_asset_sha256": _sha(MAP2D_UI_ASSET_PATH.read_bytes()),
            "map2d_field_asset_sha256": _sha(MAP2D_FIELD_ASSET_PATH.read_bytes()),
            "map2d_location_asset_sha256": _sha(MAP2D_LOCATION_ASSET_PATH.read_bytes()),
            "metrics_sha256": _sha(metrics_data),
            "source_sha256": _sha(source),
            "eve_source_sha256": _sha(eve_source),
        },
        "outputs": {
            DATAPACK_PATH.name: {
                "size": len(map2d.datapack),
                "sha256": _sha(map2d.datapack),
            },
            EVE_FILES_PATH.name: {
                "size": len(map2d.eve_files),
                "sha256": _sha(map2d.eve_files),
            },
        },
        "changed_members": [9, 15],
        "changed_byte_count": dungeon_result.changed_byte_count,
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
        "comp_party_ark10": {
            "first_code": comp_party_ark10.owned_codes[0],
            "last_code": comp_party_ark10.owned_codes[-1],
            "changed_codes": list(comp_party_ark10.changed_codes),
            "added_changed_byte_count": comp_party_ark10.added_changed_byte_count,
            "advance_table": list(comp_party_ark10.advance_table),
            "characters": [
                {"character": character, "code": code, "advance": advance}
                for character, code, advance in comp_party_ark10.mappings
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
        "dungeon_locations": {
            "required_draw_code_limit": dungeon_result.required_limit,
            "reserved_codes": list(range(result.required_limit, 0x06B0)),
            "owned_codes": list(dungeon_result.owned_codes),
            "changed_codes": list(dungeon_result.changed_codes),
            "digit_codes": list(dungeon_result.digit_codes),
            "basement_code": dungeon_result.basement_code,
            "floor_code": dungeon_result.floor_code,
            "added_changed_byte_count": dungeon_result.added_changed_byte_count,
            "records": [
                {
                    "location_id": record.location_id,
                    "text": record.text,
                    "lines": [line.text for line in record.lines],
                    "glyphs": [
                        {
                            "character": glyph.character,
                            "code": glyph.code,
                            "x": glyph.x_offset,
                            "row": glyph.row,
                            "advance": glyph.advance,
                        }
                        for glyph in record.glyphs
                    ],
                }
                for record in dungeon_result.records
            ],
        },
        "map2d": {
            "required_draw_code_limit": map2d.required_limit,
            "owned_codes": list(map2d.owned_codes),
            "changed_codes": list(map2d.changed_codes),
            "eve_owned_codes": list(map2d.eve_owned_codes),
            "eve_changed_codes": list(map2d.eve_changed_codes),
            "scratch_ward_codes": list(map2d.scratch_ward_codes),
            "scratch_city_codes": list(map2d.scratch_city_codes),
            "datapack_added_changed_byte_count": map2d.datapack_added_changed_byte_count,
            "eve_added_changed_byte_count": map2d.eve_added_changed_byte_count,
            "records": [
                {
                    "name": record.name,
                    "text": record.text,
                    "words": list(record.words),
                    "eve_words": list(record.eve_words),
                    "measured_width": record.measured_width,
                }
                for record in map2d.records
            ],
            "fixed_locations": [
                {
                    "location_id": record.location_id,
                    "text": record.text,
                    "words": list(record.words),
                    "measured_width": record.measured_width,
                }
                for record in map2d.fixed_locations
            ],
            "printable": [
                {"character": glyph.character, "code": glyph.code, "advance": glyph.advance}
                for glyph in map2d.printable
            ],
        },
    }
    manifest_data = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    for path, data in (
        (OUTPUT_PATH, metrics_data),
        (DATAPACK_PATH, map2d.datapack),
        (EVE_FILES_PATH, map2d.eve_files),
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
