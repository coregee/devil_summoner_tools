"""Compose command-menu help and the existing CONFIG projection in member 14."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from psp.archive.pack import PspPack
from psp.text.util.config_menu import ConfigTextBuild, build_config_text
from psp.text.util.event_packed import glyph_code_for_character


TEXT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TEXT_ROOT.parents[1]
CONFIG_PATH = TEXT_ROOT / "config" / "command_menu_help.json"
ASSETS = {
    "general": REPO_ROOT / "assets" / "text" / "ui" / "command_help.json",
    "battle": REPO_ROOT / "assets" / "text" / "battle" / "help.json",
    "psp": REPO_ROOT / "assets" / "text" / "ui" / "command_help_psp.json",
}
TOKEN_PATTERN = re.compile(r"\{n\}|\{OP:8002\}|\{OP:8004\}")
TOKEN_WORDS = {"{n}": 0x8001, "{OP:8002}": 0x8002, "{OP:8004}": 0x8004}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_paths() -> tuple[Path, ...]:
    return tuple(ASSETS[key] for key in sorted(ASSETS))


def _translations() -> dict[tuple[str, str], str]:
    result = {}
    for source, path in ASSETS.items():
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("version") != 1 or document.get("kind") != "surface_catalog":
            raise ValueError(f"invalid command-help asset: {path}")
        for key, row in document["entries"].items():
            translation = row["text"]["translation"]
            if not isinstance(translation, str) or not translation:
                raise ValueError(f"invalid command-help translation: {source}.{key}")
            result[(source, key)] = translation
    return result


def _words(text: str) -> list[int]:
    words = []
    position = 0
    for match in TOKEN_PATTERN.finditer(text):
        fragment = text[position : match.start()]
        if "{" in fragment or "}" in fragment:
            raise ValueError("command-menu help contains an unknown control token")
        words.extend(glyph_code_for_character(character) for character in fragment)
        words.append(TOKEN_WORDS[match.group(0)])
        position = match.end()
    fragment = text[position:]
    if "{" in fragment or "}" in fragment:
        raise ValueError("command-menu help contains an unknown control token")
    words.extend(glyph_code_for_character(character) for character in fragment)
    return words


@dataclass(frozen=True, slots=True)
class CommandMenuHelpBuild:
    data: bytes
    member: bytes
    translations: tuple[str, ...]
    changed_byte_count: int


def build_command_menu_help(
    source: bytes, config_projection: ConfigTextBuild | None = None
) -> CommandMenuHelpBuild:
    plan = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if plan.get("version") != 1:
        raise ValueError("invalid PSP command-menu help binding")
    archive = PspPack.parse(source)
    member = archive.members[plan["member_index"]]
    if (
        member.offset != plan["member_offset"]
        or member.size != plan["member_size"]
        or _sha(member.data) != plan["member_sha256"]
    ):
        raise ValueError("PSP command-menu help source member changed")
    projection = config_projection or build_config_text(source)
    projected = projection.member
    translations = _translations()
    rebuilt = bytearray(projected)
    used_slots = set()
    output_text = []
    for slot_index, source_id, key in plan["records"]:
        if slot_index in used_slots or not 0 <= slot_index < plan["slot_count"]:
            raise ValueError("PSP command-menu help slot ownership is invalid")
        used_slots.add(slot_index)
        try:
            translation = translations[(source_id, key)]
        except KeyError as error:
            raise ValueError(f"missing command-help asset: {source_id}.{key}") from error
        words = _words(translation)
        if len(words) + 1 > plan["slot_words"]:
            raise ValueError(f"command-help slot {slot_index} exceeds its capacity")
        words.append(plan["terminator"])
        words.extend([0] * (plan["slot_words"] - len(words)))
        start = slot_index * plan["slot_words"] * 2
        rebuilt[start : start + plan["slot_words"] * 2] = struct.pack(
            f">{plan['slot_words']}H", *words
        )
        output_text.append(translation)
    expected_slots = set(range(45)) | set(range(54, 57))
    if used_slots != expected_slots:
        raise ValueError("PSP command-menu help does not own the expected 48 slots")
    for slot_index in range(45, 54):
        start = slot_index * plan["slot_words"] * 2
        end = start + plan["slot_words"] * 2
        if rebuilt[start:end] != projected[start:end]:
            raise ValueError("PSP command-menu help changed a CONFIG-owned slot")
    replacement = bytes(rebuilt)
    standalone = archive.rebuild({member.index: replacement})
    changed = sum(left != right for left, right in zip(source, standalone, strict=True))
    if (
        _sha(replacement) != plan["output_member_sha256"]
        or _sha(standalone) != plan["output_regdata_sha256"]
        or changed != plan["changed_byte_count"]
    ):
        raise ValueError("PSP command-menu help output contract changed")
    return CommandMenuHelpBuild(
        standalone, replacement, tuple(output_text), changed
    )


__all__ = (
    "ASSETS",
    "CONFIG_PATH",
    "CommandMenuHelpBuild",
    "asset_paths",
    "build_command_menu_help",
)
