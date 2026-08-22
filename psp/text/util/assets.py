"""Narrow authored-asset loader for the PSP title-help surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TITLE_ASSET_PATH = PROJECT_ROOT / "assets" / "text" / "ui" / "title.json"
TITLE_HELP_KEYS = (
    "help_load",
    "help_new",
    "help_option",
    "help_special",
    "help_normal",
    "help_hard",
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
