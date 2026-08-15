"""Checked migration of Saturn status-screen vocabulary into shared assets."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"
MATURE_EQUIPMENT = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "equipment_screen"
    / "ui_terms.json"
)
MATURE_STATUS = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "status_screen" / "ui_terms.json"
)
MATURE_STATUS_MODEL = (
    MATURE_ROOT
    / "saturn"
    / "engine"
    / "script"
    / "status_screen"
    / "model.py"
)
NORMCOM = ROOT / "saturn" / "rom" / "extracted" / "game" / "NORMCOM.BIN"
STATUS_OUTPUT = ROOT / "assets" / "text" / "ui" / "status.json"
COMMAND_OUTPUT = ROOT / "assets" / "text" / "battle" / "commands.json"
ALIGNMENT_OUTPUT = ROOT / "assets" / "text" / "terminology" / "alignments.json"

NORMCOM_SHA256 = "983d84ad48c0a497715633c0d2e380743c52e4b1644422ed027ac27e52a2aa9a"
BITMAP_REGIONS = {
    "attack": (0x2376C, 0x23BEC, "86c69aedbccf3b6417f9d544b86d2718ffc6ad705b00b019769dedcb735c79aa"),
    "accuracy": (0x23BEC, 0x2406C, "d7c9a5237611fd0953a7838b24ddb754e9d2354c104d2a8c8283f956e5ce37d9"),
    "loyalty_and_personalities": (
        0x2406C,
        0x269AC,
        "9ce5065a769443c3b6075eae19ff42ec207b16b135e61b29e65b91b64bd48bc9",
    ),
}

BASE_REFERENCES = {
    "strength": "力",
    "intelligence": "知",
    "magic": "魔",
    "vitality": "耐",
    "agility": "速",
    "luck": "運",
}
DERIVED_REFERENCES = {
    "sword_attack": "剣攻撃力",
    "sword_accuracy": "剣命中力",
    "gun_attack": "銃攻撃力",
    "gun_accuracy": "銃命中力",
    "defense": "防衛力",
    "evasion": "回避力",
    "magic_power": "魔法威力",
    "magic_defense": "魔法防衛",
}
DERIVED_MATURE_KEYS = {
    "sword_attack": "sword_attack",
    "sword_accuracy": "sword_accuracy",
    "gun_attack": "gun_attack",
    "gun_accuracy": "gun_accuracy",
    "defense": "defense",
    "evasion": "evasion",
    "magic_power": "magic_power",
    "magic_defense": "magic_effect",
}
PERSONALITY_REFERENCES = (
    "忠誠度",
    "剛健",
    "凶暴",
    "短気",
    "狡猾",
    "高慢",
    "温順",
    "臆病",
    "冷静",
    "慎重",
    "虚心",
)
PERSONALITY_KEYS = (
    "loyalty",
    "personality_sturdy",
    "personality_fierce",
    "personality_impatient",
    "personality_sly",
    "personality_prideful",
    "personality_gentle",
    "personality_cowardly",
    "personality_calm",
    "personality_cautious",
    "personality_impartial",
)

ASCII_FIELDS = {
    "experience": (0x132DC, 4, "EXP"),
    "level": (0x135B0, 4, "LV"),
    "personality_type": (0x13DE8, 8, "TYPE"),
    "hit_points": (0x14298, 4, "HP"),
    "magic_points": (0x142A4, 4, "MP"),
    "control_first": (0x15DA0, 4, "1ST"),
    "control_second": (0x15DA4, 4, "2ND"),
    "control_third": (0x15DA8, 4, "3RD"),
    "control_fourth": (0x15DAC, 4, "4TH"),
    "control_error": (0x15DB0, 4, "ERR"),
    "control": (0x15DE4, 6, "CTRL"),
    "next_experience": (0x15FC4, 8, "NEXT"),
    "summon_cost": (0x15FCC, 4, "CP"),
    "alignment_law": (0x16574, 4, "LAW"),
    "alignment_neutral": (0x16578, 8, "NEUTRAL"),
    "alignment_chaos": (0x16580, 8, "CHAOS"),
    "command_sword": (0x16594, 8, "SWORD"),
    "command_attack": (0x1659C, 8, "ATTACK"),
    "command_gun": (0x165A4, 4, "GUN"),
    "command_guard": (0x165A8, 8, "GUARD"),
    "command_go": (0x165B0, 4, "GO"),
    "command_offense": (0x165B4, 8, "OFFENSE"),
    "command_defense": (0x165BC, 8, "DEFENSE"),
    "auto": (0x165C4, 6, "AUTO"),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_values(section: dict[str, Any]) -> dict[str, str]:
    return {key: value["text"] for key, value in section.items()}


def personality_labels() -> tuple[str, ...]:
    tree = ast.parse(MATURE_STATUS_MODEL.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "PERSONALITY_LABELS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, tuple) or not all(
                isinstance(label, str) for label in value
            ):
                break
            return value
    raise ValueError("mature PERSONALITY_LABELS inventory is missing")


def verify_stock_bitmaps() -> None:
    source = NORMCOM.read_bytes()
    if hashlib.sha256(source).hexdigest() != NORMCOM_SHA256:
        raise ValueError("NORMCOM.BIN is not the verified retail source")
    for name, (start, end, expected) in BITMAP_REGIONS.items():
        if hashlib.sha256(source[start:end]).hexdigest() != expected:
            raise ValueError(f"NORMCOM.BIN {name} bitmap region changed")


def stock_ascii_fields() -> dict[str, str]:
    source = NORMCOM.read_bytes()
    if hashlib.sha256(source).hexdigest() != NORMCOM_SHA256:
        raise ValueError("NORMCOM.BIN is not the verified retail source")
    values: dict[str, str] = {}
    for name, (offset, capacity, expected) in ASCII_FIELDS.items():
        field_bytes = source[offset : offset + capacity]
        try:
            end = field_bytes.index(0)
        except ValueError as error:
            raise ValueError(f"NORMCOM.BIN {name} has no NUL terminator") from error
        if any(field_bytes[end + 1 :]):
            raise ValueError(f"NORMCOM.BIN {name} has nonzero trailing storage")
        value = field_bytes[:end].decode("ascii")
        if value != expected:
            raise ValueError(f"NORMCOM.BIN {name} changed from {expected!r}")
        values[name] = value
    return values


def field(reference: str, translation: str, *, note: str | None = None) -> dict:
    result = {"reference": reference, "translation": translation}
    if note is not None:
        result["note"] = note
    return {"text": result}


def build_asset() -> dict[str, Any]:
    verify_stock_bitmaps()
    ascii_fields = stock_ascii_fields()
    equipment = read_json(MATURE_EQUIPMENT)
    status = read_json(MATURE_STATUS)
    equipment_base = text_values(equipment["base_stats"])
    equipment_derived = text_values(equipment["derived_stats"])
    status_terms = text_values(status["terms"])
    personalities = personality_labels()
    if tuple(personalities) != (
        "Loyalty",
        "Sturdy",
        "Fierce",
        "Impatient",
        "Sly",
        "Prideful",
        "Gentle",
        "Cowardly",
        "Calm",
        "Cautious",
        "Impartial",
    ):
        raise ValueError("mature status personality translations changed")
    if any(equipment_base[key] != status_terms[key] for key in BASE_REFERENCES):
        raise ValueError("mature base-stat translations diverged between surfaces")
    if status_terms["loyalty"] != personalities[0]:
        raise ValueError("mature loyalty translation diverged between surfaces")

    entries: dict[str, dict[str, Any]] = {
        key: field(reference, equipment_base[key])
        for key, reference in BASE_REFERENCES.items()
    }
    entries.update(
        {
            key: field(reference, equipment_derived[DERIVED_MATURE_KEYS[key]])
            for key, reference in DERIVED_REFERENCES.items()
        }
    )
    entries["attack"] = field("攻撃力", "Attack")
    entries["accuracy"] = field("命中力", "Accuracy")
    entries["loyalty"] = field(
        f"{PERSONALITY_REFERENCES[0]} {{loyalty}}",
        f"{personalities[0]} {{loyalty}}",
    )
    entries["loyalty"]["placeholders"] = {"loyalty": "number"}
    entries["personality_type"] = field(
        f'{ascii_fields["personality_type"]} {{personality}}',
        f'{ascii_fields["personality_type"]} {{personality}}',
        note=(
            "The Saturn status screen composes this fixed Latin prefix with "
            "the selected localized personality value."
        ),
    )
    entries["personality_type"]["placeholders"] = {
        "personality": "personality_label"
    }
    entries.update(
        {
            key: field(reference, translation)
            for key, reference, translation in zip(
                PERSONALITY_KEYS[1:],
                PERSONALITY_REFERENCES[1:],
                personalities[1:],
                strict=True,
            )
        }
    )
    templates = {
        "level": (
            {"level": "number"},
            f'{ascii_fields["level"]} {{level}}',
        ),
        "hit_points": (
            {"current_hp": "number", "maximum_hp": "number"},
            f'{ascii_fields["hit_points"]} {{current_hp}}/{{maximum_hp}}',
        ),
        "magic_points": (
            {"current_mp": "number", "maximum_mp": "number"},
            f'{ascii_fields["magic_points"]} {{current_mp}}/{{maximum_mp}}',
        ),
        "experience": (
            {"experience": "number"},
            f'{ascii_fields["experience"]} {{experience}}',
        ),
        "next_experience": (
            {"experience_to_next": "number"},
            f'{ascii_fields["next_experience"]} {{experience_to_next}}',
        ),
        "summon_cost": (
            {"summon_cost": "number"},
            f'{ascii_fields["summon_cost"]} {{summon_cost}}',
        ),
        "auto_setting": (
            {"command": "battle_command"},
            f'{ascii_fields["auto"]} {{command}}',
        ),
        "party_alignment": (
            {"alignment": "alignment_label"},
            "P.A. {alignment}",
        ),
        "control": (
            {"rank": "control_rank"},
            f'{ascii_fields["control"]} {{rank}}',
        ),
    }
    entries.update(
        {
            key: {
                "placeholders": placeholders,
                "text": {"reference": text, "translation": text},
            }
            for key, (placeholders, text) in templates.items()
        }
    )
    for key in (
        "control_first",
        "control_second",
        "control_third",
        "control_fourth",
    ):
        entries[key] = field(ascii_fields[key], ascii_fields[key])
    entries["control_error"] = field(
        ascii_fields["control_error"],
        ascii_fields["control_error"],
        note=(
            "Fallback label selected when the control-order value is outside "
            "the four valid ranks."
        ),
    )
    return {"version": 1, "kind": "surface_catalog", "entries": entries}


def build_command_asset() -> dict[str, Any]:
    ascii_fields = stock_ascii_fields()
    entries = {}
    for key in ("sword", "attack", "gun", "guard", "go", "offense", "defense"):
        value = ascii_fields[f"command_{key}"]
        entries[key] = {
            "name": {"reference": value, "translation": value}
        }
    return {"version": 1, "kind": "entity_catalog", "entries": entries}


def build_alignment_asset() -> dict[str, Any]:
    ascii_fields = stock_ascii_fields()
    entries = {
        key: {
            "party_label": {
                "reference": ascii_fields[f"alignment_{key}"],
                "translation": ascii_fields[f"alignment_{key}"],
            },
            "axis_label": {"reference": axis, "translation": axis},
        }
        for key, axis in (("law", "L"), ("neutral", "N"), ("chaos", "C"))
    }
    entries["light"] = {
        "axis_label": {"reference": "L", "translation": "L"}
    }
    entries["dark"] = {
        "axis_label": {"reference": "D", "translation": "D"}
    }
    return {"version": 1, "kind": "entity_catalog", "entries": entries}


def main() -> None:
    outputs = {
        STATUS_OUTPUT: build_asset(),
        COMMAND_OUTPUT: build_command_asset(),
        ALIGNMENT_OUTPUT: build_alignment_asset(),
    }
    for output, document in outputs.items():
        expected = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
