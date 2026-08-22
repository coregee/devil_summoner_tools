"""Read-only font views over the positional glyph rasters in TITLE.BIN."""

from __future__ import annotations

import base64
import hashlib
import io
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from saturn.visual.util.catalog import (
    TITLE_MENU_GLYPHS,
    TITLE_PRESS_START_GLYPHS,
)
from saturn.visual.util.codec import decode
from saturn.visual.util.model import ImageAsset

from .catalog import PROJECT_ROOT, CorpusCatalog
from .languages import LanguageService

TITLE_BIN_PATH = (
    PROJECT_ROOT / "saturn" / "rom" / "extracted" / "game" / "TITLE.BIN"
)
EXTRACTED_ROOT = PROJECT_ROOT / "saturn" / "visual" / "extracted" / "game"
MODIFIED_ROOT = PROJECT_ROOT / "saturn" / "visual" / "modified" / "game"
CATALOG_PATH = PROJECT_ROOT / "saturn" / "visual" / "util" / "catalog.py"


@dataclass(frozen=True)
class VisualFont:
    id: str
    stem: str
    name: str
    description: str
    assets: tuple[ImageAsset, ...]
    characters: str
    surfaces: tuple[str, ...]

    @property
    def height(self) -> int:
        return max(asset.height for asset in self.assets)

    @property
    def width(self) -> int:
        return max(asset.width for asset in self.assets)


VISUAL_FONTS = (
    VisualFont(
        "game/title_prompt",
        "title_prompt",
        "TITLE Prompt - PRESS START BUTTON Raster",
        (
            "Sixteen positional 16x12 RGB555 glyph records in TITLE.BIN. The ten "
            "distinct stock capitals are fully mapped; no unused physical cells or "
            "complete PSP alphabet exist."
        ),
        TITLE_PRESS_START_GLYPHS,
        "PRESSSTARTBUTTON",
        ("title.press_start",),
    ),
    VisualFont(
        "game/title_menu",
        "title_menu",
        "TITLE Menu - START / OPTION Raster",
        (
            "Eleven positional RGB555 glyph records for START and OPTION. Most "
            "cells are 16x9; the I cell is 8x9. These are image records rather "
            "than a conventional .FON resource."
        ),
        TITLE_MENU_GLYPHS,
        "STARTOPTION",
        ("title.menu_start", "title.menu_option"),
    ),
)


