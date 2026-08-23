"""Build the packed PSP EVENT demon-name insertion table from canonical assets."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.text.util.assets import load_asset_field

from .event_packed import encode_ascii


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "event_dvlname.json"
DVLNAME_RECORD_COUNT = 319
DVLNAME_MAX_TRANSLATION_LENGTH = 16
DVLNAME_RUNTIME_MAGIC = 0x454C5644


@dataclass(frozen=True, slots=True)
class PspDvlNameRecord:
    index: int
    asset: str
    reference: str
    translation: str


def load_psp_dvlname_text(
    path: Path = CONFIG_PATH,
) -> tuple[PspDvlNameRecord, ...]:
    """Resolve the checked 319-slot physical table through semantic assets."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP DVLNAME binding: {path}") from error
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("table") != "DVLNAME"
        or document.get("record_count") != DVLNAME_RECORD_COUNT
        or document.get("max_bytes") != DVLNAME_MAX_TRANSLATION_LENGTH
        or not isinstance(document.get("records"), list)
        or len(document["records"]) != DVLNAME_RECORD_COUNT
        or not isinstance(document.get("overrides"), list)
    ):
        raise ValueError(f"{path}: unsupported PSP DVLNAME binding")
    identities = list(document["records"])
    seen_overrides: set[int] = set()
    for position, row in enumerate(document["overrides"]):
        if (
            not isinstance(row, dict)
            or set(row) != {"record_index", "asset"}
            or type(row["record_index"]) is not int
            or not 0 <= row["record_index"] < DVLNAME_RECORD_COUNT
            or row["record_index"] in seen_overrides
            or not isinstance(row["asset"], str)
        ):
            raise ValueError(f"{path}: invalid DVLNAME override {position}")
        seen_overrides.add(row["record_index"])
        identities[row["record_index"]] = row["asset"]
    records = []
    for index, identity in enumerate(identities):
        if not isinstance(identity, str):
            raise ValueError(f"{path}: DVLNAME slot {index} has no asset identity")
        reference, translation = load_asset_field(identity)
        if (
            not reference
            or not translation
            or len(translation.encode("ascii", errors="ignore")) != len(translation)
            or len(translation) > DVLNAME_MAX_TRANSLATION_LENGTH
        ):
            raise ValueError(
                f"{path}: DVLNAME slot {index} must be 1-"
                f"{DVLNAME_MAX_TRANSLATION_LENGTH} printable ASCII characters"
            )
        if any(not 0x20 <= ord(character) <= 0x7E for character in translation):
            raise ValueError(f"{path}: DVLNAME slot {index} is not printable ASCII")
        records.append(PspDvlNameRecord(index, identity, reference, translation))
    return tuple(records)


def build_psp_dvlname_runtime_table(
    records: tuple[PspDvlNameRecord, ...] | None = None,
) -> bytes:
    """Build little-endian offsets plus a deduplicated packed-English pool."""

    records = load_psp_dvlname_text() if records is None else records
    if len(records) != DVLNAME_RECORD_COUNT:
        raise ValueError("PSP DVLNAME runtime table needs 319 records")
    offsets = bytearray(DVLNAME_RECORD_COUNT * 2)
    pool = bytearray()
    pooled_offsets: dict[str, int] = {}
    for index, record in enumerate(records):
        if record.index != index:
            raise ValueError(f"PSP DVLNAME runtime row {index} identity changed")
        offset = pooled_offsets.get(record.translation)
        if offset is None:
            offset = len(offsets) + len(pool)
            pooled_offsets[record.translation] = offset
            pool.extend(encode_ascii(record.translation))
            pool.append(0)
        if offset > 0xFFFF:
            raise ValueError("PSP DVLNAME runtime pool exceeds u16 offsets")
        struct.pack_into("<H", offsets, index * 2, offset)
    return bytes(offsets + pool)


__all__ = [
    "CONFIG_PATH",
    "DVLNAME_MAX_TRANSLATION_LENGTH",
    "DVLNAME_RECORD_COUNT",
    "DVLNAME_RUNTIME_MAGIC",
    "PspDvlNameRecord",
    "build_psp_dvlname_runtime_table",
    "load_psp_dvlname_text",
]
