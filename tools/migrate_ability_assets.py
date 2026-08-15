"""One-off checked migration of mature ability text into semantic assets."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"

MATURE_ABILITIES = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "shared" / "catalogs" / "magic.json"
)
MATURE_CONSOLE = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "battle"
    / "console"
    / "message_table.json"
)
MATURE_PSP_OVERRIDES = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "shared"
    / "catalogs"
    / "psp"
    / "magic_overrides.json"
)
MATURE_PSP_BINDING = (
    MATURE_ROOT / "psp" / "text" / "bindings" / "regdata" / "MAGNAME.json"
)

MAGNAME_CORPUS = (
    ROOT / "saturn" / "text" / "corpus" / "game" / "fixed" / "magname.json"
)
CONSOLE_CORPUS = (
    ROOT / "saturn" / "text" / "corpus" / "game" / "pointer" / "btl_mes.json"
)
ZENSHO_NAME_CORPUS = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "compendium"
    / "fixed"
    / "ability_names.json"
)
MAGNAME_SOURCE = ROOT / "saturn" / "rom" / "extracted" / "game" / "MAGNAME.DAT"

MAGIC_ASSET = ROOT / "assets" / "text" / "magic.json"
SKILL_ASSET = ROOT / "assets" / "text" / "skills.json"
MAGIC_BINDING = ROOT / "saturn" / "text" / "bindings" / "magic.json"
SKILL_BINDING = ROOT / "saturn" / "text" / "bindings" / "skills.json"

RECORD_COUNT = 255
RECORD_SIZE = 0x60
MAGIC_END = 79
CONSOLE_START = 49
CONSOLE_ABILITY_END = 227

CATEGORY_COUNTS = Counter(
    {
        "00000010": 45,
        "00000011": 27,
        "00000012": 5,
        "00000013": 149,
        "00000014": 27,
        "00000000": 2,
    }
)

CURATED_KEYS = {
    113: "demons_lure_a",
    122: "demons_lure_b",
    141: "eight_shooting_stars",
    142: "six_shining_stars",
}

# PSP rows that replace a same-index Saturn reserve with another semantic skill.
# The donor ID is the mature Saturn name record that established the join.
PSP_DORMANT_DONORS = {
    128: "ds.name_description.magname_dat.r000222",
    140: "ds.name_description.magname_dat.r000224",
    224: "ds.name_description.magname_dat.r000412",
}
PSP_ONLY_KEYS = {
    124: "jigoku_nagashi",
    221: "kyuuchaku",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def slug(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(
        r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_value.lower())
    ).strip("_")


def canonical_psp_reference(value: str) -> str:
    """Convert the mature PSP supplement's legacy raw-glyph spelling."""
    return re.sub(
        r"\{([0-9a-fA-F]{4})\}",
        lambda match: f"{{GLYPH:{match.group(1).lower()}}}",
        value,
    )


def canonical_console_reference(value: str) -> str:
    return value.replace("{GLYPH:4b}", "殺")


def physical_ids(index: int) -> tuple[str, str]:
    base = index * RECORD_SIZE
    return (
        f"game.magname.o{base + 4:06x}.name",
        f"game.magname.o{base + 0x0C:06x}.description",
    )


def zensho_physical_id(index: int) -> str:
    return f"compendium.ability_names.o{0x69BE4 + index * 0x10:06x}.text"


def reserve_key(index: int) -> str:
    family = "magic" if index < MAGIC_END else "skill"
    return f"reserved_{family}_{index + 1:03d}"


