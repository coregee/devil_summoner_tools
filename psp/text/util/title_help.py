"""Fail-closed codec for English PSP title-menu help records."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.archive.pack import PspPack
from psp.text.util.assets import TITLE_HELP_KEYS, load_title_help_asset, strings_sha256


TEXT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = TEXT_ROOT / "config" / "title_help.json"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be hexadecimal text")
    try:
        return int(value, 16)
    except ValueError as error:
        raise ValueError(f"{context} is not hexadecimal") from error


@dataclass(frozen=True, slots=True)
class TitleHelpConfig:
    iso_path: str
    source_size: int
    source_sha256: str
    member_count: int
    member_index: int
    member_offset: int
    member_size: int
    member_sha256: str
    slot_words: int
    terminator: int
    encoding: tuple[tuple[str, int], ...]
    reference_sha256: str
    translation_sha256: str
    output_sha256: str
    output_member_sha256: str

    @property
    def slot_size(self) -> int:
        return self.slot_words * 2


def load_config(path: Path = CONFIG_PATH) -> TitleHelpConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP title-help config: {path}") from error
    if not isinstance(document, dict) or set(document) != {
        "version", "id", "asset", "source", "encoding", "output"
    }:
        raise ValueError(f"{path}: invalid root fields")
    asset = document["asset"]
    source = document["source"]
    encoding = document["encoding"]
    output = document["output"]
    if (
        document["version"] != 1
        or document["id"] != "title_help"
        or not isinstance(asset, dict)
        or set(asset) != {
            "path", "keys", "reference_sha256", "translation_sha256"
        }
        or asset["path"] != "assets/text/ui/title.json"
        or tuple(asset["keys"]) != TITLE_HELP_KEYS
        or not isinstance(source, dict)
        or set(source) != {
            "iso_path", "size", "sha256", "member_count", "member_index",
            "member_offset", "member_size", "member_sha256"
        }
        or not isinstance(encoding, dict)
        or set(encoding) != {
            "slot_count", "slot_words", "terminator", "ranges", "glyphs"
        }
        or not isinstance(output, dict)
        or set(output) != {"sha256", "member_sha256"}
    ):
        raise ValueError(f"{path}: unsupported title-help contract")
    integer_fields = (
        source["size"], source["member_count"], source["member_index"],
        source["member_offset"], source["member_size"], encoding["slot_count"],
        encoding["slot_words"],
    )
    digests = (
        source["sha256"], source["member_sha256"], asset["reference_sha256"],
        asset["translation_sha256"], output["sha256"], output["member_sha256"],
    )
    if (
        any(type(value) is not int or value < 0 for value in integer_fields)
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in digests
        )
        or source["iso_path"] != "PSP_GAME/USRDIR/regdata.bin"
        or encoding["slot_count"] != len(TITLE_HELP_KEYS)
        or encoding["slot_words"] != 42
        or source["member_size"] != encoding["slot_count"] * encoding["slot_words"] * 2
    ):
        raise ValueError(f"{path}: invalid title-help geometry")

    mappings: dict[str, int] = {}
    for row in encoding["ranges"]:
        if not isinstance(row, dict) or set(row) != {"characters", "start"}:
            raise ValueError(f"{path}: invalid title-help encoding range")
        start = _hex(row["start"], "encoding range start")
        for offset, character in enumerate(row["characters"]):
            mappings[character] = start + offset
    for row in encoding["glyphs"]:
        if not isinstance(row, dict) or set(row) != {"character", "code"}:
            raise ValueError(f"{path}: invalid title-help encoding glyph")
        mappings[row["character"]] = _hex(row["code"], "encoding glyph code")
    expected = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .")
    if set(mappings) != expected or len(set(mappings.values())) != len(mappings):
        raise ValueError(f"{path}: incomplete title-help encoding")
    return TitleHelpConfig(
        source["iso_path"], source["size"], source["sha256"],
        source["member_count"], source["member_index"], source["member_offset"],
        source["member_size"], source["member_sha256"], encoding["slot_words"],
        _hex(encoding["terminator"], "terminator"), tuple(mappings.items()),
        asset["reference_sha256"], asset["translation_sha256"], output["sha256"],
        output["member_sha256"],
    )


@dataclass(frozen=True, slots=True)
class TitleHelpBuild:
    data: bytes
    member: bytes
    translations: tuple[str, ...]


def encode_slot(text: str, config: TitleHelpConfig) -> bytes:
    if not isinstance(text, str) or not text:
        raise ValueError("PSP title help must be nonempty text")
    encoding = dict(config.encoding)
    try:
        words = [encoding[character] for character in text]
    except KeyError as error:
        raise ValueError(
            f"PSP title-help character is not authorable: {error.args[0]!r}"
        ) from error
    if len(words) >= config.slot_words:
        raise ValueError(
            f"PSP title help uses {len(words)} glyphs; capacity is {config.slot_words - 1}"
        )
    words.append(config.terminator)
    words.extend([0] * (config.slot_words - len(words)))
    return struct.pack(f">{config.slot_words}H", *words)


def decode_slot(data: bytes, config: TitleHelpConfig) -> str:
    if not isinstance(data, bytes) or len(data) != config.slot_size:
        raise ValueError("PSP title-help slot has the wrong size")
    words = struct.unpack(f">{config.slot_words}H", data)
    try:
        end = words.index(config.terminator)
    except ValueError as error:
        raise ValueError("PSP title-help slot has no terminator") from error
    if any(words[end + 1 :]):
        raise ValueError("PSP title-help slot tail is not zero-filled")
    decoding = {code: character for character, code in config.encoding}
    try:
        return "".join(decoding[word] for word in words[:end])
    except KeyError as error:
        raise ValueError(f"PSP title-help word is not authorable: {error.args[0]:#06x}") from error


def build_title_help(source: bytes, config: TitleHelpConfig | None = None) -> TitleHelpBuild:
    plan = config or load_config()
    if len(source) != plan.source_size or _digest(source) != plan.source_sha256:
        raise ValueError("PSP regdata.bin source contract changed")
    archive = PspPack.parse(source)
    if len(archive.members) != plan.member_count or archive.rebuild() != source:
        raise ValueError("PSP regdata.bin pack layout changed")
    member = archive.members[plan.member_index]
    if (
        member.offset != plan.member_offset
        or member.size != plan.member_size
        or _digest(member.data) != plan.member_sha256
    ):
        raise ValueError("PSP title-help source member contract changed")
    asset = load_title_help_asset()
    references = tuple(row[1] for row in asset)
    translations = tuple(row[2] for row in asset)
    if strings_sha256(references) != plan.reference_sha256:
        raise ValueError("PSP title-help Japanese references changed")
    if strings_sha256(translations) != plan.translation_sha256:
        raise ValueError("PSP title-help translations changed")
    replacement = b"".join(encode_slot(text, plan) for text in translations)
    if len(replacement) != member.size or _digest(replacement) != plan.output_member_sha256:
        raise ValueError("PSP title-help replacement member contract changed")
    for index, translation in enumerate(translations):
        start = index * plan.slot_size
        if decode_slot(replacement[start : start + plan.slot_size], plan) != translation:
            raise ValueError(f"PSP title-help record {index} did not round-trip")
    rebuilt = archive.rebuild({member.index: replacement})
    if len(rebuilt) != len(source) or _digest(rebuilt) != plan.output_sha256:
        raise ValueError("PSP title-help regdata output contract changed")
    if rebuilt[:member.offset] != source[:member.offset] or rebuilt[
        member.offset + member.size:
    ] != source[member.offset + member.size:]:
        raise ValueError("PSP title-help build changed bytes outside member 30")
    return TitleHelpBuild(rebuilt, replacement, translations)
