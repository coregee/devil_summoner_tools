"""Checked migration of mature Saturn battle text into shared assets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en" / "shared" / "text" / "corpus"
CORPUS_ROOT = ROOT / "saturn" / "text" / "corpus" / "game"
ASSET_ROOT = ROOT / "assets" / "text"
BINDING_ROOT = ROOT / "saturn" / "text" / "bindings"

MATURE_CONSOLE = MATURE_ROOT / "battle" / "console" / "message_table.json"
MATURE_DEMON_CHAT = (
    MATURE_ROOT / "battle" / "demon_chat" / "surface_text.json"
)
MATURE_CONDITIONS = MATURE_ROOT / "battle" / "condition_messages.json"
MATURE_SYSTEM = MATURE_ROOT / "battle" / "system_text.json"
MATURE_DEBUG = MATURE_ROOT / "battle" / "diagnostics.json"
MATURE_BATTLE_HELP = MATURE_ROOT / "command_menu" / "help" / "battle.json"
MATURE_GENERAL_HELP = MATURE_ROOT / "command_menu" / "help" / "general.json"

PHYSICAL_CONSOLE = CORPUS_ROOT / "pointer" / "btl_mes.json"
PHYSICAL_DEMON_CHAT = CORPUS_ROOT / "pointer" / "btl_srf.json"
PHYSICAL_CONDITIONS = (
    CORPUS_ROOT / "fixed" / "combat_condition_messages.json"
)
PHYSICAL_SYSTEM = CORPUS_ROOT / "addressed" / "combat_system.json"
PHYSICAL_DEBUG = CORPUS_ROOT / "addressed" / "combat_debug.json"
PHYSICAL_BATTLE_HELP = CORPUS_ROOT / "fixed" / "btl_help.json"
PHYSICAL_GENERAL_HELP = CORPUS_ROOT / "fixed" / "normhelp.json"

NAMED_TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
NON_PLACEHOLDER_NAMES = {"BEAT", "WAIT", "maru_symbol", "n"}
PLACEHOLDER_TYPES = {
    "NUM": "number",
    "demon_name": "demon_name",
}

CONSOLE_KEYS = (
    "condition_dead",
    "condition_undead",
    "condition_stone",
    "condition_paralyzed",
    "condition_vamp",
    "condition_mirror",
    "condition_card",
    "condition_charmed",
    "condition_frozen",
    "condition_shocked",
    "condition_asleep",
    "condition_bound",
    "condition_panicked",
    "condition_happy",
    "condition_poisoned",
    "condition_muted",
    "resource_hp",
    "resource_mp",
    "resource_hp_and_mp",
    "resource_max_hp",
    "stat_attack",
    "stat_defense",
    "stat_accuracy",
    "stat_magic_power",
    "stat_level",
    "current_status",
    "command_sword",
    "command_gun",
    "command_dynamic",
    "command_dynamic_bracketed",
    "command_comp",
    "command_guard",
    "command_move",
    "command_return",
    "command_escape",
    "command_guard_alternate",
    "command_attack",
    "command_boycott",
    "command_go",
    "command_offense",
    "command_defense",
    "command_magic",
    "command_extra",
    "result_critical",
    "result_fatal",
    "result_reflect",
    "result_physical_reflect",
    "result_magic_reflect",
    "result_dynamic_reflect",
    "result_death_guard",
    "result_drain",
    "result_damage",
    "result_no_effect",
    "result_already_active",
    "result_dodge",
    "result_miss",
    "result_out_of_range",
    "result_resource_empty",
    "result_insufficient_resource",
    "result_resource_recovery",
    "result_status_recovery",
    "result_calmed_down",
    "result_revived",
    "result_stat_up",
    "result_stat_down",
    "result_barrier_up",
    "result_repel_up",
    "result_kaja_removed",
    "result_kunda_removed",
    "result_protect",
    "result_a_shikai_removed",
    "result_no_ammo",
    "result_shut_down",
    "result_dynamic_status",
    "command_attack_alternate",
    "command_offense_plain",
    "command_defense_plain",
    "command_magic_plain",
    "command_extra_plain",
    "comp_unit_healed",
    "comp_unit_revived",
    "result_not_possessed",
)

BATTLE_HELP_KEYS = (
    "fight",
    "talk",
    "escape",
    "auto_settings",
    "sword",
    "gun",
    "summon",
    "magic",
    "item",
    "move",
    "guard",
    "go",
    "offense",
    "defense",
    "return",
    "attack",
    "extra",
    "auto_preset",
    "auto_repeat",
)

GENERAL_HELP_KEYS = (
    "party_setup",
    "magic_menu",
    "items_menu",
    "equipment_menu",
    "status_details",
    "reposition_source",
    "reposition_destination",
    "summon_demon_select",
    "summon_demon_destination",
    "return_demon",
    "remove_demon_warning",
    "formation_error",
    "magic_caster",
    "magic_target",
    "item_target",
    "item_discard",
    "equipped_item_warning",
    "equipment_member",
    "equipment_slot",
    "recommended_equipment",
    "remove_equipment",
    "status_member",
    "key_items",
    "alignment_error",
)

DEBUG_KEYS = (
    "ellipsis_six",
    "ellipsis_seven",
    "ellipsis_eight",
    "ellipsis_nine",
    "bug",
    "cannot_talk_to_this",
    "field_wk",
    "field_no",
    "field_bad",
    "field_s",
    "field_dcode",
    "field_exist",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def asset_entry(row: dict[str, Any]) -> dict[str, Any]:
    reference = row["jp"]
    translation = row["tr"]
    names = {
        name
        for value in (reference, translation)
        for name in NAMED_TOKEN_RE.findall(value)
        if name not in NON_PLACEHOLDER_NAMES
    }
    unknown = names - PLACEHOLDER_TYPES.keys()
    if unknown:
        raise ValueError(f"unclassified battle placeholders: {sorted(unknown)}")
    field: dict[str, Any] = {
        "reference": reference,
        "translation": translation,
    }
    if row.get("reviewed"):
        field["reviewed"] = True
    if row.get("note"):
        field["note"] = row["note"]
    entry: dict[str, Any] = {"text": field}
    if names:
        entry["placeholders"] = {
            name: PLACEHOLDER_TYPES[name] for name in sorted(names)
        }
    return entry


def write_asset_and_binding(
    asset_path: str,
    entries: dict[str, Any],
    binding_name: str,
    records: dict[str, str],
    surface: str,
    *,
    glyph_equivalence: dict[str, str] | None = None,
) -> None:
    write_json(
        ASSET_ROOT / asset_path,
        {"version": 1, "kind": "surface_catalog", "entries": entries},
    )
    binding: dict[str, Any] = {
        "version": 1,
        "asset": asset_path,
        "records": records,
    }
    if glyph_equivalence:
        binding["glyph_equivalence"] = glyph_equivalence
    binding["field_surfaces"] = {"text": [surface]}
    write_json(BINDING_ROOT / binding_name, binding)


def migrate_console() -> None:
    mature = read_json(MATURE_CONSOLE)
    physical = read_json(PHYSICAL_CONSOLE)
    if len(mature) != 358 or len(physical) != 358:
        raise ValueError("unexpected BTL_MES inventory")
    if len(CONSOLE_KEYS) != 82:
        raise ValueError("console semantic key inventory changed")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for index, key in zip(range(276, 358), CONSOLE_KEYS, strict=True):
        mature_row = mature[index]
        physical_row = physical[index]
        normalized = physical_row["reference"].replace("{GLYPH:4b}", "殺")
        if mature_row["excluded"] or not mature_row["jp"]:
            raise ValueError(f"BTL_MES row {index} is unexpectedly blank")
        if normalized != mature_row["jp"]:
            raise ValueError(f"BTL_MES reference mismatch at row {index}")
        expected_id = f"game.btl_mes.p{index:04d}"
        if physical_row["id"] != expected_id:
            raise ValueError(f"BTL_MES physical identity changed at row {index}")
        entries[key] = asset_entry(mature_row)
        records[expected_id] = f"{key}.text"
    write_asset_and_binding(
        "battle/console.json",
        entries,
        "battle_console.json",
        records,
        "battle.console",
        glyph_equivalence={"4b": "殺"},
    )


def migrate_demon_chat() -> None:
    mature = read_json(MATURE_DEMON_CHAT)
    physical = read_json(PHYSICAL_DEMON_CHAT)
    if len(mature) != 363 or len(physical) != 363:
        raise ValueError("unexpected BTL_SRF inventory")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for index, (mature_row, physical_row) in enumerate(
        zip(mature, physical, strict=True)
    ):
        if mature_row["excluded"]:
            if mature_row["jp"] or physical_row["reference"]:
                raise ValueError(f"BTL_SRF excluded row {index} is not blank")
            continue
        if physical_row["reference"] != mature_row["jp"]:
            raise ValueError(f"BTL_SRF reference mismatch at row {index}")
        expected_id = f"game.btl_srf.p{index:04d}"
        if physical_row["id"] != expected_id:
            raise ValueError(f"BTL_SRF physical identity changed at row {index}")
        key = f"dialogue_{len(entries):04d}"
        entries[key] = asset_entry(mature_row)
        records[expected_id] = f"{key}.text"
    if len(entries) != 203:
        raise ValueError("unexpected visible BTL_SRF inventory")
    write_asset_and_binding(
        "battle/demon_chat.json",
        entries,
        "battle_demon_chat.json",
        records,
        "battle.demon_chat",
    )


def migrate_condition_fallbacks() -> None:
    mature = read_json(MATURE_CONDITIONS)
    physical = read_json(PHYSICAL_CONDITIONS)
    if len(mature) != 113 or len(physical) != 113:
        raise ValueError("unexpected combat-condition inventory")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for mature_row, physical_row in zip(mature, physical, strict=True):
        kind = mature_row["kind"]
        if not (kind.endswith("_fallback") or kind == "comp_signal_happy"):
            continue
        if mature_row["jp"] != physical_row["reference"]:
            raise ValueError(f"condition reference mismatch for {kind}")
        key = kind.removesuffix("_fallback")
        entries[key] = asset_entry(mature_row)
        records[physical_row["id"]] = f"{key}.text"
    if len(entries) != 8:
        raise ValueError("unexpected unowned condition fallback inventory")
    write_asset_and_binding(
        "battle/condition_fallbacks.json",
        entries,
        "battle_condition_fallbacks.json",
        records,
        "battle.negotiation_dialogue",
    )


def migrate_help(
    mature_path: Path,
    physical_path: Path,
    keys: tuple[str, ...],
    asset_path: str,
    binding_name: str,
    surface: str,
) -> None:
    mature = read_json(mature_path)
    physical = read_json(physical_path)
    if len(mature) != len(physical) or len(mature) != len(keys):
        raise ValueError(f"unexpected {asset_path} inventory")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for key, mature_row, physical_row in zip(
        keys, mature, physical, strict=True
    ):
        if mature_row["excluded"] or mature_row["jp"] != physical_row["reference"]:
            raise ValueError(f"help reference mismatch for {key}")
        entries[key] = asset_entry(mature_row)
        records[physical_row["id"]] = f"{key}.text"
    write_asset_and_binding(
        asset_path,
        entries,
        binding_name,
        records,
        surface,
    )


def migrate_provisioning() -> None:
    mature = read_json(MATURE_SYSTEM)
    physical = read_json(PHYSICAL_SYSTEM)
    if len(mature) != 4 or len(physical) != 4:
        raise ValueError("unexpected battle provisioning inventory")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for mature_row, physical_row in zip(mature, physical, strict=True):
        key = mature_row["kind"]
        if mature_row["jp"] != physical_row["reference"]:
            raise ValueError(f"provisioning reference mismatch for {key}")
        entries[key] = asset_entry(mature_row)
        records[physical_row["id"]] = f"{key}.text"
    write_asset_and_binding(
        "battle/provisioning.json",
        entries,
        "battle_provisioning.json",
        records,
        "battle.negotiation_choice",
    )


def migrate_debug() -> None:
    mature = read_json(MATURE_DEBUG)
    physical = read_json(PHYSICAL_DEBUG)
    if len(mature) != 14 or len(physical) != 14 or len(DEBUG_KEYS) != 12:
        raise ValueError("unexpected battle-debug inventory")
    if [row["jp"] for row in mature[:2]] != ["葛葉キョウジ", "レイ"]:
        raise ValueError("battle-debug actor identities changed")
    if [row["reference"] for row in physical[:2]] != ["葛葉キョウジ", "レイ"]:
        raise ValueError("physical battle-debug actor identities changed")
    entries: dict[str, Any] = {}
    records: dict[str, str] = {}
    for key, mature_row, physical_row in zip(
        DEBUG_KEYS, mature[2:], physical[2:], strict=True
    ):
        if mature_row["jp"] != physical_row["reference"]:
            raise ValueError(f"battle-debug reference mismatch for {key}")
        entries[key] = asset_entry(mature_row)
        records[physical_row["id"]] = f"{key}.text"
    write_asset_and_binding(
        "battle/debug.json",
        entries,
        "battle_debug.json",
        records,
        "battle.debug_text",
    )
    write_json(
        BINDING_ROOT / "battle_debug_characters.json",
        {
            "version": 1,
            "asset": "characters.json",
            "records": {
                physical[0]["id"]: "kyouji_kuzunoha.battle_test_name",
                physical[1]["id"]: "rei_reiho.battle_test_name",
            },
            "field_surfaces": {"battle_test_name": ["battle.debug_text"]},
        },
    )


def main() -> None:
    migrate_console()
    migrate_demon_chat()
    migrate_condition_fallbacks()
    migrate_help(
        MATURE_BATTLE_HELP,
        PHYSICAL_BATTLE_HELP,
        BATTLE_HELP_KEYS,
        "battle/help.json",
        "battle_help.json",
        "battle.help",
    )
    migrate_help(
        MATURE_GENERAL_HELP,
        PHYSICAL_GENERAL_HELP,
        GENERAL_HELP_KEYS,
        "ui/command_help.json",
        "command_help.json",
        "comp.help",
    )
    migrate_provisioning()
    migrate_debug()


if __name__ == "__main__":
    main()
