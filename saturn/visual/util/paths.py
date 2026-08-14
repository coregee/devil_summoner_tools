"""Paths owned by the Saturn visual package."""

from pathlib import Path

VISUAL_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = VISUAL_ROOT.parent
EXTRACTED_ROOT = VISUAL_ROOT / "extracted"
MODIFIED_ROOT = VISUAL_ROOT / "modified"
SPECIAL_VIEWS_PATH = VISUAL_ROOT / "util" / "special_views.json"

DISCS = ("game", "compendium")


def _disc_path(root: Path, disc: str) -> Path:
    if disc not in DISCS:
        raise ValueError(f"unsupported Saturn disc: {disc}")
    return root / disc


def rom_root(disc: str) -> Path:
    return _disc_path(SATURN_ROOT / "rom" / "extracted", disc)


def extracted_root(disc: str) -> Path:
    return _disc_path(EXTRACTED_ROOT, disc)


def modified_root(disc: str) -> Path:
    return _disc_path(MODIFIED_ROOT, disc)


def manifest_path(disc: str) -> Path:
    return modified_root(disc) / "manifest.json"
