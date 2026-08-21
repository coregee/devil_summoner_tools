"""Checked language-project storage for non-technical localization flows."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from .catalog import PROJECT_ROOT

LANGUAGE_ROOT = PROJECT_ROOT / "assets" / "languages"
_ID_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
_LOCALE_RE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, document: dict[str, Any]) -> None:
    value = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_language(value: Any, context: str = "language") -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version",
        "id",
        "label",
        "locale",
        "base",
        "characters",
        "fonts",
    }:
        raise ValueError(f"{context} has an invalid language-project structure")
    if value["version"] != 1:
        raise ValueError(f"{context}.version must be 1")
    language_id = value["id"]
    if not isinstance(language_id, str) or _ID_RE.fullmatch(language_id) is None:
        raise ValueError(f"{context}.id must be a lowercase language identifier")
    label = value["label"]
    if not isinstance(label, str) or not label.strip():
        raise ValueError(f"{context}.label must be nonempty text")
    locale = value["locale"]
    if not isinstance(locale, str) or _LOCALE_RE.fullmatch(locale) is None:
        raise ValueError(f"{context}.locale must be a language tag such as fr or fr-CA")
    base = value["base"]
    if base is not None and (
        not isinstance(base, str) or _ID_RE.fullmatch(base) is None
    ):
        raise ValueError(f"{context}.base must be a language identifier or null")
    characters = value["characters"]
    if not isinstance(characters, str) or any(
        character in "{}\r\n\t" for character in characters
    ):
        raise ValueError(f"{context}.characters contains unsupported controls")
    if len(set(characters)) != len(characters):
        raise ValueError(f"{context}.characters must not contain duplicates")
    fonts = value["fonts"]
    if not isinstance(fonts, dict):
        raise ValueError(f"{context}.fonts must be an object")
    for font_id, raw_font in fonts.items():
        font_context = f"{context}.fonts.{font_id}"
        if not isinstance(font_id, str) or "/" not in font_id:
            raise ValueError(f"{font_context} has an invalid font id")
        if not isinstance(raw_font, dict) or set(raw_font) != {
            "source",
            "source_sha256",
            "mappings",
        }:
            raise ValueError(f"{font_context} has an invalid override")
        source = raw_font["source"]
        digest = raw_font["source_sha256"]
        mappings = raw_font["mappings"]
        if not isinstance(source, str) or not source.startswith("imported/"):
            raise ValueError(f"{font_context}.source must be an imported font")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{font_context}.source_sha256 is invalid")
        if not isinstance(mappings, dict):
            raise ValueError(f"{font_context}.mappings must be an object")
        for code, replacement in mappings.items():
            if (
                not code.isdecimal()
                or not isinstance(replacement, str)
                or not replacement
            ):
                raise ValueError(f"{font_context}.mappings contains an invalid glyph")
    return value


class LanguageService:
    def __init__(self, root: Path = LANGUAGE_ROOT) -> None:
        self.root = root
        self._lock = threading.RLock()

    def _path(self, language_id: str) -> Path:
        if _ID_RE.fullmatch(language_id) is None:
            raise ValueError("invalid language id")
        return self.root / f"{language_id}.json"

    def _load(self, language_id: str) -> dict[str, Any]:
        path = self._path(language_id)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError("unknown language project") from error
        return validate_language(document, path.as_posix())

    def list(self) -> dict[str, Any]:
        rows = []
        for path in sorted(self.root.glob("*.json")):
            document = validate_language(
                json.loads(path.read_text(encoding="utf-8")), path.as_posix()
            )
            rows.append(
                {
                    "id": document["id"],
                    "label": document["label"],
                    "locale": document["locale"],
                    "base": document["base"],
                    "characters": document["characters"],
                    "font_count": len(document["fonts"]),
                    "file_hash": _file_hash(path),
                    "built_in": document["id"] == "en",
                }
            )
        if not any(row["id"] == "en" for row in rows):
            raise ValueError("the built-in English language project is missing")
        return {"languages": rows}

    def detail(self, language_id: str) -> dict[str, Any]:
        document = self._load(language_id)
        return {
            **document,
            "file_hash": _file_hash(self._path(language_id)),
            "built_in": language_id == "en",
        }

    def create(
        self, language_id: str, label: str, locale: str, characters: str
    ) -> dict[str, Any]:
        with self._lock:
            path = self._path(language_id)
            if path.exists():
                raise ValueError("a language project with this id already exists")
            document = validate_language(
                {
                    "version": 1,
                    "id": language_id,
                    "label": label.strip(),
                    "locale": locale,
                    "base": "en",
                    "characters": "".join(dict.fromkeys(characters)),
                    "fonts": {},
                }
            )
            _atomic_json(path, document)
        return self.detail(language_id)

    def update(
        self,
        language_id: str,
        label: str,
        locale: str,
        characters: str,
        base_hash: str,
    ) -> dict[str, Any]:
        if language_id == "en":
            raise ValueError("the built-in English project cannot be edited")
        with self._lock:
            path = self._path(language_id)
            if _file_hash(path) != base_hash:
                raise RuntimeError(
                    "This language project changed on disk. Reload it before saving."
                )
            document = self._load(language_id)
            document["label"] = label.strip()
            document["locale"] = locale
            document["characters"] = "".join(dict.fromkeys(characters))
            validate_language(document)
            _atomic_json(path, document)
        return self.detail(language_id)

    def set_font_override(
        self,
        language_id: str,
        font_id: str,
        source: str,
        source_sha256: str,
        mappings: dict[str, str],
    ) -> dict[str, Any]:
        if language_id == "en":
            raise ValueError("English uses the checked base font definitions")
        with self._lock:
            path = self._path(language_id)
            document = self._load(language_id)
            document["fonts"][font_id] = {
                "source": source,
                "source_sha256": source_sha256,
                "mappings": mappings,
            }
            validate_language(document)
            _atomic_json(path, document)
        return self.detail(language_id)

    def update_font_mapping(
        self,
        language_id: str,
        font_id: str,
        code: int,
        replacement: str,
        base_hash: str,
    ) -> dict[str, Any]:
        if language_id == "en":
            raise ValueError("English uses the checked base font definitions")
        with self._lock:
            path = self._path(language_id)
            if _file_hash(path) != base_hash:
                raise RuntimeError(
                    "This language project changed on disk. Reload it before saving."
                )
            document = self._load(language_id)
            try:
                override = document["fonts"][font_id]
            except KeyError as error:
                raise ValueError("import a typeface for this font first") from error
            override["mappings"][str(code)] = replacement
            validate_language(document)
            _atomic_json(path, document)
        return self.detail(language_id)

    def replace_font_mappings(
        self,
        language_id: str,
        font_id: str,
        mappings: dict[str, str],
        base_hash: str,
    ) -> dict[str, Any]:
        if language_id == "en":
            raise ValueError("English uses the checked base font definitions")
        with self._lock:
            path = self._path(language_id)
            if _file_hash(path) != base_hash:
                raise RuntimeError(
                    "This language project changed on disk. Reload it before saving."
                )
            document = self._load(language_id)
            try:
                override = document["fonts"][font_id]
            except KeyError as error:
                raise ValueError("import a typeface for this font first") from error
            override["mappings"] = dict(mappings)
            validate_language(document)
            _atomic_json(path, document)
        return self.detail(language_id)
