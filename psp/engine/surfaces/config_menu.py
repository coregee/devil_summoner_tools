"""Compose the checked PSP CONFIG runtime into the engine output."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable
from dataclasses import dataclass

from psp.text.util.assets import load_config_asset

from ..core.patching import Patch, apply_patches
from .config_menu_runtime import (
    ConfigMenuPatchSource,
    PatchWrite,
    build_config_menu_patch,
)


BOOT_SIZE = 2_404_599
BOOT_STOCK_SHA256 = (
    "37b5b7a49fe1a5af60ab042d2822befb00580e02a7d7d2ed77dd279ebe6f55fa"
)
ADDRESS_BIAS = 0x80
WRITE_COUNT = 45
WRITE_FINGERPRINT = (
    "69161b6092657273a92d656b8b294100e743c7e3b9027ade6f891cd4c187d039"
)


@dataclass(frozen=True, slots=True)
class ConfigMenuBuild:
    data: bytes
    patches: tuple[Patch, ...]
    runtime_used_size: int


def _source() -> ConfigMenuPatchSource:
    grouped: dict[str, list[str]] = {}
    for role, _key, _reference, translation in load_config_asset():
        grouped.setdefault(role, []).append(translation)
    return ConfigMenuPatchSource(
        labels=tuple(grouped["label"]),
        actions=tuple(grouped["action"]),
        orientations=tuple(grouped["orientation"]),
        speeds=tuple(grouped["speed"]),
        sizes=tuple(grouped["size"]),
        frames=tuple(grouped["frame"]),
        secondary_help=grouped["secondary_help"][0],
        modes=tuple(grouped["mode"]),
    )


def _mapping(rows: object, face: str) -> tuple[dict[str, int], dict[str, int]]:
    if not isinstance(rows, list):
        raise ValueError(f"PSP CONFIG {face} font mapping is invalid")
    codes: dict[str, int] = {}
    advances: dict[str, int] = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"character", "code", "advance"}
            or not isinstance(row["character"], str)
            or len(row["character"]) != 1
            or type(row["code"]) is not int
            or type(row["advance"]) is not int
        ):
            raise ValueError(f"PSP CONFIG {face} font mapping is invalid")
        character = row["character"]
        if character in codes:
            raise ValueError(f"PSP CONFIG {face} font mapping is not unique")
        codes[character] = row["code"]
        advances[character] = row["advance"]
    return codes, advances


def _fingerprint(writes: Iterable[PatchWrite]) -> str:
    digest = hashlib.sha256()
    for write in writes:
        name = write.name.encode("utf-8")
        digest.update(struct.pack("<I", len(name)))
        digest.update(name)
        digest.update(struct.pack("<II", write.address, len(write.data)))
        digest.update(write.data)
    return digest.hexdigest()


def build_config_menu(
    stock: bytes,
    intermediate: bytes,
    font_contract: dict[str, object],
) -> ConfigMenuBuild:
    """Apply CONFIG after earlier disjoint engine surfaces."""

    if (
        len(stock) != BOOT_SIZE
        or hashlib.sha256(stock).hexdigest() != BOOT_STOCK_SHA256
    ):
        raise ValueError("PSP CONFIG BOOT.BIN source contract changed")
    if len(intermediate) != len(stock):
        raise ValueError("PSP CONFIG intermediate BOOT.BIN size changed")
    ark12_codes, ark12_advances = _mapping(font_contract.get("ark12"), "Ark12")
    ark16_codes, ark16_advances = _mapping(font_contract.get("ark16"), "Ark16")
    first_code = font_contract.get("ark16_advance_first_code")
    draw_limit = font_contract.get("required_draw_code_limit")
    if type(first_code) is not int or type(draw_limit) is not int:
        raise ValueError("PSP CONFIG font limits are invalid")
    runtime = build_config_menu_patch(
        _source(),
        ark16_codes,
        ark16_advances,
        ark12_codes,
        ark12_advances,
        ark16_advance_first_code=first_code,
        draw_code_limit=draw_limit,
    )
    if (
        len(runtime.writes) != WRITE_COUNT
        or _fingerprint(runtime.writes) != WRITE_FINGERPRINT
    ):
        raise ValueError("PSP CONFIG runtime emitter contract changed")
    patches = tuple(
        Patch(
            "config_menu.ui",
            write.name,
            write.address,
            stock[
                write.address + ADDRESS_BIAS :
                write.address + ADDRESS_BIAS + len(write.data)
            ],
            write.data,
        )
        for write in runtime.writes
    )
    output = apply_patches(intermediate, ADDRESS_BIAS, patches)
    runtime_names = {
        "config_main_draw_wrapper",
        "config_main_descriptors",
        "config_ark16_widths",
        "config_main_records",
    }
    used = sum(
        len(write.data) for write in runtime.writes if write.name in runtime_names
    )
    return ConfigMenuBuild(output, patches, used)


__all__ = [
    "ConfigMenuBuild",
    "WRITE_COUNT",
    "WRITE_FINGERPRINT",
    "build_config_menu",
]
