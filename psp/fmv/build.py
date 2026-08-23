"""Build or verify the checked PSP START2 runtime-subtitle manifest."""

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

from psp.fmv.util.subtitles import (
    CONFIG_PATH,
    FONT_MANIFEST_PATH,
    compile_runtime_cues,
    load_authored_cues,
    load_config,
    load_font_rows,
    validate_pmf,
)
from psp.rom.util.catalog import (
    CATALOG_PATH,
    file_sha256,
    load_catalog,
    validate_source,
)
from psp.rom.util.iso9660 import read_iso9660_file


FMV_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = FMV_ROOT / "generated" / "game" / "psp.fmv.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest() -> bytes:
    config = load_config()
    authored = load_authored_cues(config)
    font_rows = load_font_rows()
    cues = compile_runtime_cues(authored, font_rows, config)
    disc = load_catalog()["game"]
    try:
        contract = disc.entries[config.disc_entry]
    except KeyError as error:
        raise ValueError("PSP disc catalogue has no START2 PMF contract") from error
    source_path = validate_source(disc, verify_hash=False)
    extent, pmf = read_iso9660_file(source_path, contract.path)
    extent_offset = extent.offset
    validate_pmf(
        pmf,
        extent_offset=extent_offset,
        size=contract.size,
        sha256=contract.sha256,
        config=config,
    )
    cue_rows = [
        {
            "start_frame": cue.start_frame,
            "end_frame_exclusive": cue.end_frame_exclusive,
            "glyphs": [
                {"x": glyph.x, "y": glyph.y, "code": glyph.code}
                for glyph in cue.glyphs
            ],
        }
        for cue in cues
    ]
    compiled_data = json.dumps(
        cue_rows,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    document = {
        "version": 1,
        "surface": "psp.fmv",
        "components": ["start2_news.runtime_overlay"],
        "inputs": {
            "asset_sha256": file_sha256(config.asset_path),
            "config_sha256": file_sha256(CONFIG_PATH),
            "disc_catalog_sha256": file_sha256(CATALOG_PATH),
            "font_manifest_sha256": file_sha256(FONT_MANIFEST_PATH),
        },
        "movie": {
            "path": contract.path,
            "extent_offset": extent_offset,
            "size": len(pmf),
            "sha256": _sha(pmf),
            "unchanged": True,
        },
        "runtime": {
            "cue_count": len(cues),
            "visible_glyph_count": sum(len(cue.glyphs) for cue in cues),
            "maximum_cue_glyph_count": max(len(cue.glyphs) for cue in cues),
            "compiled_sha256": _sha(compiled_data),
            "cues": cue_rows,
        },
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publish(data: bytes, *, check: bool) -> None:
    if check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_bytes() != data:
            raise ValueError(f"PSP FMV output is missing or stale: {OUTPUT_PATH}")
        print(f"verified {OUTPUT_PATH.relative_to(FMV_ROOT).as_posix()}")
        return
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=OUTPUT_PATH.parent,
        prefix=f".{OUTPUT_PATH.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, OUTPUT_PATH)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"generated {OUTPUT_PATH.relative_to(FMV_ROOT).as_posix()}")


def build_fmv(*, check: bool) -> None:
    _publish(_manifest(), check=check)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("all",), nargs="?", default="all")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build_fmv(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
