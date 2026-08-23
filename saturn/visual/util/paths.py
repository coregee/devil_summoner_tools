"""Repository and platform paths consumed by the Saturn visual package."""

from pathlib import Path

VISUAL_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = VISUAL_ROOT.parent
REPOSITORY_ROOT = SATURN_ROOT.parent
IMAGE_ROOT = REPOSITORY_ROOT / "assets" / "image"
IMAGE_CATALOG_PATH = IMAGE_ROOT / "catalog.json"
EXTRACTED_ROOT = VISUAL_ROOT / "extracted"
MANIFEST_ROOT = VISUAL_ROOT / "modified"
BINDINGS_ROOT = VISUAL_ROOT / "bindings"
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


def manifest_path(disc: str) -> Path:
    return _disc_path(MANIFEST_ROOT, disc) / "manifest.json"


def bindings_path(disc: str) -> Path:
    return _disc_path(BINDINGS_ROOT, disc).with_suffix(".json")
