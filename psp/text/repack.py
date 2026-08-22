"""Build or verify generated PSP authored-text resources."""

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

from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import TITLE_ASSET_PATH
from psp.text.util.assets import CONFIG_ASSET_PATH
from psp.text.util.config_menu import (
    CONFIG_PATH as CONFIG_MENU_PATH,
    build_config_text,
)
from psp.archive.pack import PspPack
from psp.text.util.title_help import CONFIG_PATH, build_title_help, load_config


TEXT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = TEXT_ROOT / "generated" / "game"
OUTPUT_PATH = OUTPUT_ROOT / "regdata.bin"
MANIFEST_PATH = OUTPUT_ROOT / "psp.text.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _publish(path: Path, data: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError(f"generated PSP text output is missing or stale: {path}")
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


def build(*, check: bool) -> None:
    disc = load_catalog()["game"]
    source_iso = validate_source(disc, verify_hash=True)
    config = load_config()
    extent, source = read_iso9660_file(source_iso, config.iso_path)
    contract = disc.entries.get("regdata")
    if (
        contract is None
        or extent.size != contract.size
        or len(source) != contract.size
        or _sha(source) != contract.sha256
    ):
        raise ValueError("PSP regdata disc contract changed")
    title_result = build_title_help(source, config)
    config_result = build_config_text(source)
    archive = PspPack.parse(source)
    combined = archive.rebuild(
        {14: config_result.member, config.member_index: title_result.member}
    )
    if _sha(combined) != (
        "a642bbea6b2d3a087261bd2aaf6ac0687eba2eb272681344b3a0cc1946688e4b"
    ):
        raise ValueError("combined PSP CONFIG/title-help regdata contract changed")
    manifest = {
        "version": 1,
        "surface": "psp.text",
        "components": ["title_help.text", "config_menu.text"],
        "inputs": {
            "asset_sha256": _sha(TITLE_ASSET_PATH.read_bytes()),
            "config_asset_sha256": _sha(CONFIG_ASSET_PATH.read_bytes()),
            "config_sha256": _sha(CONFIG_PATH.read_bytes()),
            "config_menu_binding_sha256": _sha(CONFIG_MENU_PATH.read_bytes()),
            "source_sha256": _sha(source),
        },
        "output": {
            "filename": OUTPUT_PATH.name,
            "size": len(combined),
            "sha256": _sha(combined),
        },
        "member": {
            "indices": [14, config.member_index],
            "sha256": {
                "14": _sha(config_result.member),
                str(config.member_index): _sha(title_result.member),
            },
        },
        "records": {
            "title_help": list(title_result.translations),
            "config_help": list(config_result.translations),
        },
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _publish(OUTPUT_PATH, combined, check=check)
    _publish(MANIFEST_PATH, manifest_bytes, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target", choices=("all",), nargs="?", default="all"
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
