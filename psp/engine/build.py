"""Build or verify generated PSP engine surfaces."""

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

from psp.engine.surfaces.battle_console import (
    CONFIG_PATH as BATTLE_CONSOLE_CONFIG_PATH,
    build_battle_console,
)
from psp.engine.surfaces.battle_names import (
    CONFIG_PATH as BATTLE_NAMES_CONFIG_PATH,
    build_battle_names,
)
from psp.engine.surfaces.config_menu import build_config_menu
from psp.engine.surfaces.command_menu_help import (
    CONFIG_PATH as COMMAND_HELP_CONFIG_PATH,
    build_command_menu_help,
    load_eve_widths,
)
from psp.engine.surfaces.compendium import (
    CONFIG_PATH as COMPENDIUM_CONFIG_PATH,
    build_compendium,
)
from psp.engine.surfaces.comp_party_panel import (
    CONFIG_PATH as COMP_PARTY_PANEL_CONFIG_PATH,
    build_comp_party_panel,
)
from psp.engine.surfaces.event_window import (
    CONFIG_PATH as EVENT_WINDOW_CONFIG_PATH,
    build_event_window,
)
from psp.engine.surfaces.dungeon_locations import (
    CONFIG_PATH as DUNGEON_LOCATION_CONFIG_PATH,
    build_dungeon_locations,
)
from psp.engine.surfaces.fmv_subtitles import (
    CONFIG_PATH as FMV_SUBTITLE_CONFIG_PATH,
    FMV_MANIFEST_PATH,
    build_fmv_subtitles,
)
from psp.engine.surfaces.item_runtime import (
    CONFIG_PATH as ITEM_RUNTIME_CONFIG_PATH,
    build_item_runtime,
)
from psp.engine.surfaces.map2d import (
    CONFIG_PATH as MAP2D_CONFIG_PATH,
    build_map2d,
)
from psp.engine.surfaces.name_entry import (
    CONFIG_PATH as NAME_ENTRY_CONFIG_PATH,
    build_name_entry,
)
from psp.engine.surfaces.savedata import (
    CONFIG_PATH as SAVEDATA_CONFIG_PATH,
    build_savedata,
)
from psp.engine.surfaces.title_help_ui import (
    CONFIG_PATH,
    TARGET,
    _configuration,
    build_title_help_ui,
)
from psp.font.util.metrics import CONFIG_PATH as METRIC_CONFIG_PATH
from psp.rom.util.catalog import (
    CATALOG_PATH,
    file_sha256,
    load_catalog,
    validate_source,
)
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import CONFIG_ASSET_PATH


