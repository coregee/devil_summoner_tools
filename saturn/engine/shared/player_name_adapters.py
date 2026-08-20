"""Target-neutral builders for cloned EVENT/MSGR player-name adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from engine.core.sh2 import AssemblyError, assemble_file
from engine.shared.player_names import PLAYER_NAME_FIELD_BY_KEY


@dataclass(frozen=True, slots=True)
class PlayerNameAdapterSpec:
    label: str
    codename_address: int
    codename_continue: int
    raw_menu_address: int
    raw_menu_capacity: int
    menu_blitter_pointer: int
    original_blitter: int
    stock_advance: int
    result_sites: tuple[int, ...]
    result_continue: int


@dataclass(frozen=True, slots=True)
class PlayerNameAssembly:
    replacements: Mapping[str, bytes]
    raw_menu_used_size: int
    raw_menu_capacity: int


def pointer_contract() -> Mapping[str, int]:
    """Return the complete generated-row contract shared by both overlays."""
    fields = PLAYER_NAME_FIELD_BY_KEY
    return MappingProxyType(
        {
            "first_insert_pointer": fields["first_name"].runtime_address,
            "last_insert_pointer": fields["last_name"].runtime_address,
            "city_insert_pointer": fields["city"].runtime_address,
            "ward_insert_pointer": fields["ward"].runtime_address,
            "codename_insert_pointer": fields["codename"].runtime_address,
            "raw_menu_first_insert_pointer": fields["first_name"].runtime_address,
            "raw_menu_last_insert_pointer": fields["last_name"].runtime_address,
        }
    )


def _assembled(
    source: Path,
    address: int,
    symbols: Mapping[str, int],
    context: str,
) -> bytes:
    try:
        result = assemble_file(source, address, dict(symbols))
    except (AssemblyError, FileNotFoundError) as error:
        raise ValueError(f"{context}: {error}") from error
    if result.warnings:
        raise ValueError(f"{context}: assembly warnings: {result.warnings}")
    return result.data


def build_player_name_assembly(
    spec: PlayerNameAdapterSpec,
    *,
    codename_source: Path,
    raw_menu_source: Path,
    result_source: Path,
) -> PlayerNameAssembly:
    """Assemble all code replacements whose symbols differ by overlay."""
    codename = _assembled(
        codename_source,
        spec.codename_address,
        {"CONTINUE": spec.codename_continue},
        f"{spec.label} codename adapter",
    )
    raw_menu = _assembled(
        raw_menu_source,
        spec.raw_menu_address,
        {
            "MENU_BLITTER_POINTER": spec.menu_blitter_pointer,
            "ORIGINAL_BLITTER": spec.original_blitter,
            "STOCK_ADVANCE": spec.stock_advance,
            "TERMINATOR": 0x8000,
        },
        f"{spec.label} raw-menu name adapter",
    )
    if len(raw_menu) > spec.raw_menu_capacity:
        raise ValueError(
            f"{spec.label} raw-menu adapter needs {len(raw_menu)} bytes; "
            f"capacity is {spec.raw_menu_capacity}"
        )
    replacements = {
        "codename_skip_copy": codename,
        "raw_menu_name_renderer": raw_menu.ljust(spec.raw_menu_capacity, b"\0"),
    }
    for address in spec.result_sites:
        replacements[f"raw_menu_name_result_{address:08x}"] = _assembled(
            result_source,
            address,
            {"CONTINUE": spec.result_continue},
            f"{spec.label} raw-menu result at {address:#010x}",
        )
    return PlayerNameAssembly(
        MappingProxyType(replacements),
        len(raw_menu),
        spec.raw_menu_capacity,
    )