def main() -> None:
    mature = read_json(MATURE_ABILITIES)
    mature_console = read_json(MATURE_CONSOLE)
    physical = read_json(MAGNAME_CORPUS)
    physical_console = read_json(CONSOLE_CORPUS)
    zensho_names = read_json(ZENSHO_NAME_CORPUS)
    psp_supplement = read_json(MATURE_PSP_OVERRIDES)
    psp_binding = read_json(MATURE_PSP_BINDING)

    assert len(mature) == RECORD_COUNT
    assert len(physical) == RECORD_COUNT * 2
    assert len(mature_console) == len(physical_console) == 358
    assert len(zensho_names) == RECORD_COUNT

    source = MAGNAME_SOURCE.read_bytes()
    assert len(source) == RECORD_COUNT * RECORD_SIZE
    categories = [source[i * RECORD_SIZE : i * RECORD_SIZE + 4].hex() for i in range(RECORD_COUNT)]
    assert Counter(categories) == CATEGORY_COUNTS
    assert set(categories[:MAGIC_END]) <= {
        "00000000",
        "00000010",
        "00000011",
        "00000012",
    }
    assert set(categories[MAGIC_END:]) <= {"00000013", "00000014"}
    assert [i for i, category in enumerate(categories) if category == "00000000"] == [77, 78]

    rows_by_id = {row["id"]: row for row in physical}
    assert len(rows_by_id) == RECORD_COUNT * 2
    for index, row in enumerate(mature):
        name_id, description_id = physical_ids(index)
        assert rows_by_id[name_id]["reference"] == row["name"]["jp"]
        assert rows_by_id[description_id]["reference"] == row["description"]["jp"]

    for physical_row, mature_row in zip(
        physical_console, mature_console, strict=True
    ):
        assert canonical_console_reference(physical_row["reference"]) == mature_row["jp"]

    reserve_indexes = {
        index for index, row in enumerate(mature) if row["name"]["tr"] == "Reserve"
    }
    assert len(reserve_indexes) == 52

    row_keys: dict[int, str] = {}
    for index, row in enumerate(mature):
        key = (
            reserve_key(index)
            if index in reserve_indexes
            else CURATED_KEYS.get(index, slug(row["name"]["tr"]))
        )
        assert re.fullmatch(r"[a-z][a-z0-9_]*", key), (index, row["name"]["tr"], key)
        row_keys[index] = key
    assert len(set(row_keys.values())) == RECORD_COUNT

    psp_rows = {row["record_index"]: row for row in psp_supplement["records"]}
    psp_binding_rows = {
        row["record_index"]: row for row in psp_binding["overrides"]
    }
    psp_alignment = {
        (row["record_index"], field_name): field["translation_alignment"]
        for row in psp_binding["overrides"]
        for field_name, field in row["fields"].items()
    }
    psp_donor_ids = {
        (row["record_index"], field_name): field.get("translation_source_record_id")
        for row in psp_binding["overrides"]
        for field_name, field in row["fields"].items()
        if field.get("translation_source_record_id") is not None
    }
    assert len(psp_alignment) == 212
    assert Counter(psp_alignment.values()) == Counter(
        {"saturn_same_semantics": 108, "psp_revision_untranslated": 104}
    )

    mature_fields_by_id = {
        field["id"]: (index, field_name)
        for index, row in enumerate(mature)
        for field_name, field in row.items()
    }
    assert {
        index: psp_donor_ids[(index, "name")]
        for index in PSP_DORMANT_DONORS
    } == PSP_DORMANT_DONORS

    magic_entries: dict[str, dict[str, object]] = {}
    skill_entries: dict[str, dict[str, object]] = {}
    bindings = {
        "magic": {},
        "skills": {},
    }
    psp_variant_counts: Counter[str] = Counter()
    zensho_variant_count = 0

    for index, row in enumerate(mature):
        key = row_keys[index]
        entries = magic_entries if index < MAGIC_END else skill_entries
        binding_records = bindings["magic" if index < MAGIC_END else "skills"]
        entry: dict[str, object] = {}
        if index in reserve_indexes:
            entry["status"] = "reserve"
            entry["note"] = (
                f"Unused Saturn MAGNAME game ID {index + 1}; retained as a distinct "
                "slot because other releases may repurpose table positions."
            )
        elif index in CURATED_KEYS:
            entry["status"] = "unresolved"
            entry["note"] = (
                "This is one of two text-identical Demon's Lure records. Their "
                "semantic relationship is not inferred without call-site evidence."
            )

        for field_name in ("name", "description"):
            source_field = row[field_name]
            field: dict[str, object] = {
                "reference": source_field["jp"],
                "translation": source_field["tr"],
            }
            variants: dict[str, dict[str, object]] = {}
            if field_name == "name":
                zensho_row = zensho_names[index]
                assert zensho_row["id"] == zensho_physical_id(index)
                zensho_reference = zensho_row["reference"].replace(
                    "{GLYPH:00e3}", "ぷ"
                )
                if zensho_reference != source_field["jp"]:
                    variants["akuma_zensho"] = {
                        "reference": zensho_row["reference"]
                    }
                    zensho_variant_count += 1
            override = psp_rows.get(index, {}).get(field_name)
            if override is not None and index not in {
                *PSP_DORMANT_DONORS,
                *PSP_ONLY_KEYS,
            }:
                psp_reference = canonical_psp_reference(override["jp"])
                assert psp_reference != source_field["jp"]
                alignment = psp_alignment[(index, field_name)]
                variant: dict[str, object] = {"reference": psp_reference}
                if alignment == "psp_revision_untranslated":
                    assert override["tr"] == ""
                    variant["translation"] = ""
                    variant["note"] = (
                        "The PSP source changes this field's meaning or parameters; "
                        "its translation remains explicit review work."
                    )
                    psp_variant_counts["revision"] += 1
                else:
                    assert alignment == "saturn_same_semantics"
                    assert override["tr"] == source_field["tr"]
                    psp_variant_counts["same_semantics"] += 1
                variants["psp"] = variant
            if variants:
                field["variants"] = variants
            entry[field_name] = field

        if (
            index < CONSOLE_ABILITY_END
            and not mature_console[CONSOLE_START + index]["excluded"]
        ):
            console_index = CONSOLE_START + index
            physical_row = physical_console[console_index]
            mature_row = mature_console[console_index]
            assert not mature_row["excluded"]
            assert mature_row["tr"]
            entry["console_text"] = {
                "reference": physical_row["reference"],
                "translation": mature_row["tr"],
            }
            binding_records[physical_row["id"]] = f"{key}.console_text"
        elif index < CONSOLE_ABILITY_END:
            assert index in reserve_indexes or index in {73, 74, 75, 76}

        name_id, description_id = physical_ids(index)
        binding_records[name_id] = f"{key}.name"
        binding_records[description_id] = f"{key}.description"
        binding_records[zensho_physical_id(index)] = f"{key}.name"
        entries[key] = entry

    assert psp_variant_counts == Counter(
        {"same_semantics": 105, "revision": 102}
    )
    assert zensho_variant_count == 28

    # The dormant PSP donor rows belong to established skills, not the Saturn
    # reserve entities at the same table positions.
    for psp_index, donor_id in PSP_DORMANT_DONORS.items():
        donor_index, donor_field = mature_fields_by_id[donor_id]
        assert donor_field == "name"
        donor = skill_entries[row_keys[donor_index]]["name"]
        override_reference = canonical_psp_reference(psp_rows[psp_index]["name"]["jp"])
        if "psp" in donor.get("variants", {}):
            if donor["variants"]["psp"]["reference"] != override_reference:
                assert psp_binding_rows[psp_index]["fields"]["name"]["source_hex"] == (
                    psp_binding_rows[donor_index]["fields"]["name"]["source_hex"]
                )
        else:
            assert donor["reference"] == override_reference

    for psp_index, key in PSP_ONLY_KEYS.items():
        source_field = psp_rows[psp_index]["name"]
        assert psp_alignment[(psp_index, "name")] == "psp_revision_untranslated"
        assert source_field["tr"] == ""
        skill_entries[key] = {
            "status": "unresolved",
            "note": (
                "Dormant PSP-only skill name with no proven Saturn semantic donor; "
                "the English name remains untranslated and visible for review."
            ),
            "name": {
                "reference": canonical_psp_reference(source_field["jp"]),
                "translation": "",
            },
        }

    assert len(magic_entries) == 79
    assert len(skill_entries) == 178
    assert sum(
        len(entry) - ("status" in entry) - ("note" in entry)
        for entry in magic_entries.values()
    ) == 231
    assert sum(
        len(entry) - ("status" in entry) - ("note" in entry)
        for entry in skill_entries.values()
    ) == 480
    assert len(bindings["magic"]) == 310
    assert len(bindings["skills"]) == 654

    binding_variants: dict[str, dict[str, str]] = {"magic": {}, "skills": {}}
    for index, row in enumerate(zensho_names):
        if row["reference"].replace("{GLYPH:00e3}", "ぷ") == mature[index]["name"]["jp"]:
            continue
        family = "magic" if index < MAGIC_END else "skills"
        binding_variants[family][row["id"]] = "akuma_zensho"
    assert sum(map(len, binding_variants.values())) == 28

    field_surfaces = {
        "name": [
            "battle.skill_name",
            "comp.ability_name",
            "compendium.ability_name",
            "status.skill_name",
            "level_up.ability_name",
        ],
        "description": ["battle.help", "comp.help"],
        "console_text": ["battle.console"],
    }
    write_json(
        MAGIC_ASSET,
        {"version": 1, "kind": "entity_catalog", "entries": magic_entries},
    )
    write_json(
        SKILL_ASSET,
        {"version": 1, "kind": "entity_catalog", "entries": skill_entries},
    )
    write_json(
        MAGIC_BINDING,
        {
            "version": 1,
            "asset": "magic.json",
            "records": bindings["magic"],
            "variants": binding_variants["magic"],
            "field_surfaces": field_surfaces,
        },
    )
    write_json(
        SKILL_BINDING,
        {
            "version": 1,
            "asset": "skills.json",
            "records": bindings["skills"],
            "variants": binding_variants["skills"],
            "glyph_equivalence": {"00e3": "ぷ"},
            "field_surfaces": field_surfaces,
        },
    )


if __name__ == "__main__":
    main()
