"""Apply the checked PSP battle-console message-body offset patches."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.allegrex import encode_instruction
from ..core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from ..core.patching import Patch, apply_patches


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "battle_console.json"
TARGET = "BOOT.BIN"
OUTPUT_BODY_OFFSET = 0x400


@dataclass(frozen=True, slots=True)
class BattleConsoleBuild:
    data: bytes
    patches: tuple[Patch, ...]


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="battle_console.runtime",
        target_names={TARGET},
    )


def build_patches(
    body_offset: int,
    config: PatchRecipeConfiguration | None = None,
) -> tuple[Patch, ...]:
    """Compile the two declarative Allegrex immediate replacements."""

    if type(body_offset) is not int:
        raise TypeError("PSP BTL_MES body offset must be an integer")
    if body_offset != OUTPUT_BODY_OFFSET:
        raise ValueError(
            f"PSP BTL_MES body offset is {body_offset:#x}; "
            f"expected {OUTPUT_BODY_OFFSET:#x}"
        )
    configuration = config or _configuration()
    patches = []
    for recipe in configuration.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind != "instruction":
            raise ValueError(
                f"{recipe.group}/{recipe.name}: BTL_MES needs an instruction recipe"
            )
        assert replacement_recipe.instruction is not None
        replacement = encode_instruction(
            replacement_recipe.instruction,
            recipe.address,
        )
        if replacement[:2] != struct.pack("<H", body_offset):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: instruction body offset changed"
            )
        patches.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                replacement,
            )
        )
    if len(patches) != 2:
        raise ValueError("PSP BTL_MES patch inventory changed")
    return tuple(patches)


def _validate_source(stock: bytes, config: PatchRecipeConfiguration) -> None:
    target = config.targets[TARGET]
    if len(stock) != target.size:
        raise ValueError(f"PSP BOOT.BIN is {len(stock)} bytes; expected {target.size}")
    digest = hashlib.sha256(stock).hexdigest()
    if digest != target.stock_sha256:
        raise ValueError(
            f"PSP BOOT.BIN SHA-256 is {digest}; expected {target.stock_sha256}"
        )


def build_battle_console(
    stock: bytes,
    intermediate: bytes,
    body_offset: int,
) -> BattleConsoleBuild:
    """Apply BTL_MES after earlier, disjoint BOOT surfaces."""

    config = _configuration()
    _validate_source(stock, config)
    if not isinstance(intermediate, bytes) or len(intermediate) != len(stock):
        raise ValueError("PSP BTL_MES intermediate BOOT.BIN size changed")
    patches = build_patches(body_offset, config)
    output = apply_patches(
        intermediate,
        config.targets[TARGET].address_bias,
        patches,
    )
    return BattleConsoleBuild(output, patches)


__all__ = [
    "CONFIG_PATH",
    "OUTPUT_BODY_OFFSET",
    "BattleConsoleBuild",
    "build_battle_console",
    "build_patches",
]
