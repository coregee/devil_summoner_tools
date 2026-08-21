"""Index canonical text fields and their Saturn consumer surfaces."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from saturn.text.util.assets import validate_asset_document

from .models import ConsumerUse, EntryKey

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "assets" / "text"
BINDING_ROOT = PROJECT_ROOT / "saturn" / "text" / "bindings"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON field {key!r}")
        output[key] = value
    return output


def _read_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _signature(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CorpusCatalog:
    """A refreshable in-memory view over the authored text JSON."""

    def __init__(
        self,
        *,
        asset_root: Path = ASSET_ROOT,
        binding_root: Path = BINDING_ROOT,
    ) -> None:
        self.asset_root = asset_root
        self.binding_root = binding_root
        self._lock = threading.RLock()
        self._documents: dict[str, dict[str, Any]] = {}
        self._signatures: dict[str, str] = {}
        self._consumers: dict[tuple[str, str], tuple[ConsumerUse, ...]] = {}
        self.refresh()

    def refresh(self) -> None:
        documents: dict[str, dict[str, Any]] = {}
        signatures: dict[str, str] = {}
        for path in sorted(self.asset_root.rglob("*.json")):
            relative = path.relative_to(self.asset_root).as_posix()
            document = _read_document(path)
            # A few authored text assets (notably timed FMV subtitles) have
            # purpose-built schemas.  The first editor slice indexes the shared
            # field catalogue contract and leaves those specialized documents
            # to a later adapter.
            if set(document) != {"version", "kind", "entries"}:
                continue
            validate_asset_document(document, relative)
            documents[relative] = document
            signatures[relative] = _signature(path)
        consumers = self._load_consumers()
        with self._lock:
            self._documents = documents
            self._signatures = signatures
            self._consumers = consumers

    def _load_consumers(self) -> dict[tuple[str, str], tuple[ConsumerUse, ...]]:
        uses: defaultdict[tuple[str, str], set[ConsumerUse]] = defaultdict(set)
        if not self.binding_root.is_dir():
            return {}
        for path in sorted(self.binding_root.glob("*.json")):
            document = _read_document(path)
            asset = document.get("asset")
            records = document.get("records", {})
            field_surfaces = document.get("field_surfaces", {})
            record_surfaces = document.get("record_surfaces", {})
            if not isinstance(asset, str) or not isinstance(records, dict):
                continue
            for record_id, asset_ref in records.items():
                if not isinstance(record_id, str) or not isinstance(asset_ref, str):
                    continue
                field = asset_ref.rsplit(".", 1)[-1]
                surfaces = record_surfaces.get(record_id, field_surfaces.get(field, ()))
                if not isinstance(surfaces, list):
                    surfaces = []
                if surfaces:
                    for surface in surfaces:
                        if isinstance(surface, str):
                            uses[(asset, asset_ref)].add(
                                ConsumerUse(record_id, surface)
                            )
                else:
                    uses[(asset, asset_ref)].add(ConsumerUse(record_id, None))

            additional = document.get("additional_uses", {})
            if isinstance(additional, dict):
                for record_id, rows in additional.items():
                    if not isinstance(record_id, str) or not isinstance(rows, list):
                        continue
                    surfaces = record_surfaces.get(record_id, ())
                    for row in rows:
                        if not isinstance(row, dict) or not isinstance(
                            row.get("asset"), str
                        ):
                            continue
                        asset_ref = row["asset"]
                        if isinstance(surfaces, list) and surfaces:
                            for surface in surfaces:
                                if isinstance(surface, str):
                                    uses[(asset, asset_ref)].add(
                                        ConsumerUse(record_id, surface)
                                    )
                        else:
                            uses[(asset, asset_ref)].add(ConsumerUse(record_id, None))
        return {
            key: tuple(
                sorted(value, key=lambda item: (item.surface or "", item.record_id))
            )
            for key, value in uses.items()
        }

    def list_entries(self, query: str = "", limit: int = 250) -> dict[str, Any]:
        needle = query.casefold().strip()
        rows: list[dict[str, Any]] = []
        total = 0
        with self._lock:
            for asset, document in self._documents.items():
                for entry_name, entry in document["entries"].items():
                    for field_name, field in entry.items():
                        if field_name in {"status", "note", "placeholders"}:
                            continue
                        key = EntryKey(asset, entry_name, field_name)
                        haystack = "\n".join(
                            (
                                asset,
                                entry_name,
                                field_name,
                                str(field.get("reference", "")),
                                str(field.get("translation", "")),
                            )
                        ).casefold()
                        if needle and needle not in haystack:
                            continue
                        total += 1
                        if len(rows) >= limit:
                            continue
                        consumers = self._consumers.get((asset, key.asset_ref), ())
                        surfaces = sorted(
                            {
                                item.surface
                                for item in consumers
                                if item.surface is not None
                            }
                        )
                        rows.append(
                            {
                                "id": key.id,
                                "asset": asset,
                                "entry": entry_name,
                                "field": field_name,
                                "reference": field["reference"],
                                "translation": field["translation"],
                                "reviewed": bool(field.get("reviewed", False)),
                                "surfaces": surfaces,
                                "consumer_count": len(consumers),
                            }
                        )
        return {"entries": rows, "total": total, "limited": total > len(rows)}

    def entry(self, value: str) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            try:
                document = self._documents[key.asset]
                raw_entry = document["entries"][key.entry]
                field = raw_entry[key.field]
            except KeyError as error:
                raise ValueError("unknown editor entry") from error
            consumers = self._consumers.get((key.asset, key.asset_ref), ())
            return {
                "id": key.id,
                "asset": key.asset,
                "entry": key.entry,
                "field": key.field,
                "reference": field["reference"],
                "translation": field["translation"],
                "reviewed": bool(field.get("reviewed", False)),
                "note": field.get("note") or raw_entry.get("note"),
                "status": raw_entry.get("status"),
                "variants": copy.deepcopy(field.get("variants", {})),
                "consumers": [
                    {"record_id": item.record_id, "surface": item.surface}
                    for item in consumers
                ],
                "file_hash": self._signatures[key.asset],
            }

    def candidate_document(self, value: str, translation: str) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            try:
                candidate = copy.deepcopy(self._documents[key.asset])
                candidate["entries"][key.entry][key.field]["translation"] = translation
            except KeyError as error:
                raise ValueError("unknown editor entry") from error
        validate_asset_document(candidate, key.asset)
        return candidate

    def save(self, value: str, translation: str, base_hash: str) -> dict[str, Any]:
        key = EntryKey.parse(value)
        with self._lock:
            path = self.asset_root.joinpath(*key.asset.split("/"))
            current_hash = _signature(path)
            if base_hash != current_hash:
                raise RuntimeError(
                    "This asset changed on disk. Reload it before saving."
                )
            candidate = self.candidate_document(value, translation)
            serialized = (
                json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            handle, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            try:
                with os.fdopen(handle, "wb") as output:
                    output.write(serialized)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self._documents[key.asset] = candidate
            self._signatures[key.asset] = _signature(path)
        return self.entry(value)
