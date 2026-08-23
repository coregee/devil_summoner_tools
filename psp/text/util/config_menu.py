"""Compile PSP CONFIG contextual help into regdata member 14."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.archive.pack import PspPack
from psp.text.util.assets import load_config_asset
from psp.text.util.event_packed import MESSAGE_TERMINATOR, glyph_code_for_character


TEXT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = TEXT_ROOT / "config" / "config_menu.json"
OUTPUT_SHA256 = "a4d7d6b4e049968431193eb0ef3ad5afa3c36bb37f9737d65d2c3aecff56b9e0"
OUTPUT_MEMBER_SHA256 = "453a48e898a1abed6ba4562bed3f97ca3afa00494fccabed65fa33d2e4e6a509"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class ConfigTextBuild:
    data: bytes
    member: bytes
    translations: tuple[str, ...]


def build_config_text(source: bytes) -> ConfigTextBuild:
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if document.get("version") != 1 or document.get("member_index") != 14:
        raise ValueError("invalid PSP CONFIG text binding")
    source_hash = document["source_sha256"].removeprefix("sha256:")
    if len(source) != document["source_size"] or _sha(source) != source_hash:
        raise ValueError("PSP CONFIG regdata source changed")
    archive = PspPack.parse(source)
    member = archive.members[document["member_index"]]
    if (
        member.offset != int(document["member_offset"], 16)
        or member.size != document["member_size"]
        or _sha(member.data)
        != document["member_sha256"].removeprefix("sha256:")
    ):
        raise ValueError("PSP CONFIG help member source changed")
    asset = {
        (role, key): (reference, translation)
        for role, key, reference, translation in load_config_asset()
    }
    translations = []
    rebuilt_member = bytearray(member.data)
    slot_words = document["slot_words"]
    for record in document["records"]:
        key = ("context_help", record["key"])
        reference, translation = asset[key]
        expected_reference = record["source_text_sha256"].removeprefix("sha256:")
        if _sha(reference.encode("utf-8")) != expected_reference:
            raise ValueError(f"PSP CONFIG source reference changed: {record['key']}")
        words = [glyph_code_for_character(character) for character in translation]
        if len(words) >= slot_words:
            raise ValueError(f"PSP CONFIG help exceeds slot capacity: {record['key']}")
        words.append(MESSAGE_TERMINATOR)
        words.extend([0] * (slot_words - len(words)))
        slot = struct.pack(f">{slot_words}H", *words)
        offset = int(record["slot_offset"], 16)
        rebuilt_member[offset : offset + len(slot)] = slot
        translations.append(translation)
    replacement = bytes(rebuilt_member)
    if _sha(replacement) != OUTPUT_MEMBER_SHA256:
        raise ValueError("PSP CONFIG help member output contract changed")
    rebuilt = archive.rebuild({member.index: replacement})
    if _sha(rebuilt) != OUTPUT_SHA256:
        raise ValueError("PSP CONFIG regdata output contract changed")
    return ConfigTextBuild(rebuilt, replacement, tuple(translations))
