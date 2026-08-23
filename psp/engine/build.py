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
from psp.engine.surfaces.config_menu import build_config_menu
from psp.engine.surfaces.command_menu_help import (
    CONFIG_PATH as COMMAND_HELP_CONFIG_PATH,
    build_command_menu_help,
    load_eve_widths,
)
from psp.engine.surfaces.event_window import (
    CONFIG_PATH as EVENT_WINDOW_CONFIG_PATH,
    build_event_window,
)
from psp.engine.surfaces.fmv_subtitles import (
    CONFIG_PATH as FMV_SUBTITLE_CONFIG_PATH,
    FMV_MANIFEST_PATH,
    build_fmv_subtitles,
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
) -> bytes:
    document = {
        "version": 1,
        "surface": "psp.engine",
        "components": [
            "title_help.ui",
            "config_menu.ui",
            "command_menu_help.runtime",
            "event_window.runtime_foundation",
            "battle_console.runtime",
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
            "battle_console_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in BATTLE_CONSOLE_ENGINE_SOURCES
            },
            "fmv_subtitle_sources": {
                path.relative_to(ENGINE_ROOT).as_posix(): file_sha256(path)
                for path in FMV_SUBTITLE_ENGINE_SOURCES
            },
        },
        "runtime": {"used": runtime_used, "capacity": runtime_capacity},
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
    title = build_title_help_ui(stock_boot, widths)
    config = build_config_menu(stock_boot, title.data, _config_font_contract())
    command_help = build_command_menu_help(stock_boot, config.data)
    event_window = build_event_window(
        stock_boot,
        command_help.data,
        load_eve_widths(),
    )
    battle_console = build_battle_console(
        stock_boot,
        event_window.data,
        _battle_console_body_offset(),
    )
    fmv = build_fmv_subtitles(stock_boot, battle_console.data)
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
            *battle_console.patches,
            *fmv.patches,
        ),
        runtime_used=(
            title.runtime_used_size
            + config.runtime_used_size
            + command_help.runtime_used_size
            + event_window.runtime_used_size
            + fmv.runtime_used_size
        ),
        runtime_capacity=(
            title.runtime_capacity
            + config.runtime_used_size
            + command_help.runtime_capacity
            + event_window.runtime_capacity
            + fmv.runtime_capacity
        ),
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
