"""Build the Saturn runtime patches required by configured text surfaces."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path, PurePosixPath


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from engine.surfaces.battle_negotiation import build_battle_negotiation  # noqa: E402
from engine.surfaces.battle_ui import build_battle_ui  # noqa: E402
from engine.surfaces.analyze_ui import (  # noqa: E402
    CONFIG_PATH as ANALYZE_CONFIG_PATH,
    RUNTIME_CAVE as ANALYZE_RUNTIME_CAVE,
    TABLE_CAVE as ANALYZE_TABLE_CAVE,
    build_analyze_ui,
)
from engine.surfaces.comp_menu import (  # noqa: E402
    BUILD_PATH as COMP_BUILD_PATH,
    NORMCOM_OUTPUT_PATH as COMP_NORMCOM_OUTPUT_PATH,
    build_comp_menu,
)
from engine.surfaces.compendium_text import (  # noqa: E402
    BUILD_PATH as COMPENDIUM_TEXT_BUILD_PATH,
    CONFIG_PATH as COMPENDIUM_TEXT_CONFIG_PATH,
    OUTPUT_ROOT as COMPENDIUM_TEXT_OUTPUT_ROOT,
    PROFILE_TAIL_BYTES as COMPENDIUM_PROFILE_TAIL_BYTES,
    PROFILE_TAIL_OFFSET as COMPENDIUM_PROFILE_TAIL_OFFSET,
    TARGET as COMPENDIUM_TEXT_TARGET,
    build_compendium_text,
)
from engine.surfaces.equipment_ui import build_equipment_ui  # noqa: E402
from engine.surfaces.facilities_status_ui import (  # noqa: E402
    BUILD_PATH as FACILITIES_STATUS_BUILD_MANIFEST_PATH,
    CONFIG_PATH as FACILITIES_STATUS_CONFIG_PATH,
    OUTPUT_PATH as FACILITIES_STATUS_OUTPUT_PATH,
    TARGET as FACILITIES_STATUS_TARGET,
    build_facilities_status_ui,
)
from engine.surfaces.fmv_subtitles import (  # noqa: E402
    CONFIG_PATH as FMV_SUBTITLES_CONFIG_PATH,
    TARGET as FMV_SUBTITLES_TARGET,
    build_fmv_subtitles,
)
from engine.surfaces.dungeon_locations import (  # noqa: E402
    AUTOMAP_TARGET as DUNGEON_AUTOMAP_TARGET,
    CONFIG_PATH as DUNGEON_LOCATIONS_CONFIG_PATH,
    MAZE_TARGET as DUNGEON_MAZE_TARGET,
    build_dungeon_locations,
)
from engine.surfaces.event_dialogue import (  # noqa: E402
    BUILD_PATH as EVENT_BUILD_PATH,
    CODEC_PATH,
    FONT12_METRICS_PATH,
    FONT16_METRICS_PATH,
    FONT8_METRICS_PATH,
    OUTPUT_PATH as EVENT_OUTPUT_PATH,
    SHOPSMP_TEXT_BUILD_PATH,
    build_event_dialogue,
    file_sha256,
    sha256,
    stock_event,
    validate_shopsmp_text_build,
)
from engine.surfaces.event_name_inserts import (  # noqa: E402
    CONFIG_PATH as EVENT_NAME_INSERTS_CONFIG_PATH,
    build_event_name_inserts,
)
from engine.surfaces.fusion import (  # noqa: E402
    CONFIG_PATH as FUSION_CONFIG_PATH,
    build_fusion_menu,
)
from engine.surfaces.level_up_ui import (  # noqa: E402
    CONFIG_PATH as LEVEL_UP_CONFIG_PATH,
    RUNTIME_CAVE as LEVEL_UP_RUNTIME_CAVE,
    build_level_up_ui,
)
from engine.surfaces.horoscope_ui import (  # noqa: E402
    CONFIG_PATH as HOROSCOPE_CONFIG_PATH,
    TARGET as HOROSCOPE_TARGET,
    build_horoscope_ui,
)
from engine.surfaces.credits_ui import (  # noqa: E402
    CONFIG_PATH as CREDITS_CONFIG_PATH,
    TARGET as CREDITS_TARGET,
    build_credits_ui,
)
from engine.surfaces.diagnostics_ui import (  # noqa: E402
    CONFIG_PATH as DIAGNOSTICS_CONFIG_PATH,
    TARGETS as DIAGNOSTICS_TARGETS,
    build_diagnostics_ui,
)
from engine.surfaces.map_2d_ui import (  # noqa: E402
    CONFIG_PATH as MAP_2D_CONFIG_PATH,
    TARGET as MAP_2D_TARGET,
    build_map_2d_ui,
)
from engine.surfaces.field_messages import (  # noqa: E402
    CONFIG_PATH as FIELD_MESSAGES_CONFIG_PATH,
    build_field_messages,
)
from engine.surfaces.maze_party_panel import (  # noqa: E402
    BUILD_PATH as MAZE_PARTY_PANEL_BUILD_MANIFEST_PATH,
    CONFIG_PATH as MAZE_PARTY_PANEL_CONFIG_PATH,
    build_maze_party_panel,
)
from engine.surfaces.options_ui import (  # noqa: E402
    CONFIG_PATH as OPTIONS_CONFIG_PATH,
    build_options_ui,
)
from engine.surfaces.profile_entry_ui import (  # noqa: E402
    CONFIG_PATH as PROFILE_ENTRY_CONFIG_PATH,
    TARGET as PROFILE_ENTRY_TARGET,
    build_profile_entry_ui,
)
from engine.surfaces.portrait_scene_ui import (  # noqa: E402
    BUILD_PATH as PORTRAIT_SCENE_BUILD_MANIFEST_PATH,
    CONFIG_PATH as PORTRAIT_SCENE_CONFIG_PATH,
    OUTPUT_PATH as PORTRAIT_SCENE_OUTPUT_PATH,
    TARGET as PORTRAIT_SCENE_TARGET,
    build_portrait_scene_ui,
)
from engine.surfaces.save_load_ui import (  # noqa: E402
    CONFIG_PATH as SAVE_LOAD_CONFIG_PATH,
    TARGETS as SAVE_LOAD_TARGETS,
    build_save_load_ui,
)
from engine.surfaces.status_ui import (  # noqa: E402
    CONFIG_PATH as STATUS_CONFIG_PATH,
    build_status_ui,
)


GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
EVENT_DIALOGUE_OUTPUT_PATH = EVENT_OUTPUT_PATH
BUILD_MANIFEST_PATH = EVENT_BUILD_PATH
FUSION_OUTPUT_PATH = GENERATED_ROOT / "fusion_menu" / "EVENT.BIN"
FUSION_BUILD_MANIFEST_PATH = GENERATED_ROOT / "fusion_menu_build.json"
EVENT_NAME_INSERTS_OUTPUT_PATH = (
    GENERATED_ROOT / "event_name_inserts" / "EVENT.BIN"
)
EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH = (
    GENERATED_ROOT / "event_name_inserts_build.json"
)
EQUIPMENT_EVENT_OUTPUT_PATH = GENERATED_ROOT / "equipment_ui" / "EVENT.BIN"
EQUIPMENT_NORMCOM_OUTPUT_PATH = (
    GENERATED_ROOT / "equipment_ui" / "NORMCOM.BIN"
)
EQUIPMENT_BUILD_MANIFEST_PATH = GENERATED_ROOT / "equipment_ui_build.json"
STATUS_NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "NORMCOM.BIN"
STATUS_BUILD_MANIFEST_PATH = GENERATED_ROOT / "status_ui_build.json"
OPTIONS_OUTPUT_PATH = GENERATED_ROOT / "CFG_SET.BIN"
OPTIONS_BUILD_MANIFEST_PATH = GENERATED_ROOT / "options_ui_build.json"
LEVEL_UP_OUTPUT_PATH = GENERATED_ROOT / "LEVEL_UP.BIN"
LEVEL_UP_BUILD_MANIFEST_PATH = GENERATED_ROOT / "level_up_ui_build.json"
ANALYZE_OUTPUT_PATH = GENERATED_ROOT / "DA_3D.BIN"
ANALYZE_BUILD_MANIFEST_PATH = GENERATED_ROOT / "analyze_ui_build.json"
DUNGEON_LOCATIONS_ROOT = GENERATED_ROOT / "dungeon_locations"
DUNGEON_LOCATIONS_MAZE_PATH = DUNGEON_LOCATIONS_ROOT / "MAZE.BIN"
DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH = (
    GENERATED_ROOT / "dungeon_locations_build.json"
)
FIELD_MESSAGES_OUTPUT_PATH = GENERATED_ROOT / "MAZE.BIN"
FIELD_MESSAGES_BUILD_MANIFEST_PATH = GENERATED_ROOT / "field_messages_build.json"
SAVE_LOAD_OUTPUT_PATHS = {
    target: GENERATED_ROOT / target for target in SAVE_LOAD_TARGETS
}
SAVE_LOAD_BUILD_MANIFEST_PATH = GENERATED_ROOT / "save_load_ui_build.json"
PROFILE_ENTRY_OUTPUT_PATH = GENERATED_ROOT / PROFILE_ENTRY_TARGET
PROFILE_ENTRY_BUILD_MANIFEST_PATH = GENERATED_ROOT / "profile_entry_ui_build.json"
MAP_2D_OUTPUT_PATH = GENERATED_ROOT / MAP_2D_TARGET
MAP_2D_BUILD_MANIFEST_PATH = GENERATED_ROOT / "map_2d_ui_build.json"
HOROSCOPE_OUTPUT_PATH = GENERATED_ROOT / HOROSCOPE_TARGET
HOROSCOPE_BUILD_MANIFEST_PATH = GENERATED_ROOT / "horoscope_ui_build.json"
CREDITS_OUTPUT_PATH = GENERATED_ROOT / CREDITS_TARGET
CREDITS_BUILD_MANIFEST_PATH = GENERATED_ROOT / "credits_ui_build.json"
DIAGNOSTICS_OUTPUT_PATHS = {
    target: GENERATED_ROOT / target for target in DIAGNOSTICS_TARGETS
}
DIAGNOSTICS_BUILD_MANIFEST_PATH = GENERATED_ROOT / "diagnostics_ui_build.json"
FMV_SUBTITLES_OUTPUT_PATH = GENERATED_ROOT / FMV_SUBTITLES_TARGET
FMV_SUBTITLES_BUILD_MANIFEST_PATH = GENERATED_ROOT / "fmv_subtitles_build.json"
COMPENDIUM_INSTALL_ROOT = SATURN_ROOT / "rom" / "extracted" / "compendium"
PROFILE_ENTRY_INSTALL_PATH = (
    SATURN_ROOT / "rom" / "extracted" / "game" / PROFILE_ENTRY_TARGET
)
SAVE_LOAD_INSTALL_ROOT = SATURN_ROOT / "rom" / "extracted" / "game"
SAVE_LOAD_VISUAL_MANIFEST_PATH = (
    SATURN_ROOT / "visual" / "modified" / "game" / "manifest.json"
)
SAVE_LOAD_VISUAL_PREFIX = "SAVE_LOAD/storage/"
SAVE_LOAD_VISUAL_PATHS = frozenset(
    SAVE_LOAD_VISUAL_PREFIX + name
    for name in (
        "internal_selected.png",
        "internal_idle.png",
        "cartridge_selected.png",
        "cartridge_idle.png",
    )
)


def build_fusion_surface() -> dict[Path, bytes]:
    """Compose the Fusion consumers onto the general EVENT runtime."""
    event_outputs = build_event_dialogue()
    event_patched = event_outputs[EVENT_DIALOGUE_OUTPUT_PATH]
    stock = stock_event()
    codec_digest = file_sha256(CODEC_PATH)
    validate_shopsmp_text_build(codec_digest)
    fusion = build_fusion_menu(stock, event_patched)
    manifest = {
        "version": 1,
        "surface": "fusion.menu",
        "patch_config_sha256": file_sha256(FUSION_CONFIG_PATH),
        "base_event_output_sha256": sha256(event_patched),
        "base_event_manifest_sha256": sha256(
            event_outputs[BUILD_MANIFEST_PATH]
        ),
        "shopsmp_text_build_sha256": file_sha256(SHOPSMP_TEXT_BUILD_PATH),
        "font16_metrics_sha256": file_sha256(FONT16_METRICS_PATH),
        "font12_metrics_sha256": file_sha256(FONT12_METRICS_PATH),
        "font8_metrics_sha256": file_sha256(FONT8_METRICS_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in fusion.asset_files
        },
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in fusion.assembly_files
        },
        "runtime": {
            "address": "0x06021800",
            "end": f"0x{0x06021800 + len(fusion.runtime):08x}",
            "bytes": len(fusion.runtime),
            "sha256": sha256(fusion.runtime),
        },
        "output_sha256": sha256(fusion.data),
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in fusion.patches)
        ),
        "patches": len(fusion.patches),
    }
    return {
        **event_outputs,
        FUSION_OUTPUT_PATH: fusion.data,
        FUSION_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_event_name_inserts_surface() -> dict[Path, bytes]:
    """Compose player-name EVENT adapters onto the checked Fusion stage."""
    fusion_outputs = build_fusion_surface()
    base = fusion_outputs[FUSION_OUTPUT_PATH]
    result = build_event_name_inserts(base)
    manifest = {
        "version": 1,
        "surface": "event.name_inserts",
        "patch_config_sha256": file_sha256(EVENT_NAME_INSERTS_CONFIG_PATH),
        "base": {
            "surface": "fusion.menu",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                fusion_outputs[FUSION_BUILD_MANIFEST_PATH]
            ),
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
        },
        "output": {
            "file": "EVENT.BIN",
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        **fusion_outputs,
        EVENT_NAME_INSERTS_OUTPUT_PATH: result.data,
        EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_equipment_surface() -> dict[Path, bytes]:
    """Compose shared equipment consumers onto name-adapted EVENT and COMP."""
    event_outputs = build_event_name_inserts_surface()
    comp_outputs = build_comp_menu()
    result = build_equipment_ui(
        event_outputs[EVENT_NAME_INSERTS_OUTPUT_PATH],
        comp_outputs[COMP_NORMCOM_OUTPUT_PATH],
    )
    manifest = {
        "version": 1,
        "surface": "equipment.ui",
        "patch_config_sha256": file_sha256(
            ENGINE_ROOT / "config" / "equipment_ui.json"
        ),
        "bases": {
            "EVENT.BIN": {
                "surface": "event.name_inserts",
                "sha256": sha256(
                    event_outputs[EVENT_NAME_INSERTS_OUTPUT_PATH]
                ),
                "manifest_sha256": sha256(
                    event_outputs[EVENT_NAME_INSERTS_BUILD_MANIFEST_PATH]
                ),
            },
            "NORMCOM.BIN": {
                "surface": "comp.menu",
                "sha256": sha256(comp_outputs[COMP_NORMCOM_OUTPUT_PATH]),
                "manifest_sha256": sha256(comp_outputs[COMP_BUILD_PATH]),
            },
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "outputs": {
            "EVENT.BIN": {"sha256": sha256(result.event)},
            "NORMCOM.BIN": {"sha256": sha256(result.normcom)},
        },
        "patch_groups": {
            target: list(dict.fromkeys(patch.group for patch in patches))
            for target, patches in result.patches.items()
        },
        "patches": {
            target: len(patches) for target, patches in result.patches.items()
        },
    }
    return {
        **event_outputs,
        **comp_outputs,
        EQUIPMENT_EVENT_OUTPUT_PATH: result.event,
        EQUIPMENT_NORMCOM_OUTPUT_PATH: result.normcom,
        EQUIPMENT_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_facilities_status_surface() -> dict[Path, bytes]:
    """Compose the EVENT facility and detailed-status consumers."""
    equipment_outputs = build_equipment_surface()
    base = equipment_outputs[EQUIPMENT_EVENT_OUTPUT_PATH]
    result = build_facilities_status_ui(base)
    manifest = {
        "version": 1,
        "surface": "facilities.status_ui",
        "patch_config_sha256": file_sha256(FACILITIES_STATUS_CONFIG_PATH),
        "base": {
            "surface": "equipment.ui",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                equipment_outputs[EQUIPMENT_BUILD_MANIFEST_PATH]
            ),
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": {
                arena.name: {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            },
        },
        "output": {
            "file": FACILITIES_STATUS_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        **equipment_outputs,
        FACILITIES_STATUS_OUTPUT_PATH: result.data,
        FACILITIES_STATUS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_fmv_subtitle_surface() -> dict[Path, bytes]:
    """Compose the lossless START2 overlay as the terminal EVENT image."""
    facilities_outputs = build_facilities_status_surface()
    base = facilities_outputs[FACILITIES_STATUS_OUTPUT_PATH]
    result = build_fmv_subtitles(base)
    manifest = {
        "version": 1,
        "surface": "fmv.subtitles",
        "patch_config_sha256": file_sha256(FMV_SUBTITLES_CONFIG_PATH),
        "base": {
            "surface": "facilities.status_ui",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                facilities_outputs[FACILITIES_STATUS_BUILD_MANIFEST_PATH]
            ),
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": {
                arena.name: {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            },
        },
        "cues": len(result.cues),
        "output": {
            "file": FMV_SUBTITLES_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(dict.fromkeys(patch.group for patch in result.patches)),
        "patches": len(result.patches),
    }
    return {
        **facilities_outputs,
        FMV_SUBTITLES_OUTPUT_PATH: result.data,
        FMV_SUBTITLES_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_profile_entry_surface() -> dict[Path, bytes]:
    """Build the complete Profile Entry controller from the stock NAME target."""
    result = build_profile_entry_ui()
    manifest = {
        "version": 1,
        "surface": "profile_entry.ui",
        "patch_config_sha256": file_sha256(PROFILE_ENTRY_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
        },
        "output": {
            "file": PROFILE_ENTRY_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        PROFILE_ENTRY_OUTPUT_PATH: result.data,
        PROFILE_ENTRY_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_map_2d_surface() -> dict[Path, bytes]:
    """Build the complete two-dimensional city map from the stock target."""
    result = build_map_2d_ui()
    manifest = {
        "version": 1,
        "surface": "map_2d.ui",
        "patch_config_sha256": file_sha256(MAP_2D_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
        },
        "output": {
            "file": MAP_2D_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        MAP_2D_OUTPUT_PATH: result.data,
        MAP_2D_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_horoscope_surface() -> dict[Path, bytes]:
    """Build the authored horoscope messages in the stock overlay."""
    result = build_horoscope_ui()
    manifest = {
        "version": 1,
        "surface": "horoscope.ui",
        "patch_config_sha256": file_sha256(HOROSCOPE_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {},
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": [
                {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            ],
        },
        "output": {
            "file": HOROSCOPE_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        HOROSCOPE_OUTPUT_PATH: result.data,
        HOROSCOPE_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_credits_surface() -> dict[Path, bytes]:
    """Build every authored END_ROLL staff-name consumer."""
    result = build_credits_ui()
    manifest = {
        "version": 1,
        "surface": "credits.ui",
        "patch_config_sha256": file_sha256(CREDITS_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": [
                {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            ],
        },
        "output": {"file": CREDITS_TARGET, "sha256": sha256(result.data)},
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        CREDITS_OUTPUT_PATH: result.data,
        CREDITS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_diagnostics_surface() -> dict[Path, bytes]:
    """Build the authored Sound Test and 3D Test fixed-cell labels."""
    result = build_diagnostics_ui()
    manifest = {
        "version": 1,
        "surface": "diagnostics.ui",
        "patch_config_sha256": file_sha256(DIAGNOSTICS_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {},
        "runtime": {"bytes": 0, "capacity": 0, "arenas": []},
        "outputs": {
            target: {"sha256": sha256(result.outputs[target])}
            for target in DIAGNOSTICS_TARGETS
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        **{
            DIAGNOSTICS_OUTPUT_PATHS[target]: result.outputs[target]
            for target in DIAGNOSTICS_TARGETS
        },
        DIAGNOSTICS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_compendium_text_surface() -> dict[Path, bytes]:
    """Build every proved Akuma Zensho profile and catalogue text field."""
    result = build_compendium_text()
    manifest = {
        "version": 1,
        "surface": "compendium.text",
        "patch_config_sha256": file_sha256(COMPENDIUM_TEXT_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": [
                {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            ],
        },
        "outputs": {
            target: {"sha256": sha256(data), "bytes": len(data)}
            for target, data in result.outputs.items()
        },
        "patch_groups": list(
            dict.fromkeys(
                patch.group
                for patches in result.patches.values()
                for patch in patches
            )
        ),
        "patches": sum(len(patches) for patches in result.patches.values()),
        "unresolved_physical_ids": sorted(result.unresolved_ids),
    }
    return {
        **{
            COMPENDIUM_TEXT_OUTPUT_ROOT / target: data
            for target, data in result.outputs.items()
        },
        COMPENDIUM_TEXT_BUILD_PATH: (json.dumps(manifest, indent=2) + "\n").encode(
            "utf-8"
        ),
    }


def build_portrait_scene_surface() -> dict[Path, bytes]:
    """Build the complete portrait-scene consumer from the stock MSGR target."""
    result = build_portrait_scene_ui()
    manifest = {
        "version": 1,
        "surface": "portrait_scene.ui",
        "patch_config_sha256": file_sha256(PORTRAIT_SCENE_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": {
                arena.name: {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            },
        },
        "output": {
            "file": PORTRAIT_SCENE_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        PORTRAIT_SCENE_OUTPUT_PATH: result.data,
        PORTRAIT_SCENE_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_status_surface() -> dict[Path, bytes]:
    """Compose the detailed-status consumer onto the equipment NORMCOM base."""
    equipment_outputs = build_equipment_surface()
    base = equipment_outputs[EQUIPMENT_NORMCOM_OUTPUT_PATH]
    result = build_status_ui(base)
    manifest = {
        "version": 1,
        "surface": "status.ui",
        "patch_config_sha256": file_sha256(STATUS_CONFIG_PATH),
        "base": {
            "surface": "equipment.ui",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                equipment_outputs[EQUIPMENT_BUILD_MANIFEST_PATH]
            ),
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "output": {
            "file": "NORMCOM.BIN",
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        **equipment_outputs,
        STATUS_NORMCOM_OUTPUT_PATH: result.data,
        STATUS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_options_surface() -> dict[Path, bytes]:
    """Build the standalone Options consumer for CFG_SET.BIN."""
    result = build_options_ui()
    manifest = {
        "version": 1,
        "surface": "options.ui",
        "patch_config_sha256": file_sha256(OPTIONS_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "derived_local_compound_glyphs": len(result.compounds),
        "output": {
            "file": "CFG_SET.BIN",
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        OPTIONS_OUTPUT_PATH: result.data,
        OPTIONS_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_level_up_surface() -> dict[Path, bytes]:
    """Build the main Level Up panel and its Learned Magic window."""
    result = build_level_up_ui()
    manifest = {
        "version": 1,
        "surface": "level_up.ui",
        "patch_config_sha256": file_sha256(LEVEL_UP_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "address": f"0x{LEVEL_UP_RUNTIME_CAVE:08x}",
            "end": f"0x{LEVEL_UP_RUNTIME_CAVE + result.runtime_used_size:08x}",
            "bytes": result.runtime_used_size,
            "capacity": 0x500,
        },
        "output": {
            "file": "LEVEL_UP.BIN",
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        LEVEL_UP_OUTPUT_PATH: result.data,
        LEVEL_UP_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_analyze_surface() -> dict[Path, bytes]:
    """Build the DA_3D Analyze grid and selected-demon detail panel."""
    result = build_analyze_ui()
    manifest = {
        "version": 1,
        "surface": "map_3d.analyze",
        "patch_config_sha256": file_sha256(ANALYZE_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "detail": {
                "address": f"0x{ANALYZE_RUNTIME_CAVE:08x}",
                "bytes": result.runtime_used_size,
                "capacity": result.runtime_capacity,
            },
            "table": {
                "address": f"0x{ANALYZE_TABLE_CAVE:08x}",
                "bytes": result.table_runtime_used_size,
                "capacity": result.table_runtime_capacity,
            },
        },
        "output": {
            "file": "DA_3D.BIN",
            "sha256": sha256(result.data),
        },
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        ANALYZE_OUTPUT_PATH: result.data,
        ANALYZE_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def _generated_target_path(target: str) -> Path:
    return GENERATED_ROOT.joinpath(*PurePosixPath(target).parts)


def build_dungeon_locations_surface() -> dict[Path, bytes]:
    """Build every dungeon-location consumer from the validated stock targets."""
    result = build_dungeon_locations()
    outputs = {
        (
            DUNGEON_LOCATIONS_MAZE_PATH
            if target == DUNGEON_MAZE_TARGET
            else _generated_target_path(target)
        ): data
        for target, data in result.outputs.items()
    }
    manifest = {
        "version": 1,
        "surface": "dungeon.locations",
        "patch_config_sha256": file_sha256(DUNGEON_LOCATIONS_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "outputs": {
            target: {
                "sha256": sha256(data),
                "patches": len(result.patches[target]),
            }
            for target, data in result.outputs.items()
        },
        "runtime": {
            target: {
                "bytes": len(data),
                "sha256": sha256(data),
            }
            for target, data in result.runtime_used.items()
        },
        "targets": len(result.outputs),
        "patches": sum(len(rows) for rows in result.patches.values()),
    }
    outputs[DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH] = (
        json.dumps(manifest, indent=2) + "\n"
    ).encode("utf-8")
    return outputs


def build_field_messages_surface() -> dict[Path, bytes]:
    """Compose authored field messages onto the location-patched MAZE stage."""
    location_outputs = build_dungeon_locations_surface()
    base = location_outputs[DUNGEON_LOCATIONS_MAZE_PATH]
    result = build_field_messages(base)
    manifest = {
        "version": 1,
        "surface": "field.messages",
        "patch_config_sha256": file_sha256(FIELD_MESSAGES_CONFIG_PATH),
        "base": {
            "surface": "dungeon.locations",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                location_outputs[DUNGEON_LOCATIONS_BUILD_MANIFEST_PATH]
            ),
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "output": {
            "file": DUNGEON_MAZE_TARGET,
            "sha256": sha256(result.data),
        },
        "patch_groups": list(dict.fromkeys(patch.group for patch in result.patches)),
        "patches": len(result.patches),
    }
    return {
        **location_outputs,
        FIELD_MESSAGES_OUTPUT_PATH: result.data,
        FIELD_MESSAGES_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_maze_party_panel_surface() -> dict[Path, bytes]:
    """Compose the final compact-name party panel onto field-message MAZE."""
    field_outputs = build_field_messages_surface()
    base = field_outputs[FIELD_MESSAGES_OUTPUT_PATH]
    result = build_maze_party_panel(base)
    manifest = {
        "version": 1,
        "surface": "maze.party_panel",
        "patch_config_sha256": file_sha256(MAZE_PARTY_PANEL_CONFIG_PATH),
        "base": {
            "surface": "field.messages",
            "sha256": sha256(base),
            "manifest_sha256": sha256(
                field_outputs[FIELD_MESSAGES_BUILD_MANIFEST_PATH]
            ),
        },
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            "bytes": result.runtime_used_size,
            "capacity": result.runtime_capacity,
            "arenas": [
                {
                    "address": f"0x{arena.address:08x}",
                    "bytes": arena.used_size,
                    "capacity": arena.capacity,
                }
                for arena in result.runtime_arenas
            ],
        },
        "output": {"file": DUNGEON_MAZE_TARGET, "sha256": sha256(result.data)},
        "patch_groups": list(
            dict.fromkeys(patch.group for patch in result.patches)
        ),
        "patches": len(result.patches),
    }
    return {
        **field_outputs,
        FIELD_MESSAGES_OUTPUT_PATH: result.data,
        MAZE_PARTY_PANEL_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def build_save_load_surface() -> dict[Path, bytes]:
    """Build SAVE and LOAD together before their visual assets are repacked."""
    result = build_save_load_ui()
    manifest = {
        "version": 1,
        "surface": "save_load.ui",
        "patch_config_sha256": file_sha256(SAVE_LOAD_CONFIG_PATH),
        "asset_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.asset_files
        },
        "runtime_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.runtime_input_files
        },
        "source_inputs": dict(result.source_inputs),
        "assembly_inputs": {
            path.relative_to(SATURN_ROOT.parent).as_posix(): file_sha256(path)
            for path in result.assembly_files
        },
        "runtime": {
            target: {
                component: {
                    "bytes": result.runtime_used_sizes[target][component],
                    "capacity": result.runtime_capacities[target][component],
                }
                for component in result.runtime_used_sizes[target]
            }
            for target in SAVE_LOAD_TARGETS
        },
        "outputs": {
            target: {"sha256": sha256(result.data[target])}
            for target in SAVE_LOAD_TARGETS
        },
        "patch_groups": {
            target: list(
                dict.fromkeys(patch.group for patch in result.patches[target])
            )
            for target in SAVE_LOAD_TARGETS
        },
        "patches": {
            target: len(result.patches[target]) for target in SAVE_LOAD_TARGETS
        },
    }
    return {
        **{
            SAVE_LOAD_OUTPUT_PATHS[target]: result.data[target]
            for target in SAVE_LOAD_TARGETS
        },
        SAVE_LOAD_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


def _save_load_visual_spans() -> dict[str, tuple[tuple[int, int], ...]]:
    """Load the four visual-owned storage-selector spans for each target."""
    document = json.loads(
        SAVE_LOAD_VISUAL_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    if document.get("version") != 2 or document.get("disc") != "game":
        raise ValueError("SAVE/LOAD visual ownership manifest is unsupported")
    images = document.get("images")
    if not isinstance(images, list):
        raise ValueError("SAVE/LOAD visual ownership manifest is malformed")
    rows = [
        row
        for row in images
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and row["path"].startswith(SAVE_LOAD_VISUAL_PREFIX)
    ]
    if {row["path"] for row in rows} != SAVE_LOAD_VISUAL_PATHS:
        raise ValueError(
            "SAVE/LOAD visual ownership must contain exactly the four storage "
            "selector images"
        )

    result: dict[str, tuple[tuple[int, int], ...]] = {}
    for target in SAVE_LOAD_TARGETS:
        spans = []
        for row in rows:
            targets = row.get("targets")
            if not isinstance(targets, list):
                raise ValueError(f"{row['path']}: visual targets are malformed")
            matches = [
                image
                for image in targets
                if isinstance(image, dict) and image.get("source") == target
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"{row['path']}: expected one {target} visual target"
                )
            image = matches[0]
            if (
                image.get("encoding") != "rgb555"
                or image.get("layout") != "linear"
            ):
                raise ValueError(f"{row['path']}: unsupported visual target layout")
            try:
                start = int(image["offset"])
                byte_length = int(image["width"]) * int(image["height"]) * 2
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"{row['path']}: invalid visual target geometry"
                ) from error
            if start < 0 or byte_length <= 0:
                raise ValueError(f"{row['path']}: invalid visual target span")
            spans.append((start, start + byte_length))
        spans.sort()
        if any(
            current[0] < previous[1]
            for previous, current in zip(spans, spans[1:])
        ):
            raise ValueError(f"{target}: visual-owned spans overlap")
        result[target] = tuple(spans)
    return result


def _verify_save_load_install(
    target: str,
    expected: bytes,
    installed: bytes,
    visual_spans: tuple[tuple[int, int], ...],
) -> None:
    """Compare an installed target while leaving visual-owned bytes downstream."""
    if len(installed) != len(expected):
        raise ValueError(f"installed {target} has the wrong size")
    cursor = 0
    for start, end in visual_spans:
        if start < cursor or end > len(expected):
            raise ValueError(f"{target}: visual-owned span lies outside the target")
        if installed[cursor:start] != expected[cursor:start]:
            raise ValueError(f"installed {target} has stale non-visual engine bytes")
        cursor = end
    if installed[cursor:] != expected[cursor:]:
        raise ValueError(f"installed {target} has stale non-visual engine bytes")


def install_save_load_surface(*, check: bool) -> None:
    """Install engine outputs, or verify them beneath the later visual overlays."""
    visual_spans = _save_load_visual_spans()
    generated: dict[str, bytes] = {}
    for target in SAVE_LOAD_TARGETS:
        source = SAVE_LOAD_OUTPUT_PATHS[target]
        if not source.is_file():
            raise ValueError(f"SAVE/LOAD engine output is missing: {source}")
        generated[target] = source.read_bytes()

    for target, expected in generated.items():
        destination = SAVE_LOAD_INSTALL_ROOT / target
        if check:
            if not destination.is_file():
                raise ValueError(
                    f"installed SAVE/LOAD target is missing: {destination}"
                )
            _verify_save_load_install(
                target,
                expected,
                destination.read_bytes(),
                visual_spans[target],
            )
            print(f"verified non-visual SAVE/LOAD engine bytes in {target}")
        else:
            _atomic_write(destination, expected)
            print(f"installed SAVE/LOAD engine output {target}")


def install_profile_entry_surface(*, check: bool) -> None:
    """Install NAME.BIN exactly, or verify the installed terminal image."""
    if not PROFILE_ENTRY_OUTPUT_PATH.is_file():
        raise ValueError(
            f"Profile Entry engine output is missing: {PROFILE_ENTRY_OUTPUT_PATH}"
        )
    expected = PROFILE_ENTRY_OUTPUT_PATH.read_bytes()
    if check:
        if not PROFILE_ENTRY_INSTALL_PATH.is_file():
            raise ValueError(
                f"installed Profile Entry target is missing: "
                f"{PROFILE_ENTRY_INSTALL_PATH}"
            )
        if PROFILE_ENTRY_INSTALL_PATH.read_bytes() != expected:
            raise ValueError("installed NAME.BIN has stale Profile Entry bytes")
        print("verified installed Profile Entry engine output NAME.BIN")
    else:
        _atomic_write(PROFILE_ENTRY_INSTALL_PATH, expected)
        print("installed Profile Entry engine output NAME.BIN")


def _verify_compendium_text_install(
    target: str, expected: bytes, installed: bytes
) -> None:
    if len(installed) != len(expected):
        raise ValueError(f"installed compendium target has wrong size: {target}")
    if target == COMPENDIUM_TEXT_TARGET:
        matches = installed == expected
    else:
        start = COMPENDIUM_PROFILE_TAIL_OFFSET
        end = start + COMPENDIUM_PROFILE_TAIL_BYTES
        matches = installed[start:end] == expected[start:end]
    if not matches:
        raise ValueError(f"installed compendium text is stale in {target}")


def install_compendium_text_surface(*, check: bool) -> None:
    """Install all compendium text, or verify text tails beneath visual edits."""
    if not COMPENDIUM_TEXT_BUILD_PATH.is_file():
        raise ValueError(
            f"compendium text manifest is missing: {COMPENDIUM_TEXT_BUILD_PATH}"
        )
    manifest = json.loads(COMPENDIUM_TEXT_BUILD_PATH.read_text(encoding="utf-8"))
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("surface") != "compendium.text"
        or not isinstance(outputs, dict)
        or len(outputs) != 293
        or COMPENDIUM_TEXT_TARGET not in outputs
        or sum(name.startswith("DVL_") and name.endswith(".DAT") for name in outputs)
        != 292
    ):
        raise ValueError("compendium text manifest target inventory drifted")
    for target, contract in outputs.items():
        source = COMPENDIUM_TEXT_OUTPUT_ROOT / target
        if not source.is_file():
            raise ValueError(f"compendium text output is missing: {source}")
        expected = source.read_bytes()
        if (
            not isinstance(contract, dict)
            or contract.get("bytes") != len(expected)
            or contract.get("sha256") != sha256(expected)
        ):
            raise ValueError(f"compendium text manifest is stale for {target}")
        destination = COMPENDIUM_INSTALL_ROOT / target
        if check:
            if not destination.is_file():
                raise ValueError(f"installed compendium target is missing: {destination}")
            installed = destination.read_bytes()
            _verify_compendium_text_install(target, expected, installed)
        else:
            _atomic_write(destination, expected)
    print(
        f"{'verified' if check else 'installed'} 293 compendium text targets"
    )


def _atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _publish(outputs: dict[Path, bytes], *, check: bool) -> None:
    stale = [
        path
        for path, value in outputs.items()
        if not path.is_file() or path.read_bytes() != value
    ]
    if check:
        if stale:
            raise ValueError(
                "stale engine outputs: "
                + ", ".join(str(path.relative_to(SATURN_ROOT)) for path in stale)
            )
        return
    for path, value in outputs.items():
        if not path.is_file() or path.read_bytes() != value:
            _atomic_write(path, value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "surface",
        nargs="?",
        default="event.dialogue",
        choices=(
            "event.dialogue",
            "fusion.menu",
            "event.name_inserts",
            "battle.negotiation",
            "battle.ui",
            "comp.menu",
            "equipment.ui",
            "facilities.status_ui",
            "fmv.subtitles",
            "status.ui",
            "options.ui",
            "level_up.ui",
            "map_3d.analyze",
            "dungeon.locations",
            "field.messages",
            "maze.party_panel",
            "save_load.ui",
            "profile_entry.ui",
            "map_2d.ui",
            "horoscope.ui",
            "credits.ui",
            "diagnostics.ui",
            "portrait_scene.ui",
            "compendium.text",
        ),
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--install",
        action="store_true",
        help=(
            "install a terminal Profile Entry, SAVE/LOAD, or compendium output, "
            "or verify its installed engine-owned bytes"
        ),
    )
    arguments = parser.parse_args()
    try:
        builders = {
            "event.dialogue": build_event_dialogue,
            "fusion.menu": build_fusion_surface,
            "event.name_inserts": build_event_name_inserts_surface,
            "battle.negotiation": build_battle_negotiation,
            "battle.ui": build_battle_ui,
            "comp.menu": build_comp_menu,
            "equipment.ui": build_equipment_surface,
            "facilities.status_ui": build_facilities_status_surface,
            "fmv.subtitles": build_fmv_subtitle_surface,
            "status.ui": build_status_surface,
            "options.ui": build_options_surface,
            "level_up.ui": build_level_up_surface,
            "map_3d.analyze": build_analyze_surface,
            "dungeon.locations": build_dungeon_locations_surface,
            "field.messages": build_field_messages_surface,
            "maze.party_panel": build_maze_party_panel_surface,
            "save_load.ui": build_save_load_surface,
            "profile_entry.ui": build_profile_entry_surface,
            "map_2d.ui": build_map_2d_surface,
            "horoscope.ui": build_horoscope_surface,
            "credits.ui": build_credits_surface,
            "diagnostics.ui": build_diagnostics_surface,
            "portrait_scene.ui": build_portrait_scene_surface,
            "compendium.text": build_compendium_text_surface,
        }
        if arguments.install:
            if arguments.surface == "save_load.ui":
                install_save_load_surface(check=arguments.check)
            elif arguments.surface == "profile_entry.ui":
                install_profile_entry_surface(check=arguments.check)
            elif arguments.surface == "compendium.text":
                install_compendium_text_surface(check=arguments.check)
            else:
                raise ValueError(
                    "--install is supported only for profile_entry.ui, "
                    "save_load.ui, and compendium.text"
                )
        else:
            _publish(builders[arguments.surface](), check=arguments.check)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(
        f"{'verified' if arguments.check else 'built'} "
        f"{arguments.surface} engine {'installation' if arguments.install else 'patch'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