def _data_url(image: Image.Image) -> str:
    scale = max(1, 64 // max(image.size))
    rendered = image.convert("RGB").resize(
        (image.width * scale, image.height * scale), Image.Resampling.NEAREST
    )
    output = io.BytesIO()
    rendered.save(output, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(
        "ascii"
    )


class VisualFontService:
    """Expose visual-package glyph runs through the shared Fonts workspace."""

    def __init__(self, corpus: CorpusCatalog, languages: LanguageService) -> None:
        self.corpus = corpus
        self.languages = languages

    @staticmethod
    def handles(font_id: str) -> bool:
        return any(font.id == font_id for font in VISUAL_FONTS)

    @staticmethod
    def _definition(font_id: str) -> VisualFont:
        try:
            return next(font for font in VISUAL_FONTS if font.id == font_id)
        except StopIteration as error:
            raise ValueError("unknown Saturn visual font") from error

    @staticmethod
    def _source_data() -> bytes | None:
        return TITLE_BIN_PATH.read_bytes() if TITLE_BIN_PATH.is_file() else None

    @classmethod
    def _image(
        cls, asset: ImageAsset, *, modified: bool = False
    ) -> Image.Image | None:
        if modified:
            path = MODIFIED_ROOT / asset.image
            if path.is_file():
                with Image.open(path) as opened:
                    return opened.convert("RGB")
            return None
        path = EXTRACTED_ROOT / asset.image
        if path.is_file():
            with Image.open(path) as opened:
                return opened.convert("RGB")
        data = cls._source_data()
        if data is not None:
            return decode(data, asset)
        return None

    @classmethod
    def _atlas(
        cls, definition: VisualFont, *, modified: bool = False
    ) -> str | None:
        images = [
            cls._image(asset, modified=modified) for asset in definition.assets
        ]
        if modified and not any(image is not None for image in images):
            return None
        if not any(image is not None for image in images):
            return None
        columns = 8
        rows = (len(images) + columns - 1) // columns
        atlas = Image.new(
            "RGB",
            (columns * definition.width, rows * definition.height),
            "black",
        )
        for index, image in enumerate(images):
            if image is None and modified:
                image = cls._image(definition.assets[index])
            if image is not None:
                atlas.paste(
                    image,
                    (
                        (index % columns) * definition.width,
                        (index // columns) * definition.height,
                    ),
                )
        return _data_url(atlas)

    def inventory(self, language_id: str = "en") -> dict[str, Any]:
        self.languages.detail(language_id)
        available = self._source_data() is not None or EXTRACTED_ROOT.is_dir()
        rows = []
        for definition in VISUAL_FONTS:
            rows.append(
                {
                    "id": definition.id,
                    "platform": "saturn",
                    "disc": "game",
                    "name": definition.name,
                    "file": "TITLE.BIN",
                    "cell": {
                        "width": definition.width,
                        "height": definition.height,
                        "bpp": 16,
                    },
                    "editable_slots": 0,
                    "physical_slots": len(definition.assets),
                    "known_slots": len(definition.assets),
                    "suggested_slots": 0,
                    "unknown_slots": 0,
                    "surface_count": len(definition.surfaces),
                    "source": None,
                    "generated": False,
                    "customized": False,
                    "available": available,
                }
            )
        return {"fonts": rows, "language": language_id}

    def detail(
        self,
        font_id: str,
        language_id: str = "en",
        *,
        offset: int = 0,
        limit: int = 200,
        query: str = "",
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 300:
            raise ValueError("invalid glyph page")
        self.languages.detail(language_id)
        definition = self._definition(font_id)
        audit = self.corpus.font_usage_audit(
            font_id, set(definition.characters), set(definition.characters)
        )
        usage: Counter[str] = audit["required"]
        needle = query.strip().casefold()
        matching = [
            code
            for code, (asset, character) in enumerate(
                zip(definition.assets, definition.characters, strict=True)
            )
            if not needle
            or needle
            in f"{code} 0x{code:04x} 0x{asset.offset:05x} {character}".casefold()
        ]
        slots = []
        for code in matching[offset : offset + limit]:
            asset = definition.assets[code]
            character = definition.characters[code]
            original = self._image(asset)
            replacement = self._image(asset, modified=True)
            current = replacement or original
            slots.append(
                {
                    "code": code,
                    "code_label": f"slot {code:02d} · 0x{asset.offset:05X}",
                    "original": character,
                    "source_value": character,
                    "source_status": "defined",
                    "can_edit_source": False,
                    "replacement": None,
                    "can_edit_render": False,
                    "usage": usage[character],
                    "original_image": (
                        _data_url(original) if original is not None else None
                    ),
                    "modified_image": (
                        _data_url(current) if current is not None else None
                    ),
                    "image": _data_url(current) if current is not None else None,
                    "record_offset": asset.offset,
                    "record_width": asset.width,
                    "record_height": asset.height,
                    "visual_path": asset.image,
                }
            )
        digest = hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
        return {
            "id": definition.id,
            "platform": "saturn",
            "disc": "game",
            "context": "Saturn game disc · TITLE.BIN visual glyphs",
            "name": definition.name,
            "file": "TITLE.BIN",
            "description": definition.description,
            "cell": {
                "width": definition.width,
                "height": definition.height,
                "bpp": 16,
            },
            "source": None,
            "slots": slots,
            "slot_page": {
                "offset": offset,
                "limit": limit,
                "total": len(matching),
                "physical": len(definition.assets),
            },
            "slot_counts": {
                "defined": len(definition.assets),
                "suggested": 0,
                "unknown": 0,
                "replaceable": 0,
            },
            "characters": sorted(set(definition.characters)),
            "surfaces": list(definition.surfaces),
            "config_hash": digest,
            "source_hash": digest,
            "language": language_id,
            "customized": False,
            "can_import": False,
            "can_edit": False,
            "can_rebuild": False,
            "available": (
                self._source_data() is not None or EXTRACTED_ROOT.is_dir()
            ),
            "atlases": {
                "original": self._atlas(definition),
                "modified": self._atlas(definition, modified=True),
            },
        }

    @staticmethod
    def _locked() -> None:
        raise ValueError(
            "TITLE.BIN glyph generation is locked until a profile-specific "
            "positional renderer is implemented."
        )

    def update_plan(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def apply_update(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def import_typeface(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def save_source_value(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()

    def remap(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._locked()
