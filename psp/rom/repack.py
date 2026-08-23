"""Build or verify the configured PSP ISO from checked generated extents."""

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

from psp.archive.pack import PspPack
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
FMV_MANIFEST = PSP_ROOT / "fmv" / "generated" / "game" / "psp.fmv.json"
TEXT_GENERATED = PSP_ROOT / "text" / "generated" / "game"
TEXT_MANIFEST = TEXT_GENERATED / "psp.text.json"
EVENT_MANIFEST = TEXT_GENERATED / "psp.events.json"
VISUAL_GENERATED = PSP_ROOT / "visual" / "generated" / "game"
VISUAL_MANIFEST = VISUAL_GENERATED / "psp.visual.json"


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
    output_key: str = "output",
) -> bytes:
    if not manifest_path.is_file():
        raise ValueError(f"PSP component manifest is missing: {manifest_path}")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP component manifest: {manifest_path}") from error
    container = document.get(output_key) if isinstance(document, dict) else None
    output = (
        container.get(output_path.name)
        if output_key == "outputs" and isinstance(container, dict)
        else container
    )
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("surface") != surface
        or not isinstance(output, dict)
        or set(output)
        != (
            {"size", "sha256"}
            if output_key == "outputs"
            else {"filename", "size", "sha256"}
        )
        or (output_key != "outputs" and output["filename"] != output_path.name)
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
            output_key="outputs" if surface == "psp.fonts" else "output",
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
    contract = disc.entries.get("eve_files")
    if contract is None:
        raise ValueError("PSP disc has no eve_files entry contract")
    eve_output = TEXT_GENERATED / "eve_files.bin"
    replacement = _resource_output(
        EVENT_MANIFEST,
        surface="psp.event_text",
        output_path=eve_output,
        output_key="outputs",
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
    rows.extend(_visual_replacements(source_path, disc))
    return tuple(rows)


def _visual_replacements(source_path: Path, disc) -> tuple[IsoReplacement, ...]:
    if not VISUAL_MANIFEST.is_file():
        raise ValueError(f"PSP visual manifest is missing: {VISUAL_MANIFEST}")
    try:
        document = json.loads(VISUAL_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PSP visual manifest: {VISUAL_MANIFEST}") from error
    source_contract = document.get("source") if isinstance(document, dict) else None
    outputs = document.get("outputs") if isinstance(document, dict) else None
    if (
        document.get("version") != 1
        or document.get("surface") != "psp.visual"
        or not isinstance(source_contract, dict)
        or source_contract
        != {
            "filename": disc.source_filename,
            "size": disc.source_size,
            "sha256": disc.source_sha256,
        }
        or not isinstance(outputs, dict)
        or not outputs
    ):
        raise ValueError("PSP visual manifest has an invalid contract")

    by_path: dict[str, list[tuple[int, bytes, str]]] = {}
    for key, row in outputs.items():
        if (
            not isinstance(key, str)
            or not isinstance(row, dict)
            or not isinstance(row.get("filename"), str)
            or not isinstance(row.get("targets"), list)
            or not isinstance(row.get("source_sha256"), str)
        ):
            raise ValueError("PSP visual manifest has a malformed output")
        relative = PurePosixPath(row["filename"])
        if relative.is_absolute() or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise ValueError(f"PSP visual output {key} has an unsafe filename")
        output_path = VISUAL_GENERATED.joinpath(*relative.parts)
        if not output_path.is_file():
            raise ValueError(f"PSP visual output is missing: {output_path}")
        replacement = output_path.read_bytes()
        if len(replacement) != row.get("size") or _sha256(replacement) != row.get(
            "sha256"
        ):
            raise ValueError(f"PSP visual output violates its manifest: {output_path}")
        for target in row["targets"]:
            if (
                not isinstance(target, dict)
                or set(target) != {"iso_path", "member_index"}
                or not isinstance(target["iso_path"], str)
                or type(target["member_index"]) is not int
            ):
                raise ValueError(f"PSP visual output {key} has an invalid target")
            by_path.setdefault(target["iso_path"], []).append(
                (target["member_index"], replacement, row["source_sha256"])
            )

    result = []
    for iso_path, member_rows in sorted(by_path.items()):
        extent, source = read_iso9660_file(source_path, iso_path)
        pack = PspPack.parse(source)
        replacements = {}
        for index, replacement, source_sha256 in member_rows:
            if index in replacements or not 0 <= index < len(pack.members):
                raise ValueError(f"{iso_path}: invalid or duplicate visual member")
            member = pack.members[index].data
            if _sha256(member) != source_sha256 or len(member) != len(replacement):
                raise ValueError(f"{iso_path} member {index}: source contract changed")
            replacements[index] = replacement
        rebuilt = pack.rebuild(replacements)
        if len(rebuilt) != len(source):
            raise ValueError(f"{iso_path}: visual rebuild changed fixed pack size")
        result.append(IsoReplacement(extent, source, rebuilt))
    return tuple(result)


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
            "fmv": file_sha256(FMV_MANIFEST),
            "font": file_sha256(FONT_MANIFEST),
            "text": file_sha256(TEXT_MANIFEST),
            "event_text": file_sha256(EVENT_MANIFEST),
            "visual": file_sha256(VISUAL_MANIFEST),
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
