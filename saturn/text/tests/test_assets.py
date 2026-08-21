from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

TEXT_ROOT = Path(__file__).resolve().parents[1]
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))

from util.assets import (  # noqa: E402
    BINDING_ROOT,
    AssetCatalog,
    _safe_relative_path,
    load_asset,
    load_binding,
    load_bound_translations,
    validate_asset_document,
)


class AuthoredAssetInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.equipment = load_asset("equipment.json")
        cls.items = load_asset("items.json")
        cls.messages = load_asset("field/messages.json")
        cls.equipment_binding = load_binding(BINDING_ROOT / "equipment.json")
        cls.item_binding = load_binding(BINDING_ROOT / "items.json")
        cls.message_binding = load_binding(BINDING_ROOT / "field_messages.json")

    def test_entity_inventory_is_complete_and_semantic(self) -> None:
        self.assertEqual(len(self.equipment.entries), 208)
        self.assertEqual(len(self.items.entries), 73)
        self.assertEqual(len(self.messages.entries), 18)

        for catalog in (self.equipment, self.items, self.messages):
            for key in catalog.entries:
                self.assertNotIn("saturn", key)
                self.assertNotIn("psp", key)
                self.assertNotIn("_after_", key)
                self.assertIsNone(re.fullmatch(r"(?:(?:r|p|o)[0-9]+|[0-9]+)", key))

        self.assertEqual(
            self.equipment.entries["athame_knife"].fields["name"].translation,
            "Athame Knife",
        )
        self.assertEqual(
            self.equipment.entries["eight_foot_naginata"]
            .fields["description"]
            .reference,
            "攻撃力34 命中60 0～7回 ♀{n}後列から攻撃可能",
        )
        self.assertEqual(
            self.equipment.entries["sixes_choker"].fields["name"].translation,
            "6's Choker",
        )

    def test_all_item_slots_and_authored_forms_are_retained(self) -> None:
        console_fields = sum(
            "console_text" in entry.fields for entry in self.items.entries.values()
        )
        self.assertEqual(console_fields, 44)
        self.assertEqual(
            sum(entry.status == "reserve" for entry in self.items.entries.values()),
            2,
        )
        self.assertEqual(
            sum(
                entry.status == "unresolved"
                for entry in self.items.entries.values()
            ),
            1,
        )

        medicine = self.items.entries["medicine"]
        self.assertEqual(medicine.fields["name"].translation, "Medicine")
        self.assertEqual(
            medicine.fields["description"].translation,
            "Recovery item: One ally{n}Restores a small amount of HP",
        )
        self.assertEqual(medicine.fields["console_text"].translation, "Medicine")

        event = self.items.entries["event_08"]
        self.assertEqual(event.fields["description"].reference, "")
        self.assertEqual(event.fields["description"].translation, "")

        self.assertEqual(
            sum(
                entry.fields["description"].reference == ""
                for entry in self.items.entries.values()
            ),
            18,
        )
        self.assertEqual(self.item_binding.reference_normalization, "layout_blank")
        self.assertEqual(
            sum(
                asset_ref == "unused_reserve.name"
                for asset_ref in self.item_binding.records.values()
            ),
            5,
        )
        self.assertEqual(
            sum(
                asset_ref == "reserved_diagnostic.name"
                for asset_ref in self.item_binding.records.values()
            ),
            3,
        )

    def test_unresolved_a_shikai_join_is_explicit(self) -> None:
        entry = self.items.entries["unresolved_a_shikai"]
        self.assertEqual(entry.status, "unresolved")
        self.assertEqual(entry.fields["name"].reference, "リザーブ")
        self.assertEqual(entry.fields["console_text"].reference, "AーSikai")
        self.assertEqual(entry.fields["console_text"].translation, "A_Shikai")
        self.assertEqual(
            self.item_binding.records["game.btl_mes.p0043"],
            "unresolved_a_shikai.console_text",
        )
        self.assertIn("game.btl_mes.p0043", self.item_binding.unresolved)

    def test_physical_binding_inventory_is_exact(self) -> None:
        self.assertEqual(len(self.equipment_binding.records), 416)
        self.assertEqual(len(self.item_binding.records), 208)
        self.assertEqual(len(self.message_binding.records), 17)

        itemname_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "fixed" / "itemname.json")
            .read_text(encoding="utf-8")
        )
        itemname_ids = {row["id"] for row in itemname_rows}
        bound_itemname_ids = {
            physical_id
            for binding in (self.equipment_binding, self.item_binding)
            for physical_id in binding.records
            if physical_id.startswith("game.itemname.")
        }
        self.assertEqual(bound_itemname_ids, itemname_ids)
        padded_descriptions = [
            row
            for row in itemname_rows
            if row["reference"] == "                    {n}"
        ]
        self.assertEqual(len(padded_descriptions), 22)
        for row in padded_descriptions:
            asset_ref = self.item_binding.records[row["id"]]
            self.assertEqual(self.items.field(asset_ref).reference, "")

        battle_rows = json.loads(
            (TEXT_ROOT / "corpus" / "game" / "pointer" / "btl_mes.json")
            .read_text(encoding="utf-8")
        )
        bound_battle_ids = {
            physical_id
            for physical_id in self.item_binding.records
            if physical_id.startswith("game.btl_mes.")
        }
        self.assertEqual(
            bound_battle_ids,
            {row["id"] for row in battle_rows[1:49]},
        )
        self.assertEqual(
            self.item_binding.records[
                "game.combat_result_labels.o053b8c"
            ],
            "bead.name",
        )
        self.assertEqual(
            self.item_binding.records[
                "game.combat_result_labels.o053ce0"
            ],
            "life_stone.name",
        )
        self.assertEqual(
            self.item_binding.field_surfaces,
            {"console_text": ("battle.console",)},
        )
        self.assertEqual(
            self.item_binding.record_surfaces,
            {
                "game.combat_result_labels.o053b8c": (
                    "battle.result_name",
                ),
                "game.combat_result_labels.o053ce0": (
                    "battle.result_name",
                ),
            },
        )


class FieldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.messages = load_asset("field/messages.json")
        cls.binding = load_binding(BINDING_ROOT / "field_messages.json")

    def test_dynamic_messages_are_complete_typed_templates(self) -> None:
        obtained = self.messages.entries["currency_obtained"]
        self.assertEqual(
            dict(obtained.placeholders),
            {"currency_amount": "formatted_currency_amount"},
        )
        self.assertEqual(
            obtained.fields["text"].reference,
            "{yen_symbol}{currency_amount}を手に入れた",
        )
        self.assertEqual(
            obtained.fields["text"].translation,
            "Obtained {yen_symbol}{currency_amount}.",
        )
        self.assertEqual(
            obtained.fields["text"].resolve("magnetite")[:2],
            (
                "{mag_symbol}{currency_amount}を手に入れた",
                "Obtained {mag_symbol}{currency_amount}.",
            ),
        )

        self.assertEqual(
            self.messages.entries["item_found"].fields["text"].translation,
            "Found {item}.",
        )
        self.assertEqual(
            self.messages.entries["item_obtained"].fields["text"].translation,
            "Obtained {item}.",
        )
        self.assertEqual(
            self.messages.entries["item_full"].fields["text"].translation,
            "Cannot hold more {item}.",
        )

    def test_identical_suffixes_keep_separately_proven_domains(self) -> None:
        self.assertEqual(
            self.binding.records["game.maze_messages.o0251d0"],
            "value_obtained.text",
        )
        self.assertEqual(
            self.binding.composition["game.maze_messages.o0251d0"].supplies,
            ("value",),
        )
        self.assertIn(
            "game.maze_messages.o0251d0", self.binding.unresolved
        )
        self.assertEqual(
            self.binding.records["game.maze_messages.o0251dc"],
            "currency_obtained.text",
        )
        self.assertEqual(
            self.binding.composition["game.maze_messages.o0251dc"].supplies,
            ("currency_amount",),
        )
        item_use = self.binding.additional_uses[
            "game.maze_messages.o0251dc"
        ]
        self.assertEqual(len(item_use), 2)
        self.assertEqual(item_use[0].asset_ref, "item_obtained.text")
        self.assertIsNone(item_use[0].variant)
        self.assertEqual(item_use[0].composition.supplies, ("item",))
        self.assertEqual(item_use[1].asset_ref, "currency_obtained.text")
        self.assertEqual(item_use[1].variant, "magnetite")
        self.assertEqual(
            item_use[1].composition.supplies, ("currency_amount",)
        )
        self.assertEqual(dict(self.binding.field_surfaces), {})
        self.assertEqual(
            set(self.binding.record_surfaces),
            set(self.binding.records),
        )
        self.assertEqual(
            self.binding.record_surfaces[
                "game.maze_speech_choices_static.o0250d0"
            ],
            ("map_3d.field_choice",),
        )
        self.assertEqual(
            self.binding.record_surfaces[
                "game.maze_speech_choices_static.o0250d6"
            ],
            ("map_3d.field_choice",),
        )
        self.assertTrue(
            all(
                surfaces == ("map_3d.field_message",)
                for physical_id, surfaces in self.binding.record_surfaces.items()
                if physical_id.startswith("game.maze_messages.")
            )
        )


