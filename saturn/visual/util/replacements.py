"""Resolve shared replacement images through Saturn-specific view bindings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .paths import IMAGE_CATALOG_PATH, IMAGE_ROOT, bindings_path


@dataclass(frozen=True)
class ReplacementImage:
    asset: str
    view: str
    path: Path
    width: int
    height: int
    portability: str

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


def _document(path: Path, kind: str) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("version") != 1 or document.get("kind") != kind:
        raise ValueError(f"{path}: unsupported {kind}")
    return document


def _asset_path(value: object) -> Path:
    relative = PurePosixPath(str(value))
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".png":
        raise ValueError(f"{IMAGE_CATALOG_PATH}: unsafe image path {value!r}")
    return IMAGE_ROOT.joinpath(*relative.parts)


def load_replacements(disc: str) -> tuple[ReplacementImage, ...]:
    catalog = _document(IMAGE_CATALOG_PATH, "image_catalog")
    images = catalog.get("images")
    if not isinstance(images, dict):
        raise ValueError(f"{IMAGE_CATALOG_PATH}: images must be an object")

    binding_path = bindings_path(disc)
    binding = _document(binding_path, "visual_bindings")
    if binding.get("platform") != "saturn" or binding.get("disc") != disc:
        raise ValueError(f"{binding_path}: platform or disc mismatch")
    rows = binding.get("replacements")
    if not isinstance(rows, list):
        raise ValueError(f"{binding_path}: replacements must be an array")

    catalog_paths: dict[Path, str] = {}
    for asset, metadata in images.items():
        if not isinstance(asset, str) or not isinstance(metadata, dict):
            raise ValueError(f"{IMAGE_CATALOG_PATH}: malformed image entry")
        path = _asset_path(metadata.get("path"))
        if path in catalog_paths:
            raise ValueError(
                f"{IMAGE_CATALOG_PATH}: {asset!r} and "
                f"{catalog_paths[path]!r} use the same image path"
            )
        catalog_paths[path] = asset

    replacements = []
    seen_views: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{binding_path}: replacement must be an object")
        asset = str(row.get("asset", ""))
        view = str(row.get("view", ""))
        if not asset:
            raise ValueError(f"{binding_path}: empty asset")
        if not view or view.casefold() in seen_views:
            raise ValueError(f"{binding_path}: duplicate or empty view {view!r}")
        metadata = images.get(asset)
        if not isinstance(metadata, dict):
            raise ValueError(f"{binding_path}: unknown image asset {asset!r}")
        width = metadata.get("width")
        height = metadata.get("height")
        portability = metadata.get("portability")
        if not isinstance(width, int) or width <= 0:
            raise ValueError(f"{IMAGE_CATALOG_PATH}: invalid width for {asset}")
        if not isinstance(height, int) or height <= 0:
            raise ValueError(f"{IMAGE_CATALOG_PATH}: invalid height for {asset}")
        if not isinstance(portability, str) or not portability:
            raise ValueError(f"{IMAGE_CATALOG_PATH}: invalid portability for {asset}")
        replacements.append(
            ReplacementImage(
                asset=asset,
                view=view,
                path=_asset_path(metadata.get("path")),
                width=width,
                height=height,
                portability=portability,
            )
        )
        seen_views.add(view.casefold())
    return tuple(replacements)
