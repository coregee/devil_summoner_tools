"""One-off checked migration of race and affinity text into semantic assets."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"
MATURE_TERMS = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "shared"
    / "terminology"
    / "races_and_affinities.json"
)
MATURE_COMPACT = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "battle"
    / "analysis_affinities.json"
)
PSP_BOOT_BINDING = (
    MATURE_ROOT
    / "psp"
    / "text"
    / "bindings"
    / "boot"
    / "embedded_text_tables.json"
)
GAME_TABLES = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "game"
    / "addressed"
    / "normcom_tables.json"
)
GAME_COMPACT = GAME_TABLES.with_name("combat_analysis_affinities.json")
SHOPSMP = ROOT / "saturn" / "text" / "corpus" / "game" / "eve" / "shopsmp.json"
COMPENDIUM_RACES = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "compendium"
    / "addressed"
    / "race_names.json"
)
RACE_ASSET = ROOT / "assets" / "text" / "races.json"
AFFINITY_ASSET = ROOT / "assets" / "text" / "affinities.json"
ANALYZE_FORMAT_ASSET = (
    ROOT / "assets" / "text" / "battle" / "analyze_formats.json"
)
RACE_BINDING = ROOT / "saturn" / "text" / "bindings" / "races.json"
AFFINITY_BINDING = (
    ROOT / "saturn" / "text" / "bindings" / "affinities.json"
)

RACE_PREVIEW_LABELS = (
    "DE", "MG", "HR", "AV", "TR", "EN", "GE", "AT", "HO", "EL", "MI",
    "HE", "FU", "LA", "KI", "DG", "DV", "FL", "YO", "FY", "SN", "BE",
    "UM", "JI", "NI", "FA", "BR", "FE", "VI", "RA", "WO", "RE", "WI",
    "JA", "HA", "VE", "TY", "DR", "GH", "SP", "FO", "ZO", "HU",
)

# These are the exact strings produced by the mature Saturn build's 26-pixel
# fusion-chart truncation. They are authored here so the replacement renderer
# does not own or synthesize visible abbreviations.
RACE_CHART_LABELS = (
    "Deity", "Mega", "Hera", "Avia", "Tree", "Enig", "Genm", "Avat", "Holy",
    "Elem", "Mita", "Hero", "Fury", "Lady", "Kishi", "Drag", "Divin", "Fligh",
    "Yoma", "Fairy", "Snak", "Beas", "UMA", "Jirae", "Night", "Falle", "Brut",
    "Femm", "Vile", "Rapt", "Wood", "Reap", "Wilde", "Jaki", "Haun", "Verm",
    "Tyra", "Drak", "Ghos", "Spiri", "Foul", "Zoma", "Time",
)
RACE_CHART_SHA256 = (
    "ce7ecdaa6e7e9187ebcedb6c350bd61c7ee80d0883ca8ff507d814fd0ada8589"
)

SUPPLEMENT_REFERENCES = (
    "造魔",
    "怨霊",
    "魔人",
    "{GLYPH:00b4}{GLYPH:00b4}{GLYPH:00b4}",
    "{GLYPH:00b4}{GLYPH:00b4}{GLYPH:00b4}",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def slug(text: str) -> str:
    value = text.lower().replace("{n}", "_")
    value = value.replace("atk", "attack").replace("phys", "physical")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def canonical_psp_tokens(text: str) -> str:
    return re.sub(r"\{PSP:([0-9a-f]{4})\}", r"{GLYPH:\1}", text)


def migrate_races(
    mature_races: list[dict],
    physical_races: list[dict],
    compendium_races: list[dict],
    shopsmp: list[dict],
    psp_tables: list[dict],
) -> None:
    assert len(mature_races) == len(physical_races) == 43
    assert [row["reference"] for row in physical_races] == [
        row["jp"] for row in mature_races
    ]
    assert all(
        row["tr"] and not row["reviewed"] and not row["excluded"]
        for row in mature_races
    )
    keys = tuple(slug(row["tr"]) for row in mature_races)
    assert len(keys) == len(set(keys)) == 43
    assert len(RACE_PREVIEW_LABELS) == len(RACE_CHART_LABELS) == 43
    assert hashlib.sha256("\0".join(RACE_CHART_LABELS).encode()).hexdigest() == (
        RACE_CHART_SHA256
    )

    standard = compendium_races[:42]
    human = compendium_races[42]
    supplement = compendium_races[43:]
    assert [row["reference"] for row in standard] == [
        row["jp"] for row in mature_races[:42]
    ]
    assert human["reference"] == mature_races[42]["jp"] == "人"
    assert tuple(row["reference"] for row in supplement) == SUPPLEMENT_REFERENCES

    psp_races = next(table for table in psp_tables if table["id"] == "races")
    assert psp_races["record_count"] == 43
    assert psp_races["status_ranges"][-1] == {
        "start": 42,
        "end": 42,
        "status": "blank_variant",
    }
    assert psp_races["variants"] == [
        {
            "index": 42,
            "shared_id": "ds.mirrored_words.normcom_tables.r000042",
            "saturn_jp": "人",
            "psp_jp": "",
            "source_sha256": "sha256:af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
        }
    ]

    shopsmp_by_message = {
        int(row["id"].split(".m", 1)[1].split(".", 1)[0]): row
        for row in shopsmp
    }
    assert set(range(161, 204)) | set(range(218, 263)) <= set(
        shopsmp_by_message
    )

    entries: dict[str, object] = {}
    for index, (key, row) in enumerate(zip(keys, mature_races, strict=True)):
        name: dict[str, object] = {
            "reference": row["jp"],
            "translation": row["tr"],
        }
        if index == 42:
            name["variants"] = {
                "psp": {
                    "reference": "",
                    "translation": "",
                    "note": "The PSP race table leaves this slot blank.",
                }
            }
        chart_label: dict[str, object] = {
            "reference": shopsmp_by_message[220 + index]["reference"]
            if index < 42
            else row["jp"],
            "translation": RACE_CHART_LABELS[index],
        }
        if index in {2, 12, 13, 25}:
            chart_label["variants"] = {
                "catalog_source": {
                    "reference": row["jp"],
                    "note": (
                        "The canonical race catalogue spells out the name; "
                        "the fusion chart owns the compact source form."
                    ),
                }
            }
        entry: dict[str, object] = {
            "name": name,
            "fusion_preview_label": {
                "reference": row["jp"],
                "translation": RACE_PREVIEW_LABELS[index],
            },
            "fusion_chart_label": chart_label,
        }
        if index == 42:
            entry["fusion_name"] = {
                "reference": row["jp"],
                "translation": "Time",
                "note": "The fusion screens deliberately call the final race Time.",
            }
        entries[key] = entry

    entries.update(
        {
            "time": {
                "name": {
                    "reference": "時間",
                    "translation": "Time",
                },
                "fusion_group_label": {
                    "reference": "時",
                    "translation": "Time",
                },
            },
            "vengeful_spirit": {
                "status": "unresolved",
                "note": "Bonus-disc race label with no mature English output.",
                "name": {"reference": "怨霊", "translation": ""},
            },
            "fiend": {
                "status": "unresolved",
                "note": "Bonus-disc race label with no mature English output.",
                "name": {"reference": "魔人", "translation": ""},
            },
            "compendium_race_placeholder_a": {
                "status": "reserve",
                "note": "Unresolved raw bonus-disc placeholder; identity retained.",
                "name": {
                    "reference": SUPPLEMENT_REFERENCES[3],
                    "translation": "",
                },
            },
            "compendium_race_placeholder_b": {
                "status": "reserve",
                "note": "Second independently addressable bonus-disc placeholder.",
                "name": {
                    "reference": SUPPLEMENT_REFERENCES[4],
                    "translation": "",
                },
            },
        }
    )

    records = {
        row["id"]: f"{key}.name"
        for row, key in zip(physical_races, keys, strict=True)
    }
    records.update(
        {
            row["id"]: f"{keys[index]}.name"
            for index, row in enumerate(standard)
        }
    )
    for index, key in enumerate(keys[:42]):
        records[shopsmp_by_message[161 + index]["id"]] = f"{key}.name"
        records[shopsmp_by_message[220 + index]["id"]] = (
            f"{key}.fusion_chart_label"
        )
    records[shopsmp_by_message[202]["id"]] = "zoma.name"
    records[shopsmp_by_message[203]["id"]] = "time.name"
    records[shopsmp_by_message[213]["id"]] = "element.name"
    records[shopsmp_by_message[217]["id"]] = "foul.name"
    records[shopsmp_by_message[218]["id"]] = "time.fusion_group_label"
    records[shopsmp_by_message[219]["id"]] = "zoma.name"
    records[shopsmp_by_message[261]["id"]] = "zoma.fusion_chart_label"
    records[shopsmp_by_message[262]["id"]] = "time.name"
    records[human["id"]] = f"{keys[42]}.name"
    supplement_assets = (
        "zoma.name",
        "vengeful_spirit.name",
        "fiend.name",
        "compendium_race_placeholder_a.name",
        "compendium_race_placeholder_b.name",
    )
    records.update(
        {
            row["id"]: asset
            for row, asset in zip(supplement, supplement_assets, strict=True)
        }
    )

    additional_uses: dict[str, list[dict[str, str]]] = {}
    for index, (row, key) in enumerate(zip(physical_races, keys, strict=True)):
        uses = [
            {"asset": f"{key}.fusion_preview_label"},
            {
                "asset": f"{key}.fusion_chart_label",
                **(
                    {"variant": "catalog_source"}
                    if index in {2, 12, 13, 25}
                    else {}
                ),
            },
        ]
        if index == 42:
            uses.append({"asset": f"{key}.fusion_name"})
        additional_uses[row["id"]] = uses

    unresolved = {
        row["id"]: (
            "The bonus-disc label has no mature English output; keep it visible "
            "until its consumer is rebuilt."
        )
        for row in supplement[1:3]
    }
    unresolved.update(
        {
            row["id"]: (
                "Raw bonus-disc placeholder is independently addressable and "
                "must not be inferred from its duplicate text."
            )
            for row in supplement[3:]
        }
    )

    write_json(
        RACE_ASSET,
        {"version": 1, "kind": "entity_catalog", "entries": entries},
    )
    write_json(
        RACE_BINDING,
        {
            "version": 1,
            "asset": "races.json",
            "records": records,
            "additional_uses": additional_uses,
            "field_surfaces": {
                "name": [
                    "map_3d.analyze_race",
                    "battle.analyze_race_heading",
                    "status.demon_race",
                    "fusion.table_race",
                    "compendium.race",
                ],
                "fusion_preview_label": ["fusion.preview_race"],
                "fusion_chart_label": ["fusion.chart_race"],
                "fusion_name": ["fusion.table_race"],
                "fusion_group_label": ["fusion.table_race"],
            },
            "glyph_equivalence": {"01a7": "間"},
            "unresolved": unresolved,
        },
    )


def migrate_affinities(
    mature_affinities: list[dict],
    mature_compact: list[dict],
    physical_affinities: list[dict],
    physical_compact: list[dict],
    psp_tables: list[dict],
    psp_candidates: list[dict],
) -> None:
    assert len(mature_affinities) == len(physical_affinities) == 96
    assert [row["reference"] for row in physical_affinities] == [
        row["jp"] for row in mature_affinities
    ]
    assert all(
        row["tr"] and not row["reviewed"] and not row["excluded"]
        for row in mature_affinities
    )
    assert len(physical_compact) == 66
    compact_by_reference = {row["jp"]: row["tr"] for row in mature_compact}
    assert len(mature_compact) == len(compact_by_reference) == 41
    assert set(row["reference"] for row in physical_compact) == set(
        compact_by_reference
    )

    keys: list[str] = []
    for index, row in enumerate(mature_affinities):
        if index == 0:
            key = "mirror"
        elif index == 1:
            key = "card"
        elif index >= 66:
            key = f"reserved_affinity_{index:03d}"
        else:
            key = slug(row["tr"])
        assert key and key not in keys
        keys.append(key)

    psp_affinities = next(
        table for table in psp_tables if table["id"] == "detailed_affinities"
    )
    assert psp_affinities["record_count"] == 96
    layout_variants = {row["index"]: row for row in psp_affinities["variants"]}
    assert set(layout_variants) == {12, 65}
    candidates = {row["index"]: row for row in psp_candidates}
    assert set(candidates) == set(range(66, 95))

    entries: dict[str, object] = {}
    for index, (key, row) in enumerate(
        zip(keys, mature_affinities, strict=True)
    ):
        description: dict[str, object] = {
            "reference": row["jp"],
            "translation": row["tr"],
        }
        if index in layout_variants:
            variant = layout_variants[index]
            assert variant["saturn_jp"] == row["jp"]
            description["variants"] = {
                "psp": {
                    "reference": variant["psp_jp"],
                    "note": "PSP source layout differs; translation is shared.",
                }
            }
        elif index in candidates:
            candidate = candidates[index]
            description["variants"] = {
                "psp": {
                    "reference": canonical_psp_tokens(candidate["jp"]),
                    "translation": "",
                    "reviewed": False,
                    "note": (
                        "PSP replaces this Saturn reserve with real text; "
                        "translation is pending."
                    ),
                }
            }
        entry: dict[str, object] = {"description": description}
        if index < 66:
            compact = physical_compact[index]
            entry["battle_summary"] = {
                "reference": compact["reference"],
                "translation": compact_by_reference[compact["reference"]],
            }
        else:
            entry["status"] = "reserve"
            entry["note"] = (
                "Reserved in Saturn; the PSP variant is retained on this "
                "physical affinity slot."
            )
        entries[key] = entry

    records = {
        row["id"]: f"{key}.description"
        for row, key in zip(physical_affinities, keys, strict=True)
    }
    records.update(
        {
            row["id"]: f"{keys[index]}.battle_summary"
            for index, row in enumerate(physical_compact)
        }
    )
    write_json(
        AFFINITY_ASSET,
        {"version": 1, "kind": "entity_catalog", "entries": entries},
    )
    write_json(
        AFFINITY_BINDING,
        {
            "version": 1,
            "asset": "affinities.json",
            "records": records,
            "field_surfaces": {
                "description": ["status.affinity"],
                "battle_summary": ["battle.analyze_affinity"],
            },
        },
    )


def main() -> None:
    mature_terms = read_json(MATURE_TERMS)
    mature_races = [row for row in mature_terms if row["table"] == "races"]
    mature_affinities = [
        row for row in mature_terms if row["table"] == "affinities"
    ]
    game_tables = read_json(GAME_TABLES)
    physical_races = [
        row for row in game_tables if ".races." in row["id"]
    ]
    physical_affinities = [
        row for row in game_tables if ".affinities." in row["id"]
    ]
    psp = read_json(PSP_BOOT_BINDING)

    migrate_races(
        mature_races,
        physical_races,
        read_json(COMPENDIUM_RACES),
        read_json(SHOPSMP),
        psp["tables"],
    )
    migrate_affinities(
        mature_affinities,
        read_json(MATURE_COMPACT),
        physical_affinities,
        read_json(GAME_COMPACT),
        psp["tables"],
        psp["psp_only_candidates"],
    )
    write_json(
        ANALYZE_FORMAT_ASSET,
        {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "race_heading": {
                    "placeholders": {"race": "demon_race"},
                    "text": {
                        "reference": "{race}:",
                        "translation": "{race}:",
                    },
                }
            },
        },
    )


if __name__ == "__main__":
    main()
