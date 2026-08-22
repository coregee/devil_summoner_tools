"""Build or verify the configured PSP ISO from checked generated extents."""

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

from psp.rom.util.catalog import file_sha256, load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file
from psp.rom.util.publication import (
    IsoReplacement,
    replaced_iso_sha256,
    verify_replaced_iso,
    write_replaced_iso,
)


PSP_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PSP_ROOT / "engine"
ENGINE_GENERATED = ENGINE_ROOT / "generated" / "game"
ENGINE_MANIFEST = ENGINE_GENERATED / "psp.engine.json"
FONT_GENERATED = PSP_ROOT / "font" / "generated" / "game"
FONT_MANIFEST = FONT_GENERATED / "psp.fonts.json"
TEXT_GENERATED = PSP_ROOT / "text" / "generated" / "game"
TEXT_MANIFEST = TEXT_GENERATED / "psp.text.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _engine_outputs() -> dict[str, dict[str, object]]:
    if not ENGINE_MANIFEST.is_file():
        raise ValueError(f"PSP engine manifest is missing: {ENGINE_MANIFEST}")
    try:
        document = json.loads(ENGINE_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP engine manifest: {ENGINE_MANIFEST}") from error
    outputs = document.get("outputs") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != "psp.engine"
        or not isinstance(outputs, dict)
        or set(outputs) != {"BOOT.BIN", "EBOOT.BIN"}
        or any(
            not isinstance(row, dict)
            or set(row) != {"size", "sha256"}
            or type(row["size"]) is not int
            or row["size"] <= 0
            or not isinstance(row["sha256"], str)
            or len(row["sha256"]) != 64
            for row in outputs.values()
        )
    ):
        raise ValueError("PSP engine manifest has an invalid output contract")
    return outputs


def _resource_output(
    manifest_path: Path,
    *,
    surface: str,
    output_path: Path,
) -> bytes:
    if not manifest_path.is_file():
        raise ValueError(f"PSP component manifest is missing: {manifest_path}")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP component manifest: {manifest_path}") from error
    output = document.get("output") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != surface
        or not isinstance(output, dict)
        or set(output) != {"filename", "size", "sha256"}
        or output["filename"] != output_path.name
        or type(output["size"]) is not int
        or output["size"] <= 0
        or not isinstance(output["sha256"], str)
        or len(output["sha256"]) != 64
    ):
        raise ValueError(
            f"PSP component manifest has an invalid output: {manifest_path}"
        )
    if not output_path.is_file():
        raise ValueError(f"PSP component output is missing: {output_path}")
    data = output_path.read_bytes()
    if len(data) != output["size"] or _sha256(data) != output["sha256"]:
        raise ValueError(f"PSP component output violates its manifest: {output_path}")
    return data


def _replacements(source_path: Path, disc) -> tuple[IsoReplacement, ...]:
    manifest_outputs = _engine_outputs()
    outputs = {
        "boot": ENGINE_GENERATED / "BOOT.BIN",
        "eboot": ENGINE_GENERATED / "EBOOT.BIN",
    }
    rows = []
    for entry_id, output_path in outputs.items():
        try:
            contract = disc.entries[entry_id]
        except KeyError as error:
            raise ValueError(f"PSP disc has no {entry_id} entry contract") from error
        if not output_path.is_file():
            raise ValueError(f"PSP engine output is missing: {output_path}")
        replacement = output_path.read_bytes()
        output_contract = manifest_outputs[output_path.name]
        if (
            len(replacement) != output_contract["size"]
            or _sha256(replacement) != output_contract["sha256"]
        ):
            raise ValueError(f"PSP engine output violates its manifest: {output_path}")
        extent, source = read_iso9660_file(source_path, contract.path)
        if (
            extent.size != contract.size
            or len(source) != contract.size
            or _sha256(source) != contract.sha256
        ):
            raise ValueError(f"{contract.path} source contract changed")
        rows.append(IsoReplacement(extent, source, replacement))
    for entry_id, manifest_path, surface, output_path in (
        (
            "datapack",
            FONT_MANIFEST,
            "psp.fonts",
            FONT_GENERATED / "datapack.bin",
        ),
        (
            "regdata",
            TEXT_MANIFEST,
            "psp.text",
            TEXT_GENERATED / "regdata.bin",
        ),
    ):
        try:
            contract = disc.entries[entry_id]
        except KeyError as error:
            raise ValueError(f"PSP disc has no {entry_id} entry contract") from error
        replacement = _resource_output(
            manifest_path,
            surface=surface,
            output_path=output_path,
        )
        extent, source = read_iso9660_file(source_path, contract.path)
        if (
            extent.size != contract.size
            or len(source) != contract.size
            or _sha256(source) != contract.sha256
            or len(replacement) != contract.size
        ):
            raise ValueError(f"{contract.path} source or replacement contract changed")
        rows.append(IsoReplacement(extent, source, replacement))
    return tuple(rows)


def _manifest_bytes(disc, digest: str, replacements) -> bytes:
    document = {
        "version": 1,
        "disc": disc.id,
        "source": {
            "filename": disc.source_filename,
            "size": disc.source_size,
            "sha256": disc.source_sha256,
        },
        "output": {
            "filename": disc.output_filename,
            "size": disc.source_size,
            "sha256": digest,
        },
        "component_manifests": {
            "engine": file_sha256(ENGINE_MANIFEST),
            "font": file_sha256(FONT_MANIFEST),
            "text": file_sha256(TEXT_MANIFEST),
        },
        "replacements": [
            {
                "path": row.extent.path,
                "lba": row.extent.lba,
                "size": row.extent.size,
                "source_sha256": _sha256(row.source_data),
                "replacement_sha256": _sha256(row.replacement_data),
            }
            for row in replacements
        ],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publish_manifest(path: Path, data: bytes) -> None:
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


def build_disc(*, check: bool) -> None:
    try:
        disc = load_catalog()["game"]
    except KeyError as error:
        raise ValueError("PSP disc catalogue has no game disc") from error
    source_path = validate_source(disc, verify_hash=True)
    replacements = _replacements(source_path, disc)
    digest = replaced_iso_sha256(
        source_path,
        image_size=disc.source_size,
        replacements=replacements,
    )
    manifest = _manifest_bytes(disc, digest, replacements)
    if check:
        verify_replaced_iso(
            source_path,
            disc.output_path,
            image_size=disc.source_size,
            replacements=replacements,
            expected_sha256=digest,
        )
        if (
            not disc.manifest_path.is_file()
            or disc.manifest_path.read_bytes() != manifest
        ):
            raise ValueError(
                f"PSP build manifest is missing or stale: {disc.manifest_path}"
            )
        print(f"verified {disc.output_path}")
        print(f"verified {disc.manifest_path}")
        return
    write_replaced_iso(
        source_path,
        disc.output_path,
        image_size=disc.source_size,
        replacements=replacements,
        expected_sha256=digest,
    )
    _publish_manifest(disc.manifest_path, manifest)
    print(f"built {disc.output_path}")
    print(f"manifest {disc.manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("game", "all"), nargs="?", default="all")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        build_disc(check=arguments.check)
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
