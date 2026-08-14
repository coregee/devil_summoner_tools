"""Path validation shared by CUE, extraction, and rebuilding code."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def safe_relative_path(value: str, label: str) -> Path:
    """Return a normalized relative path and reject traversal or drive syntax."""
    if not value or "\x00" in value:
        raise ValueError(f"{label} must be nonempty text")

    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{label} must be relative: {value!r}")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"{label} contains an unsafe component: {value!r}")
    return Path(*posix.parts)


def contained_path(root: Path, relative: Path, label: str) -> Path:
    root = root.resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError(f"{label} escapes {root}: {relative}")
    return result


def relative_key(path: Path) -> str:
    return path.as_posix().casefold()
