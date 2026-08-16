"""Build the Saturn runtime patches required by configured text surfaces."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = ENGINE_ROOT.parent
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from engine.surfaces.battle_negotiation import build_battle_negotiation  # noqa: E402
from engine.surfaces.battle_ui import build_battle_ui  # noqa: E402
from engine.surfaces.comp_menu import (  # noqa: E402
    BUILD_PATH as COMP_BUILD_PATH,
    NORMCOM_OUTPUT_PATH as COMP_NORMCOM_OUTPUT_PATH,
    build_comp_menu,
)
from engine.surfaces.equipment_ui import build_equipment_ui  # noqa: E402
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
from engine.surfaces.fusion import (  # noqa: E402
    CONFIG_PATH as FUSION_CONFIG_PATH,
    build_fusion_menu,
)


GENERATED_ROOT = ENGINE_ROOT / "generated" / "game"
EVENT_DIALOGUE_OUTPUT_PATH = EVENT_OUTPUT_PATH
BUILD_MANIFEST_PATH = EVENT_BUILD_PATH
FUSION_OUTPUT_PATH = GENERATED_ROOT / "fusion_menu" / "EVENT.BIN"
FUSION_BUILD_MANIFEST_PATH = GENERATED_ROOT / "fusion_menu_build.json"
EQUIPMENT_EVENT_OUTPUT_PATH = GENERATED_ROOT / "EVENT.BIN"
EQUIPMENT_NORMCOM_OUTPUT_PATH = GENERATED_ROOT / "NORMCOM.BIN"
EQUIPMENT_BUILD_MANIFEST_PATH = GENERATED_ROOT / "equipment_ui_build.json"


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


def build_equipment_surface() -> dict[Path, bytes]:
    """Compose shared equipment consumers onto Fusion and COMP bases."""
    fusion_outputs = build_fusion_surface()
    comp_outputs = build_comp_menu()
    result = build_equipment_ui(
        fusion_outputs[FUSION_OUTPUT_PATH],
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
                "surface": "fusion.menu",
                "sha256": sha256(fusion_outputs[FUSION_OUTPUT_PATH]),
                "manifest_sha256": sha256(
                    fusion_outputs[FUSION_BUILD_MANIFEST_PATH]
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
        **fusion_outputs,
        **comp_outputs,
        EQUIPMENT_EVENT_OUTPUT_PATH: result.event,
        EQUIPMENT_NORMCOM_OUTPUT_PATH: result.normcom,
        EQUIPMENT_BUILD_MANIFEST_PATH: (
            json.dumps(manifest, indent=2) + "\n"
        ).encode("utf-8"),
    }


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
            "battle.negotiation",
            "battle.ui",
            "comp.menu",
            "equipment.ui",
        ),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        builders = {
            "event.dialogue": build_event_dialogue,
            "fusion.menu": build_fusion_surface,
            "battle.negotiation": build_battle_negotiation,
            "battle.ui": build_battle_ui,
            "comp.menu": build_comp_menu,
            "equipment.ui": build_equipment_surface,
        }
        _publish(builders[arguments.surface](), check=arguments.check)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(
        f"{'verified' if arguments.check else 'built'} "
        f"{arguments.surface} engine patch"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
