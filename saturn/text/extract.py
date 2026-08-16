"""Extract the complete Saturn text inventory into deterministic corpus files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

TEXT_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = TEXT_ROOT.parent
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from util.config import load_config  # noqa: E402
from util.containers import Region, extract_source, merge_regions  # noqa: E402
from util.sources import SourceManifest, load_manifest, manifest_path  # noqa: E402
from util.tokens import format_tokens, parse_tokens  # noqa: E402

ROM_ROOT = SATURN_ROOT / "rom"
CORPUS_ROOT = TEXT_ROOT / "corpus"
DISCS_PATH = ROM_ROOT / "discs.json"
_RECORD_FIELDS = {
    "id",
    "source_encoding",
    "output_encoding",
    "reference",
    "translation",
    "note",
}


@dataclass(frozen=True, slots=True)
class CorpusState:
    translation: str
    note: str


@dataclass(frozen=True, slots=True)
class ExtractionBatch:
    rendered: dict[PurePosixPath, bytes]
    source_count: int
    record_count: int
    composed_files: tuple[PurePosixPath, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _canonical_tokens(value: str, context: str) -> None:
    try:
        tokens = parse_tokens(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context}: {error}") from error
    if format_tokens(tokens) != value:
        raise ValueError(f"{context} is not in canonical token form")


def _load_existing(
    corpus_root: Path,
) -> tuple[dict[str, CorpusState], set[PurePosixPath]]:
    existing: dict[str, CorpusState] = {}
    paths: set[PurePosixPath] = set()
    if not corpus_root.exists():
        return existing, paths
    for path in sorted(
        candidate for candidate in corpus_root.rglob("*") if candidate.is_file()
    ):
        relative = PurePosixPath(path.relative_to(corpus_root).as_posix())
        paths.add(relative)
        if path.suffix != ".json":
            continue
        try:
            rows = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}: invalid JSON: {error.msg}") from error
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        if not isinstance(rows, list):
            raise ValueError(f"{path}: corpus files must contain a JSON array")
        for index, row in enumerate(rows):
            context = f"{path}: row {index}"
            if not isinstance(row, dict) or set(row) != _RECORD_FIELDS:
                raise ValueError(
                    f"{context} must contain exactly {sorted(_RECORD_FIELDS)}"
                )
            if any(not isinstance(row[field], str) for field in _RECORD_FIELDS):
                raise ValueError(f"{context}: every corpus field must be text")
            record_id = row["id"]
            if not record_id or record_id in existing:
                raise ValueError(
                    f"{context}: duplicate or empty record id {record_id!r}"
                )
            if row["output_encoding"]:
                raise ValueError(
                    f"{context}.output_encoding must remain blank until repacking"
                )
            _canonical_tokens(row["reference"], f"{context}.reference")
            _canonical_tokens(row["translation"], f"{context}.translation")
            existing[record_id] = CorpusState(row["translation"], row["note"])
    return existing, paths


def _disc_track_sha256(disc: str) -> str:
    try:
        document = json.loads(DISCS_PATH.read_text(encoding="utf-8"))
        tracks = document["discs"][disc]["tracks"]
        track = next(row for row in tracks if row["number"] == 1)
        digest = track["sha256"]
    except (
        FileNotFoundError,
        KeyError,
        StopIteration,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            f"cannot resolve {disc!r} Track 1 identity from {DISCS_PATH}"
        ) from error
    if not isinstance(digest, str):
        raise ValueError(f"{DISCS_PATH}: Track 1 SHA-256 is invalid")
    return digest


def _read_sources(manifest: SourceManifest, extracted_root: Path) -> dict[str, bytes]:
    blobs: dict[str, bytes] = {}
    for name, spec in manifest.files.items():
        path = extracted_root.joinpath(*spec.path.parts)
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise ValueError(f"missing extracted source file: {path}") from error
        if len(data) != spec.size:
            raise ValueError(f"{path}: size is {len(data)}, expected {spec.size}")
        blobs[name] = data
    return blobs


def _read_stock_sources(manifest: SourceManifest) -> dict[str, bytes]:
    try:
        disc_spec = load_catalog()[manifest.disc]
    except KeyError as error:
        raise ValueError(f"source-disc catalog has no {manifest.disc!r} disc") from error
    validated = validate_source(disc_spec)
    by_path = read_source_files(
        validated,
        tuple(spec.path.as_posix() for spec in manifest.files.values()),
    )
    return {
        name: by_path[spec.path.as_posix()]
        for name, spec in manifest.files.items()
    }


def _owned_digest(data: bytes, regions: tuple[Region, ...]) -> str:
    digest = hashlib.sha256()
    for region in regions:
        digest.update(region.start.to_bytes(8, "big"))
        digest.update((region.end - region.start).to_bytes(8, "big"))
        digest.update(data[region.start : region.end])
    return digest.hexdigest()


def _verify_sources(
    manifest: SourceManifest,
    blobs: dict[str, bytes],
    regions: tuple[Region, ...],
) -> tuple[PurePosixPath, ...]:
    by_file: dict[str, list[Region]] = {name: [] for name in manifest.files}
    for region in regions:
        if region.file not in by_file:
            raise ValueError(f"owned region references undeclared file {region.file!r}")
        by_file[region.file].append(region)
    unused = [name for name, owned in by_file.items() if not owned]
    if unused:
        raise ValueError(f"source manifest contains unused files: {', '.join(unused)}")

    composed: list[PurePosixPath] = []
    for name, spec in manifest.files.items():
        data = blobs[name]
        merged = merge_regions(by_file[name])
        if merged[-1].end > len(data):
            raise ValueError(f"{spec.path}: owned text region exceeds the file")
        full_digest = hashlib.sha256(data).hexdigest()
        if spec.owned_sha256 is not None:
            actual_owned = _owned_digest(data, merged)
            if actual_owned != spec.owned_sha256:
                raise ValueError(
                    f"{spec.path}: owned text SHA-256 is {actual_owned}, "
                    f"expected {spec.owned_sha256}"
                )
            if full_digest != spec.stock_sha256:
                composed.append(spec.path)
        elif full_digest != spec.stock_sha256:
            actual_owned = _owned_digest(data, merged)
            raise ValueError(
                f"{spec.path}: SHA-256 is {full_digest}, expected stock "
                f"{spec.stock_sha256}; current owned-region SHA-256 is {actual_owned}"
            )
    return tuple(composed)


def _render_records(records: list[dict[str, str]]) -> bytes:
    return (json.dumps(records, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _claim_source_regions(
    claims: dict[str, list[tuple[int, int, str]]],
    regions: tuple[Region, ...],
    source_name: str,
) -> None:
    for region in merge_regions(regions):
        for prior_start, prior_end, prior_source in claims.get(region.file, []):
            if region.start < prior_end and prior_start < region.end:
                raise ValueError(
                    f"source {source_name} overlaps {prior_source} in {region.file}"
                )
        claims.setdefault(region.file, []).append(
            (region.start, region.end, source_name)
        )


def build_batch(
    disc: str,
    *,
    extracted_root: Path | None = None,
    corpus_root: Path | None = None,
) -> ExtractionBatch:
    source_path = manifest_path(disc)
    manifest = load_manifest(source_path)
    if manifest.disc != disc:
        raise ValueError(f"{source_path}: disc is {manifest.disc!r}, expected {disc!r}")
    expected_track = _disc_track_sha256(disc)
    if manifest.track_sha256 != expected_track:
        raise ValueError(f"{source_path}: Track 1 identity does not match discs.json")

    output_root = corpus_root if corpus_root is not None else CORPUS_ROOT / disc
    blobs = (
        _read_stock_sources(manifest)
        if extracted_root is None
        else _read_sources(manifest, extracted_root)
    )
    catalog = load_config()
    existing, existing_paths = _load_existing(output_root)

    rendered: dict[PurePosixPath, bytes] = {}
    generated_ids: set[str] = set()
    all_regions: list[Region] = []
    claims: dict[str, list[tuple[int, int, str]]] = {}
    record_count = 0
    for source in manifest.sources:
        extraction = extract_source(source, blobs, catalog, disc)
        _claim_source_regions(claims, extraction.regions, source.name)
        rows: list[dict[str, str]] = []
        for seed in extraction.records:
            if seed.id in generated_ids:
                raise ValueError(f"duplicate generated corpus id {seed.id!r}")
            generated_ids.add(seed.id)
            _canonical_tokens(seed.reference, f"generated record {seed.id}.reference")
            state = existing.get(seed.id, CorpusState("", ""))
            rows.append(
                {
                    "id": seed.id,
                    "source_encoding": seed.source_encoding,
                    "output_encoding": "",
                    "reference": seed.reference,
                    "translation": state.translation,
                    "note": state.note,
                }
            )
        rendered[source.corpus_path] = _render_records(rows)
        record_count += len(rows)
        all_regions.extend(extraction.regions)

    orphaned = sorted(set(existing) - generated_ids)
    if orphaned:
        preview = ", ".join(orphaned[:5])
        suffix = " ..." if len(orphaned) > 5 else ""
        raise ValueError(
            f"existing corpus contains orphaned record ids: {preview}{suffix}"
        )
    expected_paths = set(rendered)
    extras = sorted(existing_paths - expected_paths)
    if extras:
        raise ValueError(
            f"corpus contains unmanaged JSON files: {', '.join(map(str, extras))}"
        )

    composed = _verify_sources(manifest, blobs, tuple(all_regions))
    return ExtractionBatch(rendered, len(manifest.sources), record_count, composed)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def publish_batch(batch: ExtractionBatch, corpus_root: Path, *, check: bool) -> None:
    mismatches: list[str] = []
    for relative, expected in batch.rendered.items():
        path = corpus_root.joinpath(*relative.parts)
        actual = path.read_bytes() if path.exists() else None
        if actual != expected:
            mismatches.append(str(relative))
    if check:
        if mismatches:
            raise ValueError(f"corpus is not current: {', '.join(mismatches)}")
        return
    for relative in sorted(batch.rendered):
        path = corpus_root.joinpath(*relative.parts)
        expected = batch.rendered[relative]
        if not path.exists() or path.read_bytes() != expected:
            _atomic_write(path, expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disc", nargs="?", default="game", choices=("game", "compendium")
    )
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    try:
        batch = build_batch(args.disc)
        publish_batch(batch, CORPUS_ROOT / args.disc, check=args.check)
    except ValueError as error:
        parser.error(str(error))
    action = "verified" if args.check else "extracted"
    composed = (
        "; preserved "
        f"{len(batch.composed_files)} file(s) with unrelated composed changes"
        if batch.composed_files
        else ""
    )
    summary = f"{action} {batch.record_count} records"
    print(f"{summary} from {batch.source_count} sources{composed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
