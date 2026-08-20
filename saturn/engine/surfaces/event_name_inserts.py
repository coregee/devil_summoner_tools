"""Compose generated player-name rows into EVENT.BIN's non-dialogue menus."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipe,
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
    resolve_recipe_expected,
)
from engine.core.patching import Patch, apply_patches
from engine.core.sh2 import AssemblyError, assemble
from engine.shared.player_name_adapters import (
    PlayerNameAdapterSpec,
    build_player_name_assembly,
    pointer_contract,
)
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "event_name_inserts.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"
PLAYER_NAMES_PATH = ENGINE_ROOT / "shared" / "player_names.py"

TARGET = "EVENT.BIN"
LOAD_ADDRESS = 0x06020000
RUNTIME_ADDRESS = 0x06030BB4
RUNTIME_CAPACITY = 96
RUNTIME_USED_SIZE = 86

MENU_BLITTER_POINTER = 0x06030D20
ORIGINAL_BLITTER = 0x0602BCC0
STOCK_ADVANCE = 0x06076754
RAW_MENU_CONTINUE = 0x06030CDA
CODENAME_CONTINUE = 0x0602C49E
POINTER_CONTRACT = pointer_contract()
ADAPTER_SPEC = PlayerNameAdapterSpec(
    "EVENT",
    0x0602C44C,
    CODENAME_CONTINUE,
    RUNTIME_ADDRESS,
    RUNTIME_CAPACITY,
    MENU_BLITTER_POINTER,
    ORIGINAL_BLITTER,
    STOCK_ADVANCE,
    (0x06030C66, 0x06030C98),
    RAW_MENU_CONTINUE,
)


@dataclass(frozen=True, slots=True)
class EventNameInsertsBuild:
    data: bytes
    patches: tuple[Patch, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="event.name_inserts",
        target_names={TARGET},
        input_names=set(),
    )


def _stock_source() -> bytes:
    catalog = load_catalog()
    try:
        game = catalog["game"]
    except KeyError as error:
        raise ValueError("disc catalog has no game source") from error
    return read_source_files(
        validate_source(game, verify_hashes=False), (TARGET,)
    )[TARGET]


def _validate_sources(
    config: PatchRecipeConfiguration,
    stock: bytes,
    base: bytes,
) -> None:
    contract = config.targets[TARGET]
    if (
        contract.load_address != LOAD_ADDRESS
        or len(stock) != contract.size
        or _sha256(stock) != contract.stock_sha256
    ):
        raise ValueError("EVENT.BIN does not match the configured name-insert target")
    if len(base) != contract.size:
        raise ValueError("composed EVENT.BIN has the wrong size")


def _only_source(recipe: PatchRecipe, expected: str) -> Path:
    sources = recipe.replacement.sources
    if (
        len(sources) != 1
        or sources[0].relative_to(ASSEMBLY_ROOT).as_posix() != expected
    ):
        raise ValueError(f"{recipe.group}/{recipe.name}: assembly source changed")
    return sources[0]


def _instruction(recipe: PatchRecipe) -> bytes:
    source = recipe.replacement.instruction
    assert source is not None
    try:
        result = assemble(source, recipe.address)
    except AssemblyError as error:
        raise ValueError(f"{recipe.group}/{recipe.name}: {error}") from error
    if result.warnings or len(result.data) != len(recipe.expected):
        raise ValueError(f"{recipe.group}/{recipe.name}: invalid instruction")
    return result.data


def _assembly_replacements(
    config: PatchRecipeConfiguration,
) -> Mapping[str, bytes]:
    recipes = {recipe.name: recipe for recipe in config.patches[TARGET]}
    sources = {
        "codename_skip_copy": _only_source(
            recipes["codename_skip_copy"],
            "shared/player_name_inserts/codename_skip.s",
        ),
        "raw_menu_name_renderer": _only_source(
            recipes["raw_menu_name_renderer"],
            "shared/player_name_inserts/raw_menu_inserts.s",
        ),
        "raw_menu_result": _only_source(
            recipes["raw_menu_name_result_06030c66"],
            "shared/player_name_inserts/raw_menu_result.s",
        ),
    }
    for name in ("raw_menu_name_result_06030c66", "raw_menu_name_result_06030c98"):
        if _only_source(
            recipes[name], "shared/player_name_inserts/raw_menu_result.s"
        ) != sources["raw_menu_result"]:
            raise ValueError("EVENT raw-menu result source inventory changed")
    built = build_player_name_assembly(
        ADAPTER_SPEC,
        codename_source=sources["codename_skip_copy"],
        raw_menu_source=sources["raw_menu_name_renderer"],
        result_source=sources["raw_menu_result"],
    )
    if (
        built.raw_menu_used_size != RUNTIME_USED_SIZE
        or built.raw_menu_capacity != RUNTIME_CAPACITY
    ):
        raise ValueError("EVENT raw-menu name runtime geometry changed")
    return built.replacements


def _bind_patches(
    config: PatchRecipeConfiguration,
    stock: bytes,
) -> tuple[Patch, ...]:
    output: list[Patch] = []
    pointer_seen: set[str] = set()
    assembly = _assembly_replacements(config)
    assembly_seen: set[str] = set()
    for recipe in config.patches[TARGET]:
        expected = resolve_recipe_expected(recipe, stock, LOAD_ADDRESS)
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            try:
                replacement = assembly[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown assembly owner"
                ) from error
            assembly_seen.add(recipe.name)
        elif replacement_recipe.kind == "instruction":
            replacement = _instruction(recipe)
        elif replacement_recipe.kind == "pointer":
            pointer = replacement_recipe.pointer
            assert pointer is not None
            try:
                required = POINTER_CONTRACT[recipe.name]
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown name pointer owner"
                ) from error
            if pointer != required:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: player-name address contract changed"
                )
            pointer_seen.add(recipe.name)
            replacement = struct.pack(">I", pointer)
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement recipe"
            )
        if len(replacement) != len(expected):
            raise ValueError(
                f"{recipe.group}/{recipe.name}: generated {len(replacement)} bytes, "
                f"expected {len(expected)}"
            )
        output.append(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                expected,
                replacement,
            )
        )
    if pointer_seen != set(POINTER_CONTRACT):
        missing = sorted(set(POINTER_CONTRACT) - pointer_seen)
        raise ValueError(f"EVENT name-pointer recipe inventory changed: {missing}")
    if assembly_seen != set(assembly):
        raise ValueError("EVENT name assembly ownership differs from config")
    return tuple(output)


def build_event_name_inserts(event_base: bytes) -> EventNameInsertsBuild:
    """Apply only EVENT's name-row adapters to any compatible composed base."""
    config = _configuration()
    stock = _stock_source()
    _validate_sources(config, stock, event_base)
    patches = _bind_patches(config, stock)
    assembly_files = tuple(
        sorted(
            {
                source
                for recipe in config.patches[TARGET]
                for source in recipe.replacement.sources
            },
            key=lambda path: path.as_posix(),
        )
    )
    return EventNameInsertsBuild(
        apply_patches(event_base, LOAD_ADDRESS, patches),
        patches,
        assembly_files,
        (DISC_CONFIG_PATH, PLAYER_NAMES_PATH),
        MappingProxyType({f"game:{TARGET}": _sha256(stock)}),
        RUNTIME_USED_SIZE,
        RUNTIME_CAPACITY,
    )