ENGINE_ROOT = Path(__file__).resolve().parent
PSP_ROOT = ENGINE_ROOT.parent
METRICS_PATH = PSP_ROOT / "font" / "generated" / "game" / "title_help_metrics.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
BOOT_OUTPUT = GENERATED_ROOT / "BOOT.BIN"
EBOOT_OUTPUT = GENERATED_ROOT / "EBOOT.BIN"
MANIFEST_OUTPUT = GENERATED_ROOT / "psp.engine.json"
FONT_MANIFEST_PATH = (
    PSP_ROOT / "font" / "generated" / "game" / "psp.fonts.json"
)
TEXT_MANIFEST_PATH = PSP_ROOT / "text" / "generated" / "game" / "psp.text.json"
ENCODING_CODEC_PATH = PSP_ROOT / "text" / "util" / "event_packed.py"
CONFIG_ENGINE_SOURCES = (
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "config_menu.py",
    ENGINE_ROOT / "surfaces" / "config_menu_runtime.py",
)
BATTLE_CONSOLE_ENGINE_SOURCES = (
    BATTLE_CONSOLE_CONFIG_PATH,
    ENGINE_ROOT / "surfaces" / "battle_console.py",
)
BATTLE_NAMES_ENGINE_SOURCES = (
    BATTLE_NAMES_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "battle_names.py",
    ENGINE_ROOT / "surfaces" / "battle_names_runtime.py",
    PSP_ROOT / "text" / "config" / "event_dvlname.json",
    PSP_ROOT / "text" / "config" / "name_entry.json",
    PSP_ROOT / "text" / "util" / "event_dvlname.py",
    PSP_ROOT / "text" / "util" / "name_entry.py",
    PSP_ROOT.parent / "assets" / "text" / "demons.json",
    PSP_ROOT.parent / "assets" / "text" / "items.json",
    PSP_ROOT.parent / "assets" / "text" / "ui" / "profile_entry.json",
)
COMP_PARTY_PANEL_ENGINE_SOURCES = (
    COMP_PARTY_PANEL_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "comp_party_panel.py",
    ENGINE_ROOT / "surfaces" / "comp_party_panel_runtime.py",
    PSP_ROOT / "font" / "config" / "comp_party_ark10.json",
    PSP_ROOT / "font" / "util" / "comp_party_ark10.py",
    PSP_ROOT / "text" / "config" / "name_entry.json",
    PSP_ROOT.parent / "assets" / "text" / "characters.json",
    PSP_ROOT.parent / "assets" / "text" / "ui" / "profile_entry.json",
)
MAP2D_ENGINE_SOURCES = (
    MAP2D_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "map2d.py",
    ENGINE_ROOT / "surfaces" / "map2d_runtime.py",
    PSP_ROOT / "font" / "config" / "map2d.json",
    PSP_ROOT / "font" / "util" / "map2d.py",
    PSP_ROOT / "text" / "config" / "map2d.json",
    PSP_ROOT / "text" / "util" / "map2d.py",
    PSP_ROOT.parent / "assets" / "text" / "field" / "messages.json",
    PSP_ROOT.parent / "assets" / "text" / "locations.json",
    PSP_ROOT.parent / "assets" / "text" / "ui" / "map_2d.json",
)
FMV_SUBTITLE_ENGINE_SOURCES = (
    FMV_SUBTITLE_CONFIG_PATH,
    ENGINE_ROOT / "surfaces" / "fmv_subtitles.py",
)
COMMAND_HELP_ENGINE_SOURCES = (
    COMMAND_HELP_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "command_menu_help.py",
)
EVENT_WINDOW_ENGINE_SOURCES = (
    EVENT_WINDOW_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "event_window.py",
)
NAME_ENTRY_ENGINE_SOURCES = (
    NAME_ENTRY_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "name_entry.py",
    ENGINE_ROOT / "surfaces" / "name_entry_runtime.py",
    PSP_ROOT / "text" / "config" / "name_entry.json",
    PSP_ROOT / "text" / "util" / "event_packed.py",
    PSP_ROOT / "text" / "util" / "name_entry.py",
    PSP_ROOT.parent / "assets" / "text" / "ui" / "profile_entry.json",
)
SAVEDATA_ENGINE_SOURCES = (
    SAVEDATA_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "savedata.py",
    ENGINE_ROOT / "surfaces" / "savedata_runtime.py",
    PSP_ROOT / "text" / "config" / "savedata.json",
    PSP_ROOT / "text" / "util" / "event_packed.py",
    PSP_ROOT / "text" / "util" / "savedata.py",
    PSP_ROOT.parent / "assets" / "text" / "save_load.json",
    PSP_ROOT.parent / "assets" / "text" / "locations.json",
)
DUNGEON_LOCATION_ENGINE_SOURCES = (
    DUNGEON_LOCATION_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "dungeon_locations.py",
    ENGINE_ROOT / "surfaces" / "dungeon_locations_runtime.py",
    PSP_ROOT / "font" / "config" / "dungeon_locations_font16.json",
    PSP_ROOT / "font" / "util" / "dungeon_locations.py",
    PSP_ROOT / "text" / "config" / "savedata.json",
    PSP_ROOT.parent / "assets" / "text" / "locations.json",
)
COMPENDIUM_ENGINE_SOURCES = (
    COMPENDIUM_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "compendium.py",
    ENGINE_ROOT / "surfaces" / "compendium_prose_runtime.py",
    ENGINE_ROOT / "surfaces" / "compendium_name_runtime.py",
    PSP_ROOT / "text" / "config" / "compendium.json",
    PSP_ROOT / "text" / "config" / "event_dvlname.json",
    PSP_ROOT / "text" / "util" / "compendium.py",
    PSP_ROOT / "text" / "util" / "event_dvlname.py",
)
ITEM_RUNTIME_ENGINE_SOURCES = (
    ITEM_RUNTIME_CONFIG_PATH,
    ENGINE_ROOT / "core" / "emitter.py",
    ENGINE_ROOT / "core" / "layout.py",
    ENGINE_ROOT / "surfaces" / "item_runtime.py",
    ENGINE_ROOT / "surfaces" / "item_runtime_runtime.py",
    PSP_ROOT / "text" / "config" / "item_runtime.json",
    PSP_ROOT / "text" / "util" / "item_runtime.py",
    PSP_ROOT.parent / "assets" / "text" / "items_psp.json",
)
EBOOT_TRAILING_SIZE = 345


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metric_widths() -> bytes:
    config = _configuration()
    if not METRICS_PATH.is_file():
        raise ValueError(
            f"title-help metrics are missing: {METRICS_PATH}; "
            "run psp/font/repack.py title_help"
        )
    digest = file_sha256(METRICS_PATH)
    expected = config.inputs["title_help_metrics_sha256"]
    if digest != expected:
        raise ValueError(
            f"title-help metrics SHA-256 is {digest}; expected {expected}"
        )
    try:
        document = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid title-help metrics: {METRICS_PATH}") from error
    storage = document.get("storage_order") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("id") != "title_help_metrics"
        or not isinstance(storage, list)
        or len(storage) != 95
        or any(type(value) is not int or not 1 <= value <= 255 for value in storage)
    ):
        raise ValueError("title-help metrics have an invalid runtime width table")
    return bytes(storage)


