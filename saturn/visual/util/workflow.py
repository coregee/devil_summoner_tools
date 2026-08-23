"""Manifest, extraction, and selective repacking workflows."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from PIL import Image

from .catalog import discover_assets, discover_views
from .codec import adaptive_palette, decode, encode, pixel_hash
from .model import ImageAsset, ImageView
from .paths import extracted_root, manifest_path, rom_root
from .replacements import ReplacementImage, load_replacements


def _file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compose(view: ImageView, source_data: dict[str, bytes]) -> Image.Image:
    pieces = [decode(source_data[target.source], target) for target in view.targets]
    if view.layout == "identity":
        return pieces[0]
    output = Image.new("RGB", view.size)
    left = 0
    for piece in pieces:
        output.paste(piece, (left, 0))
        left += piece.width
    return output


def _split(image: Image.Image, view: ImageView) -> tuple[Image.Image, ...]:
    if image.size != view.size:
        raise ValueError(
            f"{view.path}: got {image.width}x{image.height}, "
            f"expected {view.size[0]}x{view.size[1]}"
        )
    if view.layout == "identity":
        return tuple(image.copy() for _ in view.targets)
    pieces = []
    left = 0
    for target in view.targets:
        pieces.append(image.crop((left, 0, left + target.width, target.height)))
        left += target.width
    return tuple(pieces)


def build_manifest(disc: str) -> tuple[dict[str, object], dict[str, Image.Image]]:
    root = rom_root(disc)
    assets = discover_assets(disc)
    views = discover_views(disc, assets)
    source_data = {
        source: (root / source).read_bytes()
        for source in sorted({asset.source for asset in assets})
    }
    images: dict[str, Image.Image] = {}
    rows = []
    for view in views:
        image = _compose(view, source_data)
        images[view.path] = image
        rows.append(
            {
                "path": view.path,
                "layout": view.layout,
                "width": image.width,
                "height": image.height,
                "pixel_sha256": pixel_hash(image),
                "targets": [target.to_dict() for target in view.targets],
            }
        )
    document = {
        "version": 2,
        "disc": disc,
        "sources": {
            source: {"size": len(data), "sha256": _file_hash(data)}
            for source, data in source_data.items()
        },
        "images": rows,
    }
    return document, images


def _manifest_text(document: dict[str, object]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def load_manifest(disc: str) -> dict[str, object]:
    path = manifest_path(disc)
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("version") != 2 or document.get("disc") != disc:
        raise ValueError(f"{path}: unsupported or mismatched manifest")
    if not isinstance(document.get("sources"), dict) or not isinstance(
        document.get("images"), list
    ):
        raise ValueError(f"{path}: malformed manifest")
    return document


def _view_from_row(row: dict[str, object]) -> ImageView:
    targets = row.get("targets")
    if not isinstance(targets, list):
        raise ValueError("manifest image has no target list")
    return ImageView(
        str(row["path"]),
        str(row["layout"]),
        tuple(ImageAsset.from_dict(target) for target in targets),
    )


def _validate_catalog(disc: str, document: dict[str, object]) -> None:
    root = rom_root(disc)
    current = discover_views(disc, discover_assets(disc))
    rows = document["images"]
    assert isinstance(rows, list)
    stored = [_view_from_row(row) for row in rows]
    if stored != list(current):
        raise ValueError("image structure no longer matches the extraction manifest")
    sources = document["sources"]
    assert isinstance(sources, dict)
    for source, fingerprint in sources.items():
        path = root / source
        if not path.is_file() or path.stat().st_size != fingerprint["size"]:
            raise ValueError(f"{source}: source is missing or changed size")


def extract(disc: str, *, check: bool, overwrite: bool) -> tuple[int, int]:
    if check and overwrite:
        raise ValueError("--check and --overwrite cannot be combined")
    manifest = manifest_path(disc)
    originals = extracted_root(disc)
    if manifest.is_file() and not overwrite:
        document = load_manifest(disc)
        _validate_catalog(disc, document)
        images = None
    else:
        document, images = build_manifest(disc)

    rows = document["images"]
    assert isinstance(rows, list)
    for row in rows:
        view = _view_from_row(row)
        original_path = originals / view.path
        if images is not None:
            image = images[view.path]
            if not check:
                original_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(original_path)
        elif not original_path.is_file():
            raise ValueError(
                f"{original_path}: baseline is missing; restore the original ROM and "
                "run extract.py --overwrite"
            )
        with Image.open(original_path) as opened:
            if opened.size != view.size or pixel_hash(opened) != row["pixel_sha256"]:
                raise ValueError(f"{original_path}: baseline image is stale or edited")

    if not check and images is not None:
        originals.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            _manifest_text(document), encoding="utf-8", newline="\n"
        )
    return len(rows), len(changes(disc, document))


def changes(
    disc: str, document: dict[str, object]
) -> list[tuple[dict[str, object], ImageView, ReplacementImage]]:
    rows = document["images"]
    assert isinstance(rows, list)
    registered = {str(row["path"]).casefold(): row for row in rows}
    changed = []
    for replacement in load_replacements(disc):
        row = registered.get(replacement.view.casefold())
        if row is None:
            raise ValueError(
                f"{replacement.view}: Saturn binding is absent from the manifest"
            )
        view = _view_from_row(row)
        path = replacement.path
        with Image.open(path) as opened:
            if opened.size != replacement.size:
                raise ValueError(
                    f"{path}: got {opened.width}x{opened.height}, "
                    f"expected catalog size {replacement.width}x{replacement.height}"
                )
            if replacement.size != view.size:
                raise ValueError(
                    f"{replacement.asset}: catalog size does not match "
                    f"Saturn view {replacement.view}"
                )
            if pixel_hash(opened) != row["pixel_sha256"]:
                changed.append((row, view, replacement))
    return changed


def repack(
    disc: str, *, check: bool, list_only: bool
) -> tuple[int, int, int]:
    if check and list_only:
        raise ValueError("--check and --list cannot be combined")
    root = rom_root(disc)
    document = load_manifest(disc)
    _validate_catalog(disc, document)
    changed = changes(disc, document)
    by_source: dict[str, list[tuple[ImageAsset, Image.Image]]] = defaultdict(list)
    for _row, view, replacement in changed:
        with Image.open(replacement.path) as opened:
            pieces = _split(opened.copy(), view)
        for target, piece in zip(view.targets, pieces, strict=True):
            by_source[target.source].append((target, piece))

    for _row, view, _replacement in changed:
        print(f"changed  {view.path} ({len(view.targets)} target(s))")
    if list_only:
        return len(changed), sum(map(len, by_source.values())), len(by_source)

    sources = document["sources"]
    assert isinstance(sources, dict)
    for source, replacements in sorted(by_source.items()):
        path = root / source
        original = path.read_bytes()
        if len(original) != sources[source]["size"]:
            raise ValueError(f"{source}: source size changed since extraction")
        output = bytearray(original)
        for asset, image in replacements:
            if asset.encoding == "indexed8":
                adaptive_palette(output, asset, image)
            else:
                encode(output, asset, image)
        expected = bytes(output)
        if check:
            if expected != original:
                raise ValueError(
                    f"{source}: replacement images have not been repacked"
                )
        elif expected != original:
            path.write_bytes(expected)
            print(f"repacked {source} ({len(replacements)} image target(s))")
    return len(changed), sum(map(len, by_source.values())), len(by_source)
