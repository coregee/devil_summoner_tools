"""One-off checked migration of mature demon text into semantic assets."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATURE_ROOT = ROOT.parent / "smtds_en"

MATURE_NAMES = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "shared" / "names" / "demons.json"
)
MATURE_PROFILE_ROOT = (
    MATURE_ROOT / "shared" / "text" / "corpus" / "demon_compendium" / "profiles"
)
MATURE_SUPPLEMENT = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "demon_compendium"
    / "psp"
    / "supplement.json"
)
MATURE_PSP_NAMES = (
    MATURE_ROOT
    / "shared"
    / "text"
    / "corpus"
    / "shared"
    / "names"
    / "psp"
    / "demon_overrides.json"
)

GAME_NAMES = ROOT / "saturn" / "text" / "corpus" / "game" / "fixed" / "dvlname.json"
ZENSHO_NAMES = (
    ROOT
    / "saturn"
    / "text"
    / "corpus"
    / "compendium"
    / "fixed"
    / "demon_names.json"
)
PROFILE_CORPUS = (
    ROOT / "saturn" / "text" / "corpus" / "compendium" / "profiles.json"
)
ASSET_PATH = ROOT / "assets" / "text" / "demons.json"
NAME_BINDING_PATH = ROOT / "saturn" / "text" / "bindings" / "demons.json"
PROFILE_BINDING_PATH = (
    ROOT / "saturn" / "text" / "bindings" / "demon_compendium.json"
)

FIELD_OFFSETS = {
    "origin": 0x78000,
    "summary": 0x7801E,
    "detail": 0x7808E,
}
FIELD_ASSET_NAMES = {
    "origin": "compendium_origin",
    "summary": "compendium_summary",
    "detail": "compendium_detail",
}
GLYPH_EQUIVALENCE = {
    "0026": "e",
    "0029": "a",
    "002d": "e",
    "002f": "a",
    "026e": "木",
    "0656": "木",
}
ZENSHO_NAME_VARIANT_ROWS = {1, 35, 64, 188, 262}
PSP_NAME_VARIANT_ROWS = {32, 61, 141, 286}

CURATED_KEYS = {
    61: "guan_yu",
    286: "guan_yu_rampaging",
    211: "ashinaga",
    268: "ashinaga_unprofiled",
    212: "tenaga",
    269: "tenaga_unprofiled",
    240: "enku",
    278: "enku_unprofiled",
    243: "preta",
    263: "preta_unprofiled",
    254: "slime",
    264: "slime_unprofiled",
    255: "shei_form_1",
    256: "shei_form_2",
    257: "shei_form_3",
    258: "shei_form_4",
    259: "shei_form_5",
    273: "sid_davis",
    289: "sid_unprofiled",
    293: "sid_davis_battle",
    283: "orgone_ghost_empowered",
    284: "orgone_ghost_weakened",
    294: "inaruna_princess",
    295: "inaruna_vengeful_spirit",
    296: "inaruna_unprofiled",
    **{row: "boss_reserve" for row in range(304, 319)},
}
UNPROFILED_DUPLICATES = {
    263: "Preta",
    264: "Slime",
    268: "Ashinaga",
    269: "Tenaga",
    278: "Enku",
    289: "Sid",
    296: "Inaruna",
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
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_value.lower())).strip(
        "_"
    )


def normalize_compendium_reference(value: str) -> str:
    for code, character in GLYPH_EQUIVALENCE.items():
        value = value.replace(f"{{GLYPH:{code}}}", character)
    return value


def main() -> None:
    mature_names = read_json(MATURE_NAMES)
    game_names = read_json(GAME_NAMES)
    zensho_names = read_json(ZENSHO_NAMES)
    profile_rows = read_json(PROFILE_CORPUS)
    psp_name_document = read_json(MATURE_PSP_NAMES)
    psp_name_rows = {
        row["record_index"]: row for row in psp_name_document["records"]
    }

    assert len(mature_names) == len(game_names) == len(zensho_names) == 319
    assert all(
        mature["jp"] == physical["reference"]
        for mature, physical in zip(mature_names, game_names, strict=True)
    )
    actual_zensho_variants = {
        index
        for index, (mature, physical) in enumerate(
            zip(mature_names, zensho_names, strict=True)
        )
        if mature["jp"] != physical["reference"]
    }
    assert actual_zensho_variants == ZENSHO_NAME_VARIANT_ROWS

    mature_profiles = []
    for path in sorted(MATURE_PROFILE_ROOT.glob("*.json")):
        mature_profiles.extend(read_json(path)["profiles"])
    mature_profiles.sort(key=lambda row: row["profile_ordinal"])
    assert len(mature_profiles) == 292
    assert [row["profile_ordinal"] for row in mature_profiles] == list(range(1, 293))

    physical_profiles = {row["id"]: row["reference"] for row in profile_rows}
    assert len(physical_profiles) == 876

    if str(MATURE_ROOT) not in sys.path:
        sys.path.insert(0, str(MATURE_ROOT))
    from tools import psp_compendium_bindings as psp_compendium  # noqa: PLC0415

    _config, _saturn_map, psp_map, _overrides = (
        psp_compendium.load_transcode_config()
    )
    psp_source = psp_compendium.read_psp_source()
    assert len(psp_source.profiles) == 296

    psp_profile_references: dict[tuple[int, str], str] = {}
    psp_revision_counts: Counter[str] = Counter()
    for position, profile in enumerate(mature_profiles):
        for field_index, field_name in enumerate(FIELD_OFFSETS):
            reference = psp_compendium._decode_psp(
                psp_source.profiles[position].fields[field_index], psp_map
            )
            if reference != profile["fields"][field_name]["jp"]:
                psp_profile_references[(profile["dvl_id"], field_name)] = reference
                psp_revision_counts[field_name] += 1
    assert psp_revision_counts == Counter(
        {"origin": 7, "summary": 42, "detail": 107}
    )

    row_keys: dict[int, str] = {}
    for index, row in enumerate(mature_names):
        row_keys[index] = CURATED_KEYS.get(index, slug(row["tr"]))
        assert re.fullmatch(r"[a-z][a-z0-9_]*", row_keys[index])
    collisions: dict[str, list[int]] = {}
    for row_index, key in row_keys.items():
        collisions.setdefault(key, []).append(row_index)
    assert {
        key: rows for key, rows in collisions.items() if len(rows) > 1
    } == {"boss_reserve": list(range(304, 319))}

    entries: dict[str, dict[str, object]] = {}
    for index, row in enumerate(mature_names):
        key = row_keys[index]
        if key in entries:
            assert key == "boss_reserve"
            continue
        entry: dict[str, object] = {}
        if index in UNPROFILED_DUPLICATES:
            visible_name = UNPROFILED_DUPLICATES[index]
            entry["status"] = "unresolved"
            entry["note"] = (
                f"This name-only Saturn entry duplicates {visible_name}, but no "
                "profile image or call-site evidence proves which form it represents."
            )
        elif key == "boss_reserve":
            entry["status"] = "reserve"
            entry["note"] = (
                "Fifteen unused Saturn boss slots intentionally share this editable "
                "reserve label; every physical occurrence remains explicit in the "
                "platform binding."
            )

        name_field: dict[str, object] = {
            "reference": row["jp"],
            "translation": row["tr"],
        }
        variants: dict[str, object] = {}
        if index in ZENSHO_NAME_VARIANT_ROWS:
            variants["akuma_zensho"] = {
                "reference": zensho_names[index]["reference"]
            }
        if index in PSP_NAME_VARIANT_ROWS:
            psp_name = psp_name_rows[index]["name"]
            assert psp_name["tr"] == row["tr"]
            assert psp_name["jp"] != row["jp"]
            variants["psp"] = {"reference": psp_name["jp"]}
        if variants:
            name_field["variants"] = variants
        entry["name"] = name_field
        entries[key] = entry

    profile_binding_records: dict[str, str] = {}
    for profile in mature_profiles:
        dvl_id = profile["dvl_id"]
        row_index = profile["table_row"]
        assert row_index == dvl_id - 1
        key = row_keys[row_index]
        entry = entries[key]
        for field_name, offset in FIELD_OFFSETS.items():
            mature_field = profile["fields"][field_name]
            asset_field_name = FIELD_ASSET_NAMES[field_name]
            assert asset_field_name not in entry
            field: dict[str, object] = {
                "reference": mature_field["jp"],
                "translation": mature_field["tr"],
            }
            psp_reference = psp_profile_references.get((dvl_id, field_name))
            if psp_reference is not None:
                field["variants"] = {"psp": {"reference": psp_reference}}
            entry[asset_field_name] = field

            physical_id = (
                f"compendium.profiles.dvl_{dvl_id:03x}."
                f"o{offset:06x}.{field_name}"
            )
            assert normalize_compendium_reference(
                physical_profiles[physical_id]
            ) == mature_field["jp"]
            profile_binding_records[physical_id] = f"{key}.{asset_field_name}"

    supplement = read_json(MATURE_SUPPLEMENT)
    supplemental_profiles = {row["key"]: row for row in supplement["profiles"]}
    assert set(supplemental_profiles) == {"david", "enoch", "leviathan", "skoll"}

    replacement_keys = {
        305: "red_cape_unprofiled_a",
        306: "red_cape_unprofiled_b",
        307: "yomi_kugutsu",
        308: "david",
        309: "enoch",
        310: "leviathan",
        311: "skoll",
    }
    for row_index, key in replacement_keys.items():
        source = psp_name_rows[row_index]
        name = source["name"]
        entry = {}
        if row_index in {305, 306}:
            entry["status"] = "unresolved"
            entry["note"] = (
                "This dormant PSP name has another identical name-only occurrence; "
                "their semantic relationship is not yet proven."
            )
        elif row_index == 307:
            entry["note"] = "Dormant PSP-only name record with no Compendium profile."
        entry["name"] = {
            "reference": name["jp"],
            "translation": name["tr"],
        }
        if key in supplemental_profiles:
            profile = supplemental_profiles[key]
            assert profile["name"] == name["tr"]
            for field_name in FIELD_OFFSETS:
                source_field = profile["fields"][field_name]
                entry[FIELD_ASSET_NAMES[field_name]] = {
                    "reference": source_field["jp"],
                    "translation": source_field["tr"],
                }
        assert key not in entries
        entries[key] = entry

    assert len(entries) == 312
    assert sum(
        key not in {"status", "note", "placeholders"}
        for entry in entries.values()
        for key in entry
    ) == 1200
    assert sum(
        len(field.get("variants", {}))
        for entry in entries.values()
        for field_name, field in entry.items()
        if field_name not in {"status", "note", "placeholders"}
    ) == 165

    name_binding_records: dict[str, str] = {}
    name_binding_variants: dict[str, str] = {}
    for index, (game_row, zensho_row) in enumerate(
        zip(game_names, zensho_names, strict=True)
    ):
        asset_ref = f"{row_keys[index]}.name"
        name_binding_records[game_row["id"]] = asset_ref
        name_binding_records[zensho_row["id"]] = asset_ref
        if index in ZENSHO_NAME_VARIANT_ROWS:
            name_binding_variants[zensho_row["id"]] = "akuma_zensho"

    assert len(name_binding_records) == 638
    assert len(name_binding_variants) == 5
    assert len(profile_binding_records) == 876

    write_json(
        ASSET_PATH,
        {"version": 1, "kind": "entity_catalog", "entries": entries},
    )
    write_json(
        NAME_BINDING_PATH,
        {
            "version": 1,
            "asset": "demons.json",
            "records": name_binding_records,
            "variants": name_binding_variants,
            "field_surfaces": {
                "name": [
                    "map_3d.analyze_demon_name",
                    "battle.party_demon_name",
                    "battle.analyze_demon_name",
                    "comp.party_demon_name",
                    "comp.stock_demon_name",
                    "status.demon_name",
                    "fusion.table_demon_name",
                    "fusion.status_name",
                    "bar.status_name",
                    "healer.member_name",
                    "healer.status_name",
                    "compendium.profile_name",
                ]
            },
        },
    )
    write_json(
        PROFILE_BINDING_PATH,
        {
            "version": 1,
            "asset": "demons.json",
            "records": profile_binding_records,
            "glyph_equivalence": GLYPH_EQUIVALENCE,
            "field_surfaces": {
                "compendium_origin": ["compendium.origin"],
                "compendium_summary": ["compendium.summary"],
                "compendium_detail": ["compendium.detail"],
            },
        },
    )


if __name__ == "__main__":
    main()
