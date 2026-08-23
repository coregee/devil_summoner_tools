"""Strict authored-asset loaders used by PSP text and runtime surfaces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = PROJECT_ROOT / "assets" / "text"
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


def load_asset_field(
    identity: str,
    *,
    asset_root: Path = ASSET_ROOT,
) -> tuple[str, str]:
    """Resolve one ``path#entry.field`` identity without platform imports."""

    if not isinstance(identity, str) or identity.count("#") != 1:
        raise ValueError("PSP asset identity must be path#entry.field text")
    raw_path, separator, field_identity = identity.partition("#")
    if not separator or field_identity.count(".") != 1 or "\\" in raw_path:
        raise ValueError(f"invalid PSP asset identity: {identity!r}")
    entry_name, field_name = field_identity.split(".")
    relative = PurePosixPath(raw_path)
    if (
        relative.is_absolute()
        or relative.suffix != ".json"
        or any(part in {"", ".", ".."} for part in relative.parts)
        or not entry_name
        or not field_name
    ):
        raise ValueError(f"invalid PSP asset identity: {identity!r}")
    root = asset_root.resolve()
    path = (asset_root / Path(*relative.parts)).resolve()
    if path.parent != root and root not in path.parents:
        raise ValueError(f"PSP asset identity escapes the asset root: {identity!r}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP authored asset: {path}") from error
    entries = document.get("entries") if isinstance(document, dict) else None
    entry = entries.get(entry_name) if isinstance(entries, dict) else None
    field = entry.get(field_name) if isinstance(entry, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") not in {"entity_catalog", "surface_catalog"}
        or not isinstance(field, dict)
        or not isinstance(field.get("reference"), str)
        or not isinstance(field.get("translation"), str)
    ):
        raise ValueError(f"{path}: invalid authored field {field_identity!r}")
    return field["reference"], field["translation"]


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
