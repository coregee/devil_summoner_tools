"""Route the shared font workspace to platform-owned services."""

from __future__ import annotations

from typing import Any

from .catalog import CorpusCatalog
from .fonts import FontService as SaturnFontService
from .languages import LanguageService
from .psp_fonts import PspFontService


class FontCatalogService:
    def __init__(self, corpus: CorpusCatalog, languages: LanguageService) -> None:
        self.saturn = SaturnFontService(corpus, languages)
        self.psp = PspFontService(languages)

    def _service(self, font_id: str) -> Any:
        return self.psp if font_id.startswith("psp/") else self.saturn

    def inventory(self, language_id: str = "en") -> dict[str, Any]:
        saturn = self.saturn.inventory(language_id)
        psp = self.psp.inventory(language_id)
        return {"fonts": saturn["fonts"] + psp["fonts"], "language": language_id}

    def detail(self, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).detail(font_id, *args, **kwargs)

    def update_plan(self, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).update_plan(font_id, *args, **kwargs)

    def apply_update(self, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).apply_update(font_id, *args, **kwargs)

    def import_typeface(self, language_id: str, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).import_typeface(language_id, font_id, *args, **kwargs)

    def save_source_value(self, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).save_source_value(font_id, *args, **kwargs)

    def remap(self, font_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(font_id).remap(font_id, *args, **kwargs)