def _source_entries() -> tuple[bytes, bytes, dict[str, object]]:
    try:
        disc = load_catalog()["game"]
        boot_contract = disc.entries["boot"]
        eboot_contract = disc.entries["eboot"]
    except KeyError as error:
        raise ValueError("PSP disc catalogue is missing game BOOT contracts") from error
    source_path = validate_source(disc, verify_hash=False)
    boot_extent, boot = read_iso9660_file(source_path, boot_contract.path)
    eboot_extent, eboot = read_iso9660_file(source_path, eboot_contract.path)
    for contract, extent, data in (
        (boot_contract, boot_extent, boot),
        (eboot_contract, eboot_extent, eboot),
    ):
        digest = _sha256(data)
        if extent.size != contract.size or digest != contract.sha256:
            raise ValueError(
                f"{contract.path} is not the configured stock PSP entry"
            )
    evidence = {
        "iso": disc.source_filename,
        "boot": {
            "path": boot_contract.path,
            "lba": boot_extent.lba,
            "size": len(boot),
            "sha256": _sha256(boot),
        },
        "eboot": {
            "path": eboot_contract.path,
            "lba": eboot_extent.lba,
            "size": len(eboot),
            "sha256": _sha256(eboot),
        },
    }
    return boot, eboot, evidence


def _source_regdata() -> bytes:
    try:
        disc = load_catalog()["game"]
        contract = disc.entries["regdata"]
    except KeyError as error:
        raise ValueError("PSP disc catalogue is missing the regdata contract") from error
    source_path = validate_source(disc, verify_hash=False)
    extent, data = read_iso9660_file(source_path, contract.path)
    if extent.size != contract.size or _sha256(data) != contract.sha256:
        raise ValueError(f"{contract.path} is not the configured stock PSP entry")
    return data


def _config_font_contract() -> dict[str, object]:
    if not FONT_MANIFEST_PATH.is_file():
        raise ValueError(
            f"PSP font manifest is missing: {FONT_MANIFEST_PATH}; "
            "run psp/font/repack.py all"
        )
    try:
        document = json.loads(FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP font manifest: {FONT_MANIFEST_PATH}") from error
    contract = document.get("config_menu") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
    ):
        raise ValueError("PSP font manifest has no CONFIG runtime contract")
    return contract


def _dungeon_location_font_contract() -> dict[str, object]:
    if not FONT_MANIFEST_PATH.is_file():
        raise ValueError(
            f"PSP font manifest is missing: {FONT_MANIFEST_PATH}; "
            "run psp/font/repack.py all"
        )
    try:
        document = json.loads(FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP font manifest: {FONT_MANIFEST_PATH}") from error
    contract = document.get("dungeon_locations") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
    ):
        raise ValueError("PSP font manifest has no dungeon-location contract")
    return contract


