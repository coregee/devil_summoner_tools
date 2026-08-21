"""Evaluate proposed translations against known Saturn surface contracts."""

from __future__ import annotations

import base64
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from saturn.font.util.codec import decode_glyph
from saturn.font.util.definitions import load_definition
from saturn.text.util.event_repack import FontMetrics, Glyph
from saturn.text.util.surfaces import load_surfaces
from saturn.text.util.tokens import Named, Raw, Text, parse_tokens, uppercase_text

from .catalog import PROJECT_ROOT, CorpusCatalog

FONT_ROOT = PROJECT_ROOT / "saturn" / "font"
FONT_CONFIG_ROOT = FONT_ROOT / "config" / "game"
FONT_GENERATED_ROOT = FONT_ROOT / "generated" / "game"


@dataclass(frozen=True, slots=True)
class MeasuredLine:
    text: str
    width: int | None


class DraftEvaluator:
    def __init__(self, catalog: CorpusCatalog) -> None:
        self.catalog = catalog
        self.surfaces = load_surfaces()
        self._metrics: dict[tuple[str, str], FontMetrics | None] = {}
        self._stock_font8: dict[str, dict[str, int]] | None = None

    def refresh_fonts(self) -> None:
        self._metrics.clear()
        self._stock_font8 = None

    def _font_metrics(
        self, font: str | None, alphabet: str = "replaced"
    ) -> FontMetrics | None:
        if font is None:
            return None
        key = (font, alphabet)
        if key not in self._metrics:
            path = FONT_GENERATED_ROOT / f"{font.upper()}_metrics.json"
            try:
                if font == "font8" and alphabet == "original":
                    document = json.loads(path.read_text(encoding="utf-8"))
                    rows = document["reference_sets"]["stock_latin"]
                    self._stock_font8 = {row["text"]: row for row in rows}
                    self._metrics[key] = FontMetrics(
                        document["font"],
                        tuple(
                            Glyph(
                                row["text"], row["code"], row["advance"], ()
                            )
                            for row in rows
                        ),
                    )
                else:
                    self._metrics[key] = FontMetrics.load(path)
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                self._metrics[key] = None
        return self._metrics[key]

    @staticmethod
    def _explicit_lines(value: str) -> list[str]:
        return value.replace("{n}", "\n").split("\n")

    @staticmethod
    def _wrap(value: str, metrics: FontMetrics, limit: int) -> list[MeasuredLine]:
        output: list[MeasuredLine] = []
        for explicit in DraftEvaluator._explicit_lines(value):
            words = [word for word in explicit.split(" ") if word]
            if not words:
                output.append(MeasuredLine("", 0))
                continue
            current: list[str] = []
            for word in words:
                candidate = " ".join((*current, word))
                width = metrics.measure_output(candidate)
                if current and width > limit:
                    text = " ".join(current)
                    output.append(MeasuredLine(text, metrics.measure_output(text)))
                    current = [word]
                else:
                    current.append(word)
            text = " ".join(current)
            output.append(MeasuredLine(text, metrics.measure_output(text)))
        return output

    @staticmethod
    def _measure_unwrapped(value: str, metrics: FontMetrics) -> list[MeasuredLine]:
        return [
            MeasuredLine(line, metrics.measure_output(line))
            for line in DraftEvaluator._explicit_lines(value)
        ]

    def evaluate(
        self,
        entry_id: str,
        translation: str,
        font8_alphabet: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(translation, str):
            raise ValueError("translation must be text")
        diagnostics: list[dict[str, Any]] = []
        try:
            self.catalog.candidate_document(
                entry_id, translation, font8_alphabet
            )
        except ValueError as error:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "asset_contract",
                    "message": str(error),
                    "surface": None,
                }
            )
            return {
                "valid": False,
                "diagnostics": diagnostics,
                "surfaces": [],
                "preview": None,
            }

        entry = self.catalog.entry(entry_id)
        alphabet = font8_alphabet or entry["font8_alphabet"]
        rendered_translation = (
            uppercase_text(translation)
            if alphabet == "original"
            else translation
        )
        surface_names = sorted(
            {
                item["surface"]
                for item in entry["consumers"]
                if item["surface"] is not None
            }
        )
        evaluations: list[dict[str, Any]] = []
        for surface_name in surface_names:
            surface = self.surfaces.surface(surface_name)
            layout = surface.en
            surface_alphabet = alphabet if layout.font == "font8" else "replaced"
            metrics = self._font_metrics(layout.font, surface_alphabet)
            surface_diagnostics: list[dict[str, Any]] = []
            lines: list[MeasuredLine]
            exact_wrap = (
                surface_name == "event.dialogue"
                and metrics is not None
                and layout.width.unit == "pixels"
                and layout.width.value is not None
            )
            try:
                if exact_wrap:
                    lines = self._wrap(
                        rendered_translation, metrics, layout.width.value or 0
                    )
                elif (
                    surface_name == "shop.inventory_label"
                    and surface_alphabet == "original"
                    and self._stock_font8 is not None
                ):
                    rows = [self._stock_font8[character] for character in rendered_translation]
                    lines = [
                        MeasuredLine(
                            rendered_translation,
                            sum(row["ink_right"] - row["ink_left"] for row in rows),
                        )
                    ]
                elif metrics is not None:
                    lines = self._measure_unwrapped(rendered_translation, metrics)
                else:
                    lines = [
                        MeasuredLine(line, None)
                        for line in self._explicit_lines(rendered_translation)
                    ]
            except (KeyError, ValueError) as error:
                lines = []
                surface_diagnostics.append(
                    {
                        "severity": "error",
                        "code": "font_encoding",
                        "message": str(error),
                        "surface": surface_name,
                    }
                )

            limit = layout.width.value
            if layout.width.unit == "pixels" and limit is not None:
                for index, line in enumerate(lines):
                    if line.width is not None and line.width > limit:
                        surface_diagnostics.append(
                            {
                                "severity": "error",
                                "code": "line_width",
                                "message": (
                                    f"Row {index + 1} uses {line.width}/{limit}px."
                                ),
                                "surface": surface_name,
                                "actual": line.width,
                                "limit": limit,
                                "unit": "pixels",
                            }
                        )
            elif not layout.width.known:
                surface_diagnostics.append(
                    {
                        "severity": "unknown",
                        "code": "unknown_width",
                        "message": (
                            "The English width for this surface is not yet mapped."
                        ),
                        "surface": surface_name,
                    }
                )

            pages = 1
            if layout.rows is not None and len(lines) > layout.rows:
                if surface_name == "event.dialogue":
                    pages = math.ceil(len(lines) / layout.rows)
                    surface_diagnostics.append(
                        {
                            "severity": "warning",
                            "code": "multiple_pages",
                            "message": f"The wrapped dialogue occupies {pages} pages.",
                            "surface": surface_name,
                        }
                    )
                else:
                    surface_diagnostics.append(
                        {
                            "severity": "error",
                            "code": "row_count",
                            "message": f"Text uses {len(lines)}/{layout.rows} rows.",
                            "surface": surface_name,
                            "actual": len(lines),
                            "limit": layout.rows,
                            "unit": "rows",
                        }
                    )
            if metrics is None and layout.font is not None:
                surface_diagnostics.append(
                    {
                        "severity": "unknown",
                        "code": "missing_metrics",
                        "message": (
                            f"Generated {layout.font.upper()} metrics are unavailable."
                        ),
                        "surface": surface_name,
                    }
                )
            diagnostics.extend(surface_diagnostics)
            evaluations.append(
                {
                    "name": surface_name,
                    "font": layout.font,
                    "font8_alphabet": (
                        alphabet if layout.font == "font8" else None
                    ),
                    "rows": layout.rows,
                    "width": {"unit": layout.width.unit, "value": limit},
                    "lines": [
                        {"text": line.text, "width": line.width} for line in lines
                    ],
                    "pages": pages,
                    "exact": exact_wrap
                    or (
                        surface_name == "shop.inventory_label"
                        and surface_alphabet == "original"
                    ),
                    "diagnostics": surface_diagnostics,
                }
            )

        if not surface_names:
            diagnostics.append(
                {
                    "severity": "unknown",
                    "code": "unmapped_consumer",
                    "message": "This field has no mapped Saturn surface.",
                    "surface": None,
                }
            )

        preview = self._preview(evaluations[0]) if evaluations else None
        return {
            "valid": not any(row["severity"] == "error" for row in diagnostics),
            "diagnostics": diagnostics,
            "surfaces": evaluations,
            "preview": preview,
        }

    def _preview(self, evaluation: dict[str, Any]) -> dict[str, Any] | None:
        font = evaluation["font"]
        if font is None or not evaluation["lines"]:
            return None
        metrics = self._font_metrics(
            font, evaluation.get("font8_alphabet") or "replaced"
        )
        data_path = FONT_GENERATED_ROOT / f"{font.upper()}.FON"
        config_path = FONT_CONFIG_ROOT / f"{font}.json"
        if metrics is None or not data_path.is_file() or not config_path.is_file():
            return None
        definition = load_definition(config_path, "game")
        data = data_path.read_bytes()
        image = Image.new("RGB", (352, 224), (7, 9, 12))
        draw = ImageDraw.Draw(image)
        is_event = evaluation["name"] == "event.dialogue"
        width = evaluation["width"]["value"] or 300
        rows = evaluation["rows"] or min(3, len(evaluation["lines"]))
        box_width = min(332, width + 20)
        box_height = max(32, rows * 16 + 20)
        left = (352 - box_width) // 2
        top = 224 - box_height - 10 if is_event else (224 - box_height) // 2
        draw.rectangle(
            (left, top, left + box_width, top + box_height), fill=(10, 37, 34)
        )
        draw.rectangle(
            (left + 2, top + 2, left + box_width - 2, top + box_height - 2),
            outline=(77, 131, 111),
        )
        content_left = left + 10
        content_top = top + 10
        draw.rectangle(
            (
                content_left,
                content_top,
                content_left + width - 1,
                content_top + rows * 16 - 1,
            ),
            outline=(51, 94, 82),
        )
        glyphs = metrics.by_text
        for row_index, row in enumerate(evaluation["lines"][:rows]):
            x = content_left
            y = content_top + row_index * 16
            try:
                tokens = parse_tokens(row["text"])
                for token in tokens:
                    if isinstance(token, Text):
                        segmented = metrics.segment_output(token.value)
                        compact = (
                            evaluation["name"] == "shop.inventory_label"
                            and evaluation.get("font8_alphabet") == "original"
                            and self._stock_font8 is not None
                        )
                        if compact and segmented:
                            x -= self._stock_font8[segmented[0].text]["ink_left"]
                        for index, glyph in enumerate(segmented):
                            mask = decode_glyph(data, definition.format, glyph.code)
                            mask = mask.point(lambda value: 255 if value else 0)
                            image.paste((235, 244, 231), (x, y), mask)
                            if compact and index + 1 < len(segmented):
                                current = self._stock_font8[glyph.text]
                                following = self._stock_font8[segmented[index + 1].text]
                                x += current["ink_right"] - following["ink_left"]
                            else:
                                x += glyph.advance
                    elif isinstance(token, (Named, Raw)):
                        draw.rectangle(
                            (x, y + 2, x + 77, y + 13),
                            outline=(218, 178, 94),
                        )
                        x += 80
            except ValueError:
                continue
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return {
            "data_url": "data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode("ascii"),
            "width": 352,
            "height": 224,
            "surface": evaluation["name"],
            "fidelity": "exact-font" if evaluation["exact"] else "surface",
        }
