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
from psp.font.util.title_help import (
    CONFIG_PATH as FONT16_CONFIG_PATH,
    build_title_help_font16,
    load_config as load_font16_config,
)
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.text.util.assets import TITLE_ASSET_PATH


FONT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = FONT_ROOT / "generated" / "game" / "title_help_metrics.json"
DATAPACK_PATH = FONT_ROOT / "generated" / "game" / "datapack.bin"
MANIFEST_PATH = FONT_ROOT / "generated" / "game" / "title_help_font16.json"


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


def build_title_help(*, check: bool) -> None:
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
    result = build_title_help_font16(source, config)
    manifest = {
        "version": 1,
        "surface": "title_help.font16",
        "inputs": {
            "asset_sha256": _sha(TITLE_ASSET_PATH.read_bytes()),
            "config_sha256": _sha(FONT16_CONFIG_PATH.read_bytes()),
            "metrics_sha256": _sha(metrics_data),
            "source_sha256": _sha(source),
        },
        "output": {
            "filename": DATAPACK_PATH.name,
            "size": len(result.data),
            "sha256": _sha(result.data),
        },
        "member": {
            "index": config.member_index,
            "size": len(result.member),
            "sha256": _sha(result.member),
        },
        "changed_byte_count": result.changed_byte_count,
        "changed_codes": [f"0x{code:04x}" for code in result.changed_codes],
        "advances": dict(result.advances),
    }
    manifest_data = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    for path, data in (
        (OUTPUT_PATH, metrics_data),
        (DATAPACK_PATH, result.data),
        (MANIFEST_PATH, manifest_data),
    ):
        publish(path, data, check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        choices=("title_help", "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build_title_help(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
