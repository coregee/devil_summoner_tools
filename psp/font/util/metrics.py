"""Generate checked runtime advances from the PSP title-help source face."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = FONT_ROOT / "config" / "title_help_metrics.json"
PACKED_WIDTH_COUNT = 95
CANVAS_SIZE = 64
CELL_ORIGIN = 24
CELL_HEIGHT = 16


@dataclass(frozen=True, slots=True)
class TitleHelpMetricConfig:
    provider_path: Path
    provider_sha256: str
    size: int
    baseline: int
    antialias: bool
    space_advance: int
    maximum_advance: int
    owned_characters: frozenset[str]
    fallback_storage_order: bytes


def _packed_storage_index(character: str) -> int:
    code = ord(character)
    if character == " ":
        return PACKED_WIDTH_COUNT - 1
    if 0x30 <= code <= 0x7E:
        return code - 0x30
    if 0x21 <= code <= 0x2F:
        return code + 0x2E
    raise ValueError(f"character is outside printable ASCII: {character!r}")


def _load_config(path: Path = CONFIG_PATH) -> TitleHelpMetricConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid title-help metric config: {path}") from error
    if not isinstance(document, dict) or set(document) != {
        "version",
        "id",
        "provider",
        "contract",
        "fallback",
    }:
        raise ValueError(f"{path}: invalid root fields")
    provider = document["provider"]
    contract = document["contract"]
    fallback = document["fallback"]
    if (
        document["version"] != 1
        or document["id"] != "title_help_metrics"
        or not isinstance(provider, dict)
        or set(provider)
        != {
            "source",
            "sha256",
            "size",
            "baseline",
            "antialias",
            "layout_engine",
        }
        or not isinstance(contract, dict)
        or set(contract)
        != {
            "character_first",
            "character_last",
            "space_advance",
            "maximum_advance",
            "visible_advance_rule",
            "storage_order",
            "owned_characters",
        }
        or not isinstance(fallback, dict)
        or set(fallback) != {"kind", "sha256", "storage_order"}
    ):
        raise ValueError(f"{path}: unsupported title-help metric contract")
    source = provider["source"]
    digest = provider["sha256"]
    if (
        not isinstance(source, str)
        or not source
        or not isinstance(digest, str)
        or len(digest) != 64
        or provider["size"] != 12
        or provider["baseline"] != 13
        or provider["antialias"] is not False
        or provider["layout_engine"] != "basic"
        or contract["character_first"] != 32
        or contract["character_last"] != 126
        or contract["space_advance"] != 4
        or contract["maximum_advance"] != 14
        or contract["visible_advance_rule"] != "min(ink_width + 1, 14)"
        or contract["storage_order"] != "psp_packed_printable_ascii"
    ):
        raise ValueError(f"{path}: title-help metric geometry changed")
    owned = contract["owned_characters"]
    fallback_values = fallback["storage_order"]
    if (
        not isinstance(owned, str)
        or not owned
        or len(set(owned)) != len(owned)
        or any(not 32 <= ord(character) <= 126 for character in owned)
        or fallback["kind"] != "ported_eve_runtime_advances"
        or not isinstance(fallback_values, list)
        or len(fallback_values) != PACKED_WIDTH_COUNT
        or any(
            type(value) is not int or not 1 <= value <= 255
            for value in fallback_values
        )
    ):
        raise ValueError(f"{path}: invalid title-help fallback metrics")
    fallback_bytes = bytes(fallback_values)
    fallback_digest = hashlib.sha256(fallback_bytes).hexdigest()
    if fallback_digest != fallback["sha256"]:
        raise ValueError(
            f"title-help fallback SHA-256 is {fallback_digest}; "
            f"expected {fallback['sha256']}"
        )
    provider_path = (path.parent / source).resolve()
    return TitleHelpMetricConfig(
        provider_path,
        digest,
        provider["size"],
        provider["baseline"],
        provider["antialias"],
        contract["space_advance"],
        contract["maximum_advance"],
        frozenset(owned),
        fallback_bytes,
    )


def _font(config: TitleHelpMetricConfig) -> ImageFont.FreeTypeFont:
    try:
        source = config.provider_path.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(
            f"title-help typeface is missing: {config.provider_path}"
        ) from error
    digest = hashlib.sha256(source).hexdigest()
    if digest != config.provider_sha256:
        raise ValueError(
            f"title-help typeface SHA-256 is {digest}; "
            f"expected {config.provider_sha256}"
        )
    try:
        return ImageFont.truetype(
            str(config.provider_path),
            config.size,
            layout_engine=ImageFont.Layout.BASIC,
        )
    except OSError as error:
        raise ValueError("could not load the title-help typeface") from error


def _advance(
    character: str,
    font: ImageFont.FreeTypeFont,
    config: TitleHelpMetricConfig,
) -> tuple[int, tuple[int, int, int, int] | None]:
    if character == " ":
        return config.space_advance, None
    canvas = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L" if config.antialias else "1"
    draw.text(
        (CELL_ORIGIN, CELL_ORIGIN + config.baseline),
        character,
        font=font,
        fill=255,
        anchor="ls",
    )
    bounds = canvas.getbbox()
    if bounds is None:
        raise ValueError(f"title-help typeface rendered {character!r} blank")
    left, top, right, bottom = bounds
    if top < CELL_ORIGIN or bottom > CELL_ORIGIN + CELL_HEIGHT:
        raise ValueError(f"title-help glyph {character!r} clips vertically")
    width = right - left
    return min(width + 1, config.maximum_advance), (
        0,
        top - CELL_ORIGIN,
        width,
        bottom - CELL_ORIGIN,
    )


def _mask(
    character: str,
    font: ImageFont.FreeTypeFont,
    config: TitleHelpMetricConfig,
) -> tuple[bytes, int, tuple[int, int, int, int] | None]:
    if character == " ":
        return bytes(CELL_HEIGHT * CELL_HEIGHT), config.space_advance, None
    canvas = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L" if config.antialias else "1"
    draw.text(
        (CELL_ORIGIN, CELL_ORIGIN + config.baseline),
        character,
        font=font,
        fill=255,
        anchor="ls",
    )
    bounds = canvas.getbbox()
    if bounds is None:
        raise ValueError(f"title-help typeface rendered {character!r} blank")
    left, top, right, bottom = bounds
    if top < CELL_ORIGIN or bottom > CELL_ORIGIN + CELL_HEIGHT:
        raise ValueError(f"title-help glyph {character!r} clips vertically")
    width = right - left
    strip = canvas.crop((left, CELL_ORIGIN, right, CELL_ORIGIN + CELL_HEIGHT))
    cell = Image.new("L", (CELL_HEIGHT, CELL_HEIGHT), 0)
    cell.paste(strip, (0, 0))
    coverage = bytes(cell.tobytes())
    if set(coverage) - {0, 255}:
        raise ValueError(f"title-help glyph {character!r} is antialiased")
    return coverage, min(width + 1, config.maximum_advance), (
        0,
        top - CELL_ORIGIN,
        width,
        bottom - CELL_ORIGIN,
    )


def render_title_help_masks(characters: str) -> dict[str, dict[str, object]]:
    """Render Ark Pixel 12 masks in the checked PSP FONT16 geometry."""

    plan = _load_config()
    if len(set(characters)) != len(characters):
        raise ValueError("Ark Pixel 12 mask characters are duplicated")
    font = _font(plan)
    output: dict[str, dict[str, object]] = {}
    for character in characters:
        coverage, advance, bounds = _mask(character, font, plan)
        output[character] = {
            "coverage": coverage,
            "advance": advance,
            "bounds": bounds,
        }
    return output


def build_title_help_masks(characters: str) -> dict[str, dict[str, object]]:
    """Render the exact FONT16 masks consumed by the title-help publisher."""

    plan = _load_config()
    if set(characters) != plan.owned_characters:
        raise ValueError("title-help raster ownership differs from its metric contract")
    return render_title_help_masks(characters)


def build_title_help_metrics(
    config: TitleHelpMetricConfig | None = None,
) -> dict[str, object]:
    plan = config or _load_config()
    font = _font(plan)
    storage = list(plan.fallback_storage_order)
    glyphs: list[dict[str, object]] = []
    for code in range(32, 127):
        character = chr(code)
        index = _packed_storage_index(character)
        raster_advance, bounds = _advance(character, font, plan)
        owned = character in plan.owned_characters
        if owned:
            storage[index] = raster_advance
        glyphs.append(
            {
                "character": character,
                "code": code,
                "storage_index": index,
                "advance": storage[index],
                "title_raster_advance": raster_advance,
                "owned": owned,
                "bounds": None if bounds is None else list(bounds),
            }
        )
    if any(not 1 <= value <= plan.maximum_advance for value in storage):
        raise ValueError("title-help metric table is incomplete")
    return {
        "version": 1,
        "id": "title_help_metrics",
        "provider_sha256": plan.provider_sha256,
        "storage_order": storage,
        "glyphs": glyphs,
    }


def metric_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
