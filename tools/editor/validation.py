"""Evaluate proposed translations against known Saturn surface contracts."""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from saturn.font.util.codec import decode_glyph
from saturn.font.util.definitions import load_definition
from saturn.text.util.event_repack import FontMetrics
from saturn.text.util.surfaces import load_surfaces
from saturn.text.util.tokens import Named, Raw, Text, parse_tokens

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
        self._metrics: dict[str, FontMetrics | None] = {}

    def _font_metrics(self, font: str | None) -> FontMetrics | None:
        if font is None:
            return None
        if font not in self._metrics:
            path = FONT_GENERATED_ROOT / f"{font.upper()}_metrics.json"
            try:
                self._metrics[font] = FontMetrics.load(path)
            except ValueError:
                self._metrics[font] = None
        return self._metrics[font]

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
                width = metrics.measure(candidate)
                if current and width > limit:
                    text = " ".join(current)
                    output.append(MeasuredLine(text, metrics.measure(text)))
                    current = [word]
                else:
                    current.append(word)
            text = " ".join(current)
            output.append(MeasuredLine(text, metrics.measure(text)))
        return output

    @staticmethod
    def _measure_unwrapped(value: str, metrics: FontMetrics) -> list[MeasuredLine]:
        return [
            MeasuredLine(line, metrics.measure(line))
            for line in DraftEvaluator._explicit_lines(value)
        ]

    def evaluate(self, entry_id: str, translation: str) -> dict[str, Any]:
        if not isinstance(translation, str):
            raise ValueError("translation must be text")
        diagnostics: list[dict[str, Any]] = []
        try:
            self.catalog.candidate_document(entry_id, translation)
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
            metrics = self._font_metrics(layout.font)
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
                    lines = self._wrap(translation, metrics, layout.width.value or 0)
                elif metrics is not None:
                    lines = self._measure_unwrapped(translation, metrics)
                else:
                    lines = [
                        MeasuredLine(line, None)
                        for line in self._explicit_lines(translation)
                    ]
            except ValueError as error:
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
                    "rows": layout.rows,
                    "width": {"unit": layout.width.unit, "value": limit},
                    "lines": [
                        {"text": line.text, "width": line.width} for line in lines
                    ],
                    "pages": pages,
                    "exact": exact_wrap,
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
        metrics = self._font_metrics(font)
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
                        for glyph in metrics.segment(token.value):
                            mask = decode_glyph(data, definition.format, glyph.code)
                            mask = mask.point(lambda value: 255 if value else 0)
                            image.paste((235, 244, 231), (x, y), mask)
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