def _comp_party_ark10_contract() -> dict[str, object]:
    if not FONT_MANIFEST_PATH.is_file():
        raise ValueError(
            f"PSP font manifest is missing: {FONT_MANIFEST_PATH}; "
            "run psp/font/repack.py all"
        )
    try:
        document = json.loads(FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP font manifest: {FONT_MANIFEST_PATH}") from error
    contract = document.get("comp_party_ark10") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
    ):
        raise ValueError("PSP font manifest has no COMP Ark10 contract")
    return contract


def _map2d_font_contract() -> dict[str, object]:
    if not FONT_MANIFEST_PATH.is_file():
        raise ValueError(
            f"PSP font manifest is missing: {FONT_MANIFEST_PATH}; "
            "run psp/font/repack.py all"
        )
    try:
        document = json.loads(FONT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP font manifest: {FONT_MANIFEST_PATH}") from error
    contract = document.get("map2d") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.fonts"
        or not isinstance(contract, dict)
    ):
        raise ValueError("PSP font manifest has no MAP2D contract")
    return contract


def _battle_console_body_offset() -> int:
    if not TEXT_MANIFEST_PATH.is_file():
        raise ValueError(
            f"PSP text manifest is missing: {TEXT_MANIFEST_PATH}; "
            "run psp/text/repack.py all"
        )
    try:
        document = json.loads(TEXT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP text manifest: {TEXT_MANIFEST_PATH}") from error
    records = document.get("records") if isinstance(document, dict) else None
    battle_console = (
        records.get("battle_console") if isinstance(records, dict) else None
    )
    components = document.get("components") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.text"
        or not isinstance(components, list)
        or "battle_console.text" not in components
        or not isinstance(battle_console, dict)
        or set(battle_console)
        != {
            "translated",
            "preserved_empty",
            "body_offset",
            "body_size",
            "body_capacity",
            "free_bytes",
        }
        or battle_console.get("translated") != 313
        or battle_console.get("preserved_empty") != 45
        or battle_console.get("body_offset") != 0x400
        or battle_console.get("body_size") != 3_136
        or battle_console.get("body_capacity") != 4_058
        or battle_console.get("free_bytes") != 922
    ):
        raise ValueError("PSP text manifest has no valid battle-console contract")
    return 0x400


