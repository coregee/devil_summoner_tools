"""Build the PSP title-screen help variable-width-font runtime patch."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..core.allegrex import Assembly, assemble_file, encode_instruction
from ..core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from ..core.patching import Patch, apply_patches


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ENGINE_ROOT / "config" / "title_help_ui.json"
ASSEMBLY_ROOT = ENGINE_ROOT / "asm"
TARGET = "BOOT.BIN"

PACKED_FIRST = 0x1F
PACKED_LAST = 0x7D
PACKED_WIDTH_COUNT = PACKED_LAST - PACKED_FIRST + 1
TITLE_HELP_WIDTH_TABLE_SIZE = 268
TITLE_HELP_STOCK_ADVANCE = 15
TITLE_HELP_DRAW_WRAPPER_ADDRESS = 0x0013EC80
TITLE_HELP_WIDTH_TABLE_ADDRESS = 0x0013ED00
STOCK_TITLE_HELP_GLYPH_DRAW_ADDRESS = 0x0000C998
CAVE_END_ADDRESS = 0x00140C38


@dataclass(frozen=True, slots=True)
class TitleHelpUiBuild:
    data: bytes
    patches: tuple[Patch, ...]
    assembly_files: tuple[Path, ...]
    runtime_used_size: int
    runtime_capacity: int


@dataclass(frozen=True, slots=True)
class TitleHelpRuntime:
    assembly: Assembly
    width_table: bytes


def _configuration() -> PatchRecipeConfiguration:
    return load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="title_help.ui",
        target_names={TARGET},
    )


def _packed_storage_index(character: str) -> int:
    if not isinstance(character, str) or len(character) != 1:
        raise ValueError("PSP packed-width lookup expects one character")
    code = ord(character)
    if character == " ":
        return PACKED_WIDTH_COUNT - 1
    if 0x30 <= code <= 0x7E:
        return code - 0x30
    if 0x21 <= code <= 0x2F:
        return code + 0x2E
    raise ValueError(f"character is outside printable ASCII: {character!r}")


def _validate_widths(widths: Iterable[int]) -> bytes:
    try:
        values = tuple(widths)
    except TypeError as error:
        raise TypeError("PSP VWF widths must be an iterable of integers") from error
    if len(values) != PACKED_WIDTH_COUNT:
        raise ValueError(
            f"PSP VWF width table has {len(values)} entries; "
            f"expected {PACKED_WIDTH_COUNT}"
        )
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= 0xFF
        for value in values
    ):
        raise ValueError("PSP VWF advances must be integer bytes in the range 1..255")
    return bytes(values)


def _build_width_table(widths: Iterable[int]) -> bytes:
    storage_widths = _validate_widths(widths)
    table = bytearray([TITLE_HELP_STOCK_ADVANCE] * TITLE_HELP_WIDTH_TABLE_SIZE)
    table[0] = storage_widths[_packed_storage_index(" ")]
    for offset, character in enumerate("0123456789"):
        table[1 + offset] = storage_widths[_packed_storage_index(character)]
    for offset, character in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        table[11 + offset] = storage_widths[_packed_storage_index(character)]
    for offset, character in enumerate("abcdefghijklmnopqrstuvwxyz"):
        table[37 + offset] = storage_widths[_packed_storage_index(character)]
    table[176] = storage_widths[_packed_storage_index(".")]
    return bytes(table)


def _build_runtime(
    widths: Iterable[int],
    config: PatchRecipeConfiguration | None = None,
) -> TitleHelpRuntime:
    configuration = config or _configuration()
    recipes = configuration.patches[TARGET]
    assembly_recipe = next(
        row for row in recipes if row.replacement.kind == "assembly"
    )
    source = assembly_recipe.replacement.sources[0]
    assembly = assemble_file(
        source,
        assembly_recipe.address,
        symbols={
            "title_help_widths": TITLE_HELP_WIDTH_TABLE_ADDRESS,
            "stock_title_help_glyph_draw": STOCK_TITLE_HELP_GLYPH_DRAW_ADDRESS,
        },
    )
    if assembly.labels.get("title_help_draw_wrapper") != assembly_recipe.address:
        raise ValueError("title-help assembly entry label moved")
    if len(assembly.data) != len(assembly_recipe.expected):
        raise ValueError("title-help assembly no longer fits its checked source span")
    if assembly_recipe.address + len(assembly.data) > TITLE_HELP_WIDTH_TABLE_ADDRESS:
        raise ValueError("title-help wrapper exceeds its pinned cave partition")
    width_table = _build_width_table(widths)
    if TITLE_HELP_WIDTH_TABLE_ADDRESS + len(width_table) > CAVE_END_ADDRESS:
        raise ValueError("title-help width table exceeds the checked code cave")
    return TitleHelpRuntime(assembly, width_table)


def _linked_call(address: int, target: int) -> bytes:
    return encode_instruction("jal target", address, symbols={"target": target})


def _build_patches(
    widths: Iterable[int],
    config: PatchRecipeConfiguration | None = None,
) -> tuple[tuple[Patch, ...], TitleHelpRuntime]:
    configuration = config or _configuration()
    runtime = _build_runtime(widths, configuration)
    links = dict(runtime.assembly.labels)
    generated = {"title_help_widths": runtime.width_table}
    patches: list[Patch] = []
    for recipe in configuration.patches[TARGET]:
        replacement_recipe = recipe.replacement
        if replacement_recipe.kind == "assembly":
            replacement = runtime.assembly.data
        elif replacement_recipe.kind == "linked_call":
            assert replacement_recipe.link is not None
            try:
                target = links[replacement_recipe.link]
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown link "
                    f"{replacement_recipe.link!r}"
                ) from error
            replacement = _linked_call(recipe.address, target)
        elif replacement_recipe.kind == "instruction":
            assert replacement_recipe.instruction is not None
            replacement = encode_instruction(
                replacement_recipe.instruction,
                recipe.address,
            )
        elif replacement_recipe.kind == "generated":
            assert replacement_recipe.generator is not None
            try:
                replacement = generated[replacement_recipe.generator]
            except KeyError as error:
                raise ValueError(
                    f"{recipe.group}/{recipe.name}: unknown generator "
                    f"{replacement_recipe.generator!r}"
                ) from error
        else:
            raise ValueError(
                f"{recipe.group}/{recipe.name}: unsupported replacement recipe"
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
    return tuple(patches), runtime


def _validate_source(stock: bytes, config: PatchRecipeConfiguration) -> None:
    target = config.targets[TARGET]
    if len(stock) != target.size:
        raise ValueError(
            f"PSP BOOT.BIN is {len(stock)} bytes; expected {target.size}"
        )
    digest = hashlib.sha256(stock).hexdigest()
    if digest != target.stock_sha256:
        raise ValueError(
            f"PSP BOOT.BIN SHA-256 is {digest}; expected {target.stock_sha256}"
        )
    for guard in config.guards[TARGET]:
        actual = stock[guard.file_offset : guard.file_offset + len(guard.expected)]
        if actual != guard.expected:
            raise ValueError(f"PSP title-help source guard changed: {guard.name}")


def build_title_help_ui(stock: bytes, widths: Iterable[int]) -> TitleHelpUiBuild:
    """Patch the pinned decrypted BOOT.BIN with the title-help VWF runtime."""

    config = _configuration()
    _validate_source(stock, config)
    patches, runtime = _build_patches(widths, config)
    target = config.targets[TARGET]
    output = apply_patches(stock, target.address_bias, patches)
    return TitleHelpUiBuild(
        output,
        patches,
        tuple(
            source
            for recipe in config.patches[TARGET]
            for source in recipe.replacement.sources
        ),
        len(runtime.assembly.data) + len(runtime.width_table),
        TITLE_HELP_WIDTH_TABLE_ADDRESS
        + TITLE_HELP_WIDTH_TABLE_SIZE
        - TITLE_HELP_DRAW_WRAPPER_ADDRESS,
    )

