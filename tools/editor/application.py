"""Composition root for the translation editor."""

from __future__ import annotations

from .catalog import CorpusCatalog
from .fonts import FontService
from .languages import LanguageService
from .validation import DraftEvaluator


class EditorApplication:
    def __init__(
        self,
        catalog: CorpusCatalog | None = None,
        languages: LanguageService | None = None,
    ) -> None:
        self.catalog = catalog or CorpusCatalog()
        self.languages = languages or LanguageService()
        self.evaluator = DraftEvaluator(self.catalog)
        self.fonts = FontService(self.catalog, self.languages)

    def evaluate(
        self,
        entry_id: str,
        translation: str,
        font8_alphabet: str | None = None,
    ) -> dict[str, object]:
        return self.evaluator.evaluate(entry_id, translation, font8_alphabet)

    def save(
        self,
        entry_id: str,
        translation: str,
        base_hash: str,
        font8_alphabet: str | None = None,
    ) -> dict[str, object]:
        evaluation = self.evaluate(entry_id, translation, font8_alphabet)
        if not evaluation["valid"]:
            raise ValueError("Known validation errors must be fixed before saving.")
        entry = self.catalog.save(
            entry_id, translation, base_hash, font8_alphabet
        )
        return {
            "entry": entry,
            "evaluation": self.evaluate(
                entry_id, translation, entry["font8_alphabet"]
            ),
        }

    def remap_font(
        self,
        font_id: str,
        code: int,
        replacement: str,
        base_hash: str,
        *,
        language_id: str,
        confirm_used: bool,
    ) -> dict[str, object]:
        detail = self.fonts.remap(
            font_id,
            code,
            replacement,
            base_hash,
            language_id=language_id,
            confirm_used=confirm_used,
        )
        self.evaluator.refresh_fonts()
        return detail

    def save_font_source(
        self,
        font_id: str,
        code: int,
        source_value: str,
        base_hash: str,
    ) -> dict[str, object]:
        result = self.fonts.save_source_value(
            font_id, code, source_value, base_hash
        )
        self.evaluator.refresh_fonts()
        return result