def _manifest(
    *,
    source: dict[str, object],
    boot: bytes,
    eboot: bytes,
    patches,
    runtime_used: int,
    runtime_capacity: int,
    compendium,
    item_runtime,
    name_entry,
    savedata,
    dungeon_locations,
    battle_names,
    comp_party_panel,
    map2d,
) -> bytes:
    document = {
        "version": 1,
        "surface": "psp.engine",
        "components": [
            "title_help.ui",
            "config_menu.ui",
            "command_menu_help.runtime",
            "event_window.runtime_foundation",
            "name_entry.runtime",
            "savedata.runtime",
            "maze.location_display",
            "demon_compendium.prose",
            "demon_compendium.names",
            "psp_active_items.runtime",
            "battle_console.runtime",
            "battle_party_panel.names",
            "battle_results.names",
            "comp_party_panel.names",
            "map_2d.runtime",
            "fmv_subtitles.runtime",
        ],
        "source": source,
        "inputs": {
            "disc_catalog_sha256": file_sha256(CATALOG_PATH),
            "font_metric_config_sha256": file_sha256(METRIC_CONFIG_PATH),
            "patch_config_sha256": file_sha256(CONFIG_PATH),
            "title_help_metrics_sha256": file_sha256(METRICS_PATH),
            "font_manifest_sha256": file_sha256(FONT_MANIFEST_PATH),
            "text_manifest_sha256": file_sha256(TEXT_MANIFEST_PATH),
            "encoding_codec_sha256": file_sha256(ENCODING_CODEC_PATH),
            "fmv_manifest_sha256": file_sha256(FMV_MANIFEST_PATH),
            "config_menu_asset_sha256": file_sha256(CONFIG_ASSET_PATH),
            "assembly": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in sorted(
                    {
                        source
                        for recipe in _configuration().patches[TARGET]
                        for source in recipe.replacement.sources
                    }
                )
            },
            "config_menu_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in CONFIG_ENGINE_SOURCES
            },
            "command_help_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in COMMAND_HELP_ENGINE_SOURCES
            },
            "event_window_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in EVENT_WINDOW_ENGINE_SOURCES
            },
            "name_entry_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in NAME_ENTRY_ENGINE_SOURCES
            },
            "savedata_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in SAVEDATA_ENGINE_SOURCES
            },
            "dungeon_location_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in DUNGEON_LOCATION_ENGINE_SOURCES
            },
            "compendium_sources": {
                path.relative_to(PSP_ROOT).as_posix(): file_sha256(path)
                for path in COMPENDIUM_ENGINE_SOURCES
            },
            "item_runtime_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in ITEM_RUNTIME_ENGINE_SOURCES
            },
            "battle_console_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in BATTLE_CONSOLE_ENGINE_SOURCES
            },
            "battle_name_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in BATTLE_NAMES_ENGINE_SOURCES
            },
            "comp_party_panel_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in COMP_PARTY_PANEL_ENGINE_SOURCES
            },
            "map2d_sources": {
                path.relative_to(PSP_ROOT.parent).as_posix(): file_sha256(path)
                for path in MAP2D_ENGINE_SOURCES
            },
            "fmv_subtitle_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in FMV_SUBTITLE_ENGINE_SOURCES
            },
        },
        "runtime": {"used": runtime_used, "capacity": runtime_capacity},
        "compendium": {
            "table_rows": 319,
            "live_profiles": len(compendium.text.profiles),
            "translated_fields": compendium.text.translated_field_count,
            "unique_strings": compendium.text.unique_string_count,
            "text_used": compendium.text.used_size,
            "text_capacity": len(compendium.text.text_arena),
            "text_sha256": _sha256(compendium.text.text_arena),
            "pointer_table_sha256": _sha256(compendium.text.pointer_table),
            "dvlname_table_sha256": _sha256(compendium.names.dvlname_table),
        },
        "active_items": {
            "game_ids": [record.game_id for record in item_runtime.text.records],
            "names": [record.name for record in item_runtime.text.records],
            "regdata_member_index": 4,
            "regdata_bytes_unchanged": True,
            "source_member_sha256": item_runtime.text.source_member_sha256,
            "runtime_data_sha256": _sha256(item_runtime.runtime.data_blob),
        },
        "name_entry": {
            "fields": [field.key for field in name_entry.text.fields],
            "field_size": 8,
            "tabs": [grid.key for grid in name_entry.text.grids],
            "default_city": name_entry.text.default_city,
            "default_ward": name_entry.text.default_ward,
            "write_count": len(name_entry.patches),
        },
        "savedata": {
            "language": "English",
            "game_title": savedata.text.game_title,
            "slot_title": savedata.text.slot_title,
            "detail_template": savedata.text.detail_template,
            "special_locations": [savedata.text.home, savedata.text.office],
            "dungeon_locations": list(savedata.text.locations),
            "location_record_count": len(savedata.runtime.location_ids),
            "write_count": len(savedata.patches),
        },
        "dungeon_locations": {
            "location_count": 24,
            "physical_record_count": 144,
            "name_sequence_size": len(dungeon_locations.runtime.name_sequence),
            "write_count": len(dungeon_locations.patches),
        },
        "battle_names": {
            "mysterious_man": battle_names.mysterious_man,
            "result_labels": list(battle_names.result_labels),
            "full_dvl_names": True,
            "write_count": len(battle_names.patches),
        },
        "comp_party_panel": {
            "character_names": list(comp_party_panel.character_names),
            "shared_dvlname_table": True,
            "shared_eve_handle_owner": True,
            "write_count": len(comp_party_panel.patches),
        },
        "map2d": {
            "locations": list(map2d.locations),
            "write_count": len(map2d.patches),
            "runtime_used": map2d.runtime_used_size,
            "runtime_capacity": map2d.runtime_capacity,
        },
        "patches": [
            {
                "group": patch.group,
                "name": patch.name,
                "address": f"0x{patch.address:08x}",
                "size": len(patch.replacement),
                "replacement_sha256": _sha256(patch.replacement),
            }
            for patch in patches
        ],
        "outputs": {
            "BOOT.BIN": {"size": len(boot), "sha256": _sha256(boot)},
            "EBOOT.BIN": {"size": len(eboot), "sha256": _sha256(eboot)},
        },
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publish(path: Path, data: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"PSP engine output is missing or stale: {path}")
        print(f"verified {path.relative_to(ENGINE_ROOT).as_posix()}")
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
    print(f"generated {path.relative_to(ENGINE_ROOT).as_posix()}")


