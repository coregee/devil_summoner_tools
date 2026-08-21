"""Composition root for the translation editor."""

from __future__ import annotations

from .catalog import CorpusCatalog
from .validation import DraftEvaluator


class EditorApplication:
    def __init__(self, catalog: CorpusCatalog | None = None) -> None:
        self.catalog = catalog or CorpusCatalog()
        self.evaluator = DraftEvaluator(self.catalog)

    def evaluate(self, entry_id: str, translation: str) -> dict[str, object]:
        return self.evaluator.evaluate(entry_id, translation)

    def save(
        self, entry_id: str, translation: str, base_hash: str
    ) -> dict[str, object]:
        evaluation = self.evaluate(entry_id, translation)
        if not evaluation["valid"]:
            raise ValueError("Known validation errors must be fixed before saving.")
        entry = self.catalog.save(entry_id, translation, base_hash)
        return {"entry": entry, "evaluation": self.evaluate(entry_id, translation)}

