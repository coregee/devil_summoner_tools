"""Build the fixed-cell SNDTEST and TEST3D diagnostic overlays."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.patch_recipes import (
    PatchRecipeConfiguration,
    load_patch_recipe_configuration,
)
from engine.core.patching import Patch, apply_patches
from rom.util.catalog import load_catalog, validate_source
from rom.util.workflows import read_source_files
from text.util.assets import ASSET_ROOT, BINDING_ROOT, CORPUS_ROOT, load_asset, load_binding
from text.util.surfaces import load_surfaces


ENGINE_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = ENGINE_ROOT.parent
CONFIG_PATH = ENGINE_ROOT / "config" / "diagnostics_ui.json"
GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
BUILD_PATH = GENERATED_ROOT / "diagnostics_ui_build.json"
TARGETS = ("SNDTEST.BIN", "TEST3D.BIN")
OUTPUT_PATHS = {target: GENERATED_ROOT / target for target in TARGETS}
SURFACES_PATH = SATURN_ROOT / "text" / "config" / "surfaces.json"
SOURCE_MANIFEST_PATH = (
    SATURN_ROOT / "text" / "config" / "sources" / "game" / "manifest.json"
)
DISC_CONFIG_PATH = SATURN_ROOT / "rom" / "discs.json"

SOUND_ASSET_PATH = ASSET_ROOT / "diagnostics" / "sound_test.json"
TEST3D_ASSET_PATH = ASSET_ROOT / "diagnostics" / "test_3d.json"
SOUND_BINDING_PATH = BINDING_ROOT / "sound_test.json"
TEST3D_BINDING_PATH = BINDING_ROOT / "test_3d.json"
SOUND_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "sndtest_fields.json"
TEST3D_CORPUS_PATH = CORPUS_ROOT / "game" / "addressed" / "test3d_fields.json"

LAYOUT = {
    "SNDTEST.BIN": (
        ("title", 0x06026FAC, "game.sndtest_fields.o006fac", "title"),
        (
            "request_number",
            0x06026FC0,
            "game.sndtest_fields.o006fc0",
            "request_number",
        ),
        (
            "sound_effect_request_number",
            0x06026FC8,
            "game.sndtest_fields.o006fc8",
            "sound_effect_request_number",
        ),
        (
            "exit_message",
            0x06026FD4,
            "game.sndtest_fields.o006fd4",
            "exit_message",
        ),
    ),
    "TEST3D.BIN": (
        ("title", 0x0602695C, "game.test3d_fields.o00695c", "title"),
        ("control", 0x06026970, "game.test3d_fields.o006970", "control"),
        (
            "map_number",
            0x06026978,
            "game.test3d_fields.o006978",
            "map_number",
        ),
        (
            "direction",
            0x06026980,
            "game.test3d_fields.o006980",
            "direction",
        ),
        (
            "x_position",
            0x06026988,
            "game.test3d_fields.o006988",
            "x_position",
        ),
        (
            "y_position",
            0x06026990,
            "game.test3d_fields.o006990",
            "y_position",
        ),
        ("launch", 0x060269A0, "game.test3d_fields.o0069a0", "launch"),
    ),
}


@dataclass(frozen=True, slots=True)
class DiagnosticsUiBuild:
    outputs: Mapping[str, bytes]
    patches: tuple[Patch, ...]
    asset_files: tuple[Path, ...]
    assembly_files: tuple[Path, ...]
    runtime_input_files: tuple[Path, ...]
    source_inputs: Mapping[str, str]
    runtime_used_size: int
    runtime_capacity: int
    runtime_arenas: tuple[object, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_corpus(path: Path) -> dict[str, str]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid diagnostics corpus: {path}") from error
    if not isinstance(rows, list):
        raise ValueError(f"diagnostics corpus must be an array: {path}")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"invalid diagnostics corpus row: {path}")
        physical_id = row["id"]
        reference = row.get("reference")
        if not isinstance(reference, str) or physical_id in result:
            raise ValueError(f"invalid diagnostics physical record {physical_id!r}")
        result[physical_id] = reference
    return result


def _configuration() -> PatchRecipeConfiguration:
    config = load_patch_recipe_configuration(
        CONFIG_PATH,
        surface="diagnostics.ui",
        target_names=set(TARGETS),
        input_names=set(),
    )
    expected = {
        target: tuple((name, address) for name, address, _physical, _asset in rows)
        for target, rows in LAYOUT.items()
    }
    for target in TARGETS:
        actual = tuple(
            (
                recipe.name,
                recipe.address,
                recipe.replacement.kind,
                recipe.replacement.generator,
            )
            for recipe in config.patches[target]
        )
        wanted = tuple(
            (name, address, "generated", "diagnostics_ascii")
            for name, address in expected[target]
        )
        if actual != wanted:
            raise ValueError(f"{target} diagnostics recipe contract changed")
    return config


def _validate_surfaces() -> None:
    surfaces = load_surfaces()
    for name in ("diagnostics.sound_test", "diagnostics.test_3d"):
        surface = surfaces.surface(name)
        for layout in (surface.ja, surface.en):
            if (
                layout.font,
                layout.rows,
                layout.width.unit,
                layout.width.value,
            ) != (None, 1, "glyph_cells", 19):
                raise ValueError(f"{name} geometry changed")


def _payloads(config: PatchRecipeConfiguration) -> dict[str, dict[str, bytes]]:
    assets = {
        "SNDTEST.BIN": load_asset("diagnostics/sound_test.json"),
        "TEST3D.BIN": load_asset("diagnostics/test_3d.json"),
    }
    bindings = {
        "SNDTEST.BIN": load_binding(SOUND_BINDING_PATH),
        "TEST3D.BIN": load_binding(TEST3D_BINDING_PATH),
    }
    corpora = {
        "SNDTEST.BIN": _read_corpus(SOUND_CORPUS_PATH),
        "TEST3D.BIN": _read_corpus(TEST3D_CORPUS_PATH),
    }
    expected_assets = {
        "SNDTEST.BIN": "diagnostics/sound_test.json",
        "TEST3D.BIN": "diagnostics/test_3d.json",
    }
    result: dict[str, dict[str, bytes]] = {}
    for target in TARGETS:
        binding = bindings[target]
        if binding.asset.as_posix() != expected_assets[target]:
            raise ValueError(f"{target} diagnostics binding asset changed")
        expected_records = {
            physical: f"{asset}.text"
            for _name, _address, physical, asset in LAYOUT[target]
        }
        if dict(binding.records) != expected_records:
            raise ValueError(f"{target} diagnostics binding inventory changed")
        target_payloads: dict[str, bytes] = {}
        recipes = {recipe.name: recipe for recipe in config.patches[target]}
        for name, _address, physical_id, asset_key in LAYOUT[target]:
            field = assets[target].entries[asset_key].fields["text"]
            if field.reference != corpora[target][physical_id]:
                raise ValueError(f"{physical_id} reference disagrees with its asset")
            try:
                encoded = field.translation.encode("ascii") + b"\0"
            except UnicodeEncodeError as error:
                raise ValueError(f"{target}/{name} must remain ASCII") from error
            capacity = len(recipes[name].expected)
            if len(encoded) > capacity:
                raise ValueError(
                    f"{target}/{name} uses {len(encoded)}/{capacity} bytes"
                )
            target_payloads[name] = encoded.ljust(capacity, b"\0")
        result[target] = target_payloads
    return result


def build_diagnostics_ui() -> DiagnosticsUiBuild:
    _validate_surfaces()
    config = _configuration()
    payloads = _payloads(config)
    validated = validate_source(load_catalog()["game"])
    stock_files = read_source_files(validated, TARGETS)
    outputs: dict[str, bytes] = {}
    all_patches: list[Patch] = []
    source_inputs: dict[str, str] = {}
    for target in TARGETS:
        stock = stock_files[target]
        contract = config.targets[target]
        if len(stock) != contract.size or _sha256(stock) != contract.stock_sha256:
            raise ValueError(f"stock {target} does not match diagnostics target")
        patches = tuple(
            Patch(
                recipe.group,
                recipe.name,
                recipe.address,
                recipe.expected,
                payloads[target][recipe.name],
            )
            for recipe in config.patches[target]
        )
        outputs[target] = apply_patches(stock, contract.load_address, patches)
        all_patches.extend(patches)
        source_inputs[f"game:{target}"] = _sha256(stock)
    return DiagnosticsUiBuild(
        outputs=MappingProxyType(outputs),
        patches=tuple(all_patches),
        asset_files=(SOUND_ASSET_PATH, TEST3D_ASSET_PATH),
        assembly_files=(),
        runtime_input_files=(
            SURFACES_PATH,
            SOURCE_MANIFEST_PATH,
            DISC_CONFIG_PATH,
            SOUND_BINDING_PATH,
            TEST3D_BINDING_PATH,
            SOUND_CORPUS_PATH,
            TEST3D_CORPUS_PATH,
        ),
        source_inputs=MappingProxyType(source_inputs),
        runtime_used_size=0,
        runtime_capacity=0,
        runtime_arenas=(),
    )


__all__ = [
    "BUILD_PATH",
    "CONFIG_PATH",
    "OUTPUT_PATHS",
    "TARGETS",
    "DiagnosticsUiBuild",
    "build_diagnostics_ui",
]