def build_engine(*, check: bool) -> None:
    widths = _metric_widths()
    stock_boot, stock_eboot, source = _source_entries()
    stock_regdata = _source_regdata()
    title = build_title_help_ui(stock_boot, widths)
    config = build_config_menu(stock_boot, title.data, _config_font_contract())
    command_help = build_command_menu_help(stock_boot, config.data)
    event_window = build_event_window(
        stock_boot,
        command_help.data,
        load_eve_widths(),
    )
    name_entry = build_name_entry(stock_boot, event_window.data)
    savedata = build_savedata(stock_boot, name_entry.data)
    dungeon_locations = build_dungeon_locations(
        stock_boot,
        savedata.data,
        _dungeon_location_font_contract(),
    )
    battle_console = build_battle_console(
        stock_boot,
        dungeon_locations.data,
        _battle_console_body_offset(),
    )
    compendium = build_compendium(
        stock_boot,
        battle_console.data,
        load_eve_widths(),
    )
    battle_names = build_battle_names(
        stock_boot,
        compendium.data,
        _config_font_contract(),
        compendium.names.dvlname_table,
    )
    comp_party_panel = build_comp_party_panel(
        stock_boot,
        battle_names.data,
        _comp_party_ark10_contract(),
        compendium.names.dvlname_table,
        battle_names.mysterious_man,
    )
    item_runtime = build_item_runtime(
        stock_boot,
        comp_party_panel.data,
        stock_regdata,
        load_eve_widths(),
    )
    map2d = build_map2d(
        stock_boot,
        item_runtime.data,
        _map2d_font_contract(),
    )
    fmv = build_fmv_subtitles(stock_boot, map2d.data)
    eboot = fmv.data + bytes(EBOOT_TRAILING_SIZE)
    if len(eboot) != len(stock_eboot):
        raise ValueError("PSP EBOOT replacement changed its ISO extent size")
    manifest = _manifest(
        source=source,
        boot=fmv.data,
        eboot=eboot,
        patches=(
            *title.patches,
            *config.patches,
            *command_help.patches,
            *event_window.patches,
            *name_entry.patches,
            *savedata.patches,
            *dungeon_locations.patches,
            *battle_console.patches,
            *compendium.patches,
            *battle_names.patches,
            *comp_party_panel.patches,
            *item_runtime.patches,
            *map2d.patches,
            *fmv.patches,
        ),
        runtime_used=(
            title.runtime_used_size
            + config.runtime_used_size
            + command_help.runtime_used_size
            + event_window.runtime_used_size
            + name_entry.runtime_used_size
            + savedata.runtime_used_size
            + dungeon_locations.runtime_used_size
            + compendium.runtime_used_size
            + battle_names.runtime_used_size
            + comp_party_panel.runtime_used_size
            + item_runtime.runtime_used_size
            + map2d.runtime_used_size
            + fmv.runtime_used_size
        ),
        runtime_capacity=(
            title.runtime_capacity
            + config.runtime_used_size
            + command_help.runtime_capacity
            + event_window.runtime_capacity
            + name_entry.runtime_capacity
            + savedata.runtime_capacity
            + dungeon_locations.runtime_capacity
            + compendium.runtime_capacity
            + battle_names.runtime_capacity
            + comp_party_panel.runtime_capacity
            + item_runtime.runtime_capacity
            + map2d.runtime_capacity
            + fmv.runtime_capacity
        ),
        compendium=compendium,
        item_runtime=item_runtime,
        name_entry=name_entry,
        savedata=savedata,
        dungeon_locations=dungeon_locations,
        battle_names=battle_names,
        comp_party_panel=comp_party_panel,
        map2d=map2d,
    )
    for path, data in (
        (BOOT_OUTPUT, fmv.data),
        (EBOOT_OUTPUT, eboot),
        (MANIFEST_OUTPUT, manifest),
    ):
        _publish(path, data, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surface", choices=("all",))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build_engine(check=arguments.check)
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