class AssetSchemaTests(unittest.TestCase):
    def test_named_variant_can_change_only_the_differing_text(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "obtained": {
                    "placeholders": {"item": "item_name"},
                    "text": {
                        "reference": "{item}を手に入れた",
                        "translation": "Obtained {item}.",
                        "reviewed": False,
                        "variants": {
                            "short": {"translation": "Got {item}."}
                        },
                    },
                }
            },
        }
        catalog: AssetCatalog = validate_asset_document(document)
        self.assertEqual(
            catalog.field("obtained.text").resolve("short")[:2],
            ("{item}を手に入れた", "Got {item}."),
        )

    def test_reviewed_defaults_false_and_rejects_non_booleans(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "line": {
                    "text": {
                        "reference": "行",
                        "translation": "Line",
                    }
                }
            },
        }
        catalog = validate_asset_document(document)
        self.assertFalse(catalog.field("line.text").reviewed)

        document["entries"]["line"]["text"]["reviewed"] = True
        catalog = validate_asset_document(document)
        self.assertTrue(catalog.field("line.text").reviewed)

        document["entries"]["line"]["text"]["reviewed"] = "false"
        with self.assertRaisesRegex(ValueError, "reviewed must be boolean"):
            validate_asset_document(document)

    def test_placeholder_drift_is_rejected(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "bad": {
                    "placeholders": {"item": "item_name"},
                    "text": {
                        "reference": "{item}を見つけた",
                        "translation": "Found it.",
                        "reviewed": False,
                    },
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

    def test_repeated_placeholder_drift_is_rejected(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "bad": {
                    "placeholders": {"item": "item_name"},
                    "text": {
                        "reference": "{item}と{item}",
                        "translation": "{item}",
                        "reviewed": False,
                    },
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

    def test_structural_beat_is_not_a_placeholder(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "timed": {
                    "text": {
                        "reference": "待つ{BEAT}",
                        "translation": "Wait{BEAT}",
                        "reviewed": False,
                    }
                }
            },
        }
        validate_asset_document(document)

        document["entries"]["timed"]["text"]["translation"] = "Wait"
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

        document["entries"]["timed"]["text"]["translation"] = (
            "Wait{BEAT}{BEAT}"
        )
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

    def test_unknown_operations_retain_multiplicity(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "timed": {
                    "text": {
                        "reference": "待つ{OP:801e}",
                        "translation": "Wait{OP:801e}",
                    }
                }
            },
        }
        validate_asset_document(document)
        document["entries"]["timed"]["text"]["translation"] = "Wait"
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

    def test_source_presentation_glyph_may_be_omitted(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "marked": {
                    "text": {
                        "reference": "印{maru_symbol}",
                        "translation": "Mark",
                    }
                }
            },
        }
        validate_asset_document(document)

    def test_authored_currency_symbol_identity_is_required(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "money": {
                    "placeholders": {
                        "currency_amount": "formatted_currency_amount"
                    },
                    "text": {
                        "reference": "{yen_symbol}{currency_amount}",
                        "translation": "{yen_symbol}{currency_amount}",
                    },
                }
            },
        }
        validate_asset_document(document)

        document["entries"]["money"]["text"]["translation"] = (
            "{currency_amount}"
        )
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

        document["entries"]["money"]["text"]["translation"] = (
            "{mag_symbol}{currency_amount}"
        )
        with self.assertRaisesRegex(ValueError, "functional tokens differ"):
            validate_asset_document(document)

    def test_uppercase_named_placeholder_can_be_declared(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "damage": {
                    "placeholders": {"NUM": "number"},
                    "text": {
                        "reference": "Damage {NUM}",
                        "translation": "Damage {NUM}",
                    },
                }
            },
        }
        validate_asset_document(document)

    def test_unknown_placeholder_type_is_rejected(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "damage": {
                    "placeholders": {"NUM": "numbor"},
                    "text": {
                        "reference": "Damage {NUM}",
                        "translation": "Damage {NUM}",
                    },
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "placeholder type must be"):
            validate_asset_document(document)

    def test_physical_prefix_can_ground_a_complete_template(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "control": {
                    "placeholders": {"rank": "control_rank"},
                    "text": {
                        "reference": "CTRL {rank}",
                        "translation": "CTRL {rank}",
                    },
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "status.json",
            "records": {"physical.ctrl": "control.text"},
            "composition": {
                "physical.ctrl": {
                    "source_role": "prefix",
                    "supplies": ["rank"],
                }
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "status.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.ctrl": "CTRL"},
            )
            self.assertEqual(
                binding.composition["physical.ctrl"].source_role,
                "prefix",
            )

            binding_document["composition"]["physical.ctrl"][
                "source_role"
            ] = "middle"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "source role"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.ctrl": "CTRL"},
                )

            binding_document["composition"]["physical.ctrl"][
                "source_role"
            ] = "prefix"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "not a prefix"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.ctrl": "TR"},
                )

    def test_physical_scaffold_can_ground_an_interior_literal(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "date": {
                    "placeholders": {"day": "number", "month": "number"},
                    "text": {
                        "reference": "{day}／{month}",
                        "translation": "{day}/{month}",
                    },
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "date.json",
            "records": {"physical.slash": "date.text"},
            "composition": {
                "physical.slash": {
                    "source_role": "scaffold",
                    "supplies": ["day", "month"],
                }
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "date.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.slash": "／"},
            )
            self.assertEqual(
                binding.composition["physical.slash"].source_role,
                "scaffold",
            )

            with self.assertRaisesRegex(ValueError, "not a scaffold"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.slash": "："},
                )

    def test_binding_substitutions_materialize_bound_translations_token_safely(
        self,
    ) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "capacity": {
                    "text": {"reference": "129", "translation": "256"}
                },
                "message": {
                    "placeholders": {"capacity_blocks": "number"},
                    "text": {
                        "reference": (
                            "Need {capacity_blocks}; literal {{capacity_blocks}}"
                        ),
                        "translation": (
                            "Need {capacity_blocks}; literal {{capacity_blocks}}"
                        ),
                    },
                },
            },
        }
        binding_document = {
            "version": 1,
            "asset": "capacity.json",
            "records": {"physical.message": "message.text"},
            "substitutions": {
                "physical.message": {
                    "capacity_blocks": "capacity.text",
                }
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "capacity.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            physical = {
                "physical.message": "Need 129; literal {{capacity_blocks}}"
            }
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records=physical,
            )
            self.assertEqual(
                dict(binding.substitutions["physical.message"]),
                {"capacity_blocks": "capacity.text"},
            )
            translations = load_bound_translations(
                ("physical.",),
                required_ids={"physical.message"},
                binding_paths=(binding_path,),
                physical_records=physical,
                asset_root=root,
            )
            self.assertEqual(
                translations["physical.message"],
                "Need 256; literal {{capacity_blocks}}",
            )

    def test_nl_is_layout_only(self) -> None:
        document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "line": {
                    "text": {
                        "reference": "一{NL}二",
                        "translation": "One two",
                    }
                }
            },
        }
        validate_asset_document(document)

    def test_record_surfaces_require_bound_records_and_known_surfaces(self) -> None:
        document = {
            "version": 1,
            "asset": "items.json",
            "records": {"physical.bead": "bead.name"},
            "record_surfaces": {
                "physical.missing": ["battle.result_name"]
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "binding.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unbound record"):
                load_binding(path, physical_records={})

            document["record_surfaces"] = {
                "physical.bead": ["battle.missing"]
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown text surface"):
                load_binding(path, physical_records={})

    def test_additional_use_fields_can_declare_surfaces(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "entity_catalog",
            "entries": {
                "thing": {
                    "name": {"reference": "同", "translation": "Same"},
                    "description": {
                        "reference": "同",
                        "translation": "Same",
                    },
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "thing.json",
            "records": {"physical.same": "thing.name"},
            "additional_uses": {
                "physical.same": [{"asset": "thing.description"}]
            },
            "field_surfaces": {
                "description": ["battle.result_name"]
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "thing.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.same": "同"},
            )
        self.assertEqual(
            binding.field_surfaces,
            {"description": ("battle.result_name",)},
        )

    def test_glyph_equivalence_is_explicit_and_must_be_used(self) -> None:
        reference = load_asset("demons.json").field(
            "tyr.compendium_detail"
        ).reference
        physical_reference = reference.replace(
            "Tuesday", "Tu{GLYPH:0026}sd{GLYPH:0029}y"
        )
        self.assertNotEqual(physical_reference, reference)
        document = {
            "version": 1,
            "asset": "demons.json",
            "records": {"physical.tyr": "tyr.compendium_detail"},
            "glyph_equivalence": {"0026": "e", "0029": "a"},
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "binding.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            binding = load_binding(
                path,
                physical_records={"physical.tyr": physical_reference},
            )
            self.assertEqual(
                dict(binding.glyph_equivalence), {"0026": "e", "0029": "a"}
            )

            document["glyph_equivalence"]["002d"] = "e"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unused glyph equivalence"):
                load_binding(
                    path,
                    physical_records={"physical.tyr": physical_reference},
                )

            document["glyph_equivalence"] = {"002A": "a"}
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "lowercase two- or four-digit hex"):
                load_binding(
                    path,
                    physical_records={"physical.tyr": physical_reference},
                )

    def test_glyph_equivalence_does_not_rewrite_literal_token_text(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "glyph": {
                    "text": {"reference": "e", "translation": "e"}
                },
                "literal": {
                    "text": {
                        "reference": "{{GLYPH:0026}}",
                        "translation": "{{GLYPH:0026}}",
                    }
                },
            },
        }
        binding_document = {
            "version": 1,
            "asset": "literal.json",
            "records": {
                "physical.glyph": "glyph.text",
                "physical.literal": "literal.text",
            },
            "glyph_equivalence": {"0026": "e"},
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "literal.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            load_binding(
                binding_path,
                asset_root=root,
                physical_records={
                    "physical.glyph": "{GLYPH:0026}",
                    "physical.literal": "{{GLYPH:0026}}",
                },
            )

    def test_visible_source_glyph_can_map_to_an_authored_symbol_token(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "fee": {
                    "text": {
                        "reference": "報酬{yen_symbol}50000",
                        "translation": "Fee: {yen_symbol}50,000",
                    }
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "fee.json",
            "records": {"physical.fee": "fee.text"},
            "glyph_tokens": {"00c0": "yen_symbol"},
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "fee.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.fee": "報酬{GLYPH:00c0}50000"},
            )
            self.assertEqual(dict(binding.glyph_tokens), {"00c0": "yen_symbol"})

            binding_document["glyph_tokens"] = {"00c0": "currency_symbol"}
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "authored symbol"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.fee": "報酬{GLYPH:00c0}50000"},
                )

    def test_defined_source_glyph_can_retain_an_authored_symbol_identity(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "fee": {
                    "text": {
                        "reference": "報酬{yen_symbol}50000",
                        "translation": "Fee: {yen_symbol}50,000",
                    }
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "fee.json",
            "records": {"physical.fee": "fee.text"},
            "source_glyph_tokens": {
                "physical.fee": {"▯": "yen_symbol"},
            },
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "fee.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            binding = load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.fee": "報酬▯50000"},
            )
            self.assertEqual(
                {
                    physical_id: dict(tokens)
                    for physical_id, tokens in binding.source_glyph_tokens.items()
                },
                {"physical.fee": {"▯": "yen_symbol"}},
            )

            binding_document["source_glyph_tokens"]["physical.fee"] = {
                "▯": "currency_symbol"
            }
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "authored symbol"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.fee": "報酬▯50000"},
                )

    def test_one_byte_glyph_equivalence_is_lossless_and_explicit(self) -> None:
        asset_document = {
            "version": 1,
            "kind": "surface_catalog",
            "entries": {
                "fatal": {
                    "text": {
                        "reference": "必殺",
                        "translation": "Fatal",
                    }
                }
            },
        }
        binding_document = {
            "version": 1,
            "asset": "console.json",
            "records": {"physical.fatal": "fatal.text"},
            "glyph_equivalence": {"4b": "殺"},
        }
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            (root / "console.json").write_text(
                json.dumps(asset_document), encoding="utf-8"
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            load_binding(
                binding_path,
                asset_root=root,
                physical_records={"physical.fatal": "必{GLYPH:4b}"},
            )

            binding_document["glyph_equivalence"] = {"004b": "殺"}
            binding_path.write_text(
                json.dumps(binding_document), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "unused glyph equivalence"):
                load_binding(
                    binding_path,
                    asset_root=root,
                    physical_records={"physical.fatal": "必殺"},
                )

    def test_boolean_versions_are_rejected(self) -> None:
        document = {
            "version": True,
            "kind": "surface_catalog",
            "entries": {
                "line": {
                    "text": {
                        "reference": "行",
                        "translation": "Line",
                        "reviewed": False,
                    }
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "version must be 1"):
            validate_asset_document(document)

        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "binding.json"
            path.write_text(
                json.dumps(
                    {
                        "version": True,
                        "asset": "items.json",
                        "records": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "version must be 1"):
                load_binding(path, physical_records={})

    def test_asset_paths_are_canonical_posix_relatives(self) -> None:
        for value in (
            "",
            ".",
            "./items.json",
            "field/../items.json",
            "field\\messages.json",
            "field//messages.json",
            "C:/items.json",
            "field/message-pack.json",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "relative JSON path"):
                    _safe_relative_path(value, "asset")


if __name__ == "__main__":
    unittest.main()
