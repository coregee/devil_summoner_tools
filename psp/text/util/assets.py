"""Narrow authored-asset loader for the PSP title-help surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TITLE_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "ui" / "title.json"
CONFIG_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "ui" / "config_psp.json"
TITLE_HELP_KEYS = (
    "help_load",
    "help_new",
    "help_option",
    "help_special",
    "help_normal",
    "help_hard",
)
CONFIG_IDENTITIES = (
    *(
        ("label", key)
        for key in (
            "triangle_button",
            "start_button",
            "l_button",
            "r_button",
            "auto_map",
            "battle_messages",
            "message_speed",
            "screen_size",
            "frame",
        )
    ),
    *(
        ("action", key)
        for key in (
            "magic",
            "status",
            "auto_map",
            "item_use",
            "analyze",
            "recovery",
        )
    ),
    ("orientation", "north_up"),
    ("orientation", "facing_up"),
    *(("speed", key) for key in ("fast", "normal", "slow")),
    *(("size", key) for key in ("normal", "wide_1", "wide_2")),
    *(("frame", key) for key in ("type_1", "type_2", "type_3")),
    ("secondary_help", "delete_save_data"),
    *(
        ("context_help", key)
        for key in (
            "triangle_button",
            "start_button",
            "l_button",
            "r_button",
            "auto_map",
            "battle_messages",
            "message_speed",
            "screen_size",
            "frame",
        )
    ),
    ("mode", "normal"),
    ("mode", "hard"),
)


def strings_sha256(strings: tuple[str, ...]) -> str:
    encoded = json.dumps(
        list(strings), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_title_help_asset(
    path: Path = TITLE_ASSET_PATH,
) -> tuple[tuple[str, str, str], ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP title-help asset: {path}") from error
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") != "surface_catalog"
        or not isinstance(document.get("entries"), dict)
    ):
        raise ValueError(f"{path}: invalid surface catalogue")
    rows = []
    for key in TITLE_HELP_KEYS:
        entry = document["entries"].get(key)
        text = entry.get("text") if isinstance(entry, dict) else None
        if (
            not isinstance(text, dict)
            or set(text) != {"reference", "translation", "note"}
            or not isinstance(text["reference"], str)
            or not text["reference"]
            or not isinstance(text["translation"], str)
            or not text["translation"]
            or not isinstance(text["note"], str)
        ):
            raise ValueError(f"{path}: invalid title-help entry {key!r}")
        rows.append((key, text["reference"], text["translation"]))
    return tuple(rows)


def load_config_asset(
    path: Path = CONFIG_ASSET_PATH,
) -> tuple[tuple[str, str, str, str], ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP CONFIG asset: {path}") from error
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") != "surface_catalog"
        or not isinstance(document.get("entries"), dict)
    ):
        raise ValueError(f"{path}: invalid PSP CONFIG catalogue")
    rows = []
    for role, key in CONFIG_IDENTITIES:
        entry_key = f"{role}_{key}"
        entry = document["entries"].get(entry_key)
        text = entry.get("text") if isinstance(entry, dict) else None
        if (
            not isinstance(text, dict)
            or set(text) != {"reference", "translation", "note"}
            or not isinstance(text["reference"], str)
            or not text["reference"]
            or not isinstance(text["translation"], str)
            or not text["translation"]
        ):
            raise ValueError(f"{path}: invalid PSP CONFIG entry {entry_key!r}")
        rows.append((role, key, text["reference"], text["translation"]))
    return tuple(rows)
