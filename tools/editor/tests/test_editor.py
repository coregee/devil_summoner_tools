from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saturn.font.util.codec import repack_font
from saturn.font.util.definitions import load_definition

from tools.editor.application import EditorApplication
from tools.editor.catalog import CorpusCatalog
from tools.editor.fonts import (
    FontService,
    replace_glyph_mapping,
    replace_source_mapping,
)
from tools.editor.languages import LanguageService
from tools.editor.models import EntryKey


class EntryKeyTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        value = "events/police_station.json#police_station_takeover_000.text"
        self.assertEqual(EntryKey.parse(value).id, value)

    def test_rejects_unsafe_asset_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid editor entry id"):
            EntryKey.parse("../outside.json#entry.text")


class StaticShellTests(unittest.TestCase):
    def test_hidden_workspaces_override_layout_display(self) -> None:
        styles = Path("tools/editor/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("[hidden] { display: none !important; }", styles)


class ActualCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = EditorApplication()
        cls.entry_id = (
            "events/police_station.json#police_station_takeover_000.text"
        )

    def test_event_dialogue_has_exact_font_preview(self) -> None:
        entry = self.application.catalog.entry(self.entry_id)
        result = self.application.evaluate(self.entry_id, entry["translation"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["surfaces"][0]["name"], "event.dialogue")
        self.assertTrue(result["surfaces"][0]["exact"])
        self.assertTrue(result["preview"]["data_url"].startswith("data:image/png"))

    def test_each_bound_surface_has_its_own_preview(self) -> None:
        entry = self.application.catalog.entry("battle/commands.json#go.name")
        result = self.application.evaluate(
            entry["id"], entry["translation"], entry["font8_alphabet"]
        )
        self.assertEqual(
            [surface["name"] for surface in result["surfaces"]],
            ["battle.command", "status.auto_command"],
        )
        for surface in result["surfaces"]:
            self.assertEqual(surface["preview"]["surface"], surface["name"])
            self.assertTrue(surface["preview"]["data_url"].startswith("data:image/png"))

    def test_negotiation_grid_choice_uses_a_non_blocking_width_advisory(self) -> None:
        entry_id = "negotiation/feral.json#dialogue_0207.text"
        entry = self.application.catalog.entry(entry_id)
        self.assertEqual(
            {consumer["surface"] for consumer in entry["consumers"]},
            {"battle.negotiation_choice"},
        )

        boundary = self.application.evaluate(
            entry_id, "Because it will be convenie"
        )
        self.assertEqual(boundary["surfaces"][0]["lines"][0]["width"], 142)
        self.assertNotIn(
            "advisory_line_width",
            {diagnostic["code"] for diagnostic in boundary["diagnostics"]},
        )

        overflow = self.application.evaluate(
            entry_id, "Because it will be convenient"
        )
        self.assertTrue(overflow["valid"])
        self.assertEqual(overflow["surfaces"][0]["lines"][0]["width"], 153)
        diagnostic = next(
            row
            for row in overflow["diagnostics"]
            if row["code"] == "advisory_line_width"
        )
        self.assertEqual(
            (diagnostic["severity"], diagnostic["actual"], diagnostic["limit"]),
            ("warning", 153, 142),
        )

    def test_overlong_unbroken_dialogue_is_rejected(self) -> None:
        result = self.application.evaluate(self.entry_id, "W" * 90)
        self.assertFalse(result["valid"])
        self.assertIn(
            "line_width", {row["code"] for row in result["diagnostics"]}
        )

    def test_functional_token_drift_is_rejected(self) -> None:
        rows = self.application.catalog.list_entries("{item}", 200)["entries"]
        token_row = next(
            (row for row in rows if "{item}" in row["reference"]), None
        )
        if token_row is None:
            self.skipTest("corpus contains no indexed {item} reference")
        result = self.application.evaluate(token_row["id"], "Token removed")
        self.assertFalse(result["valid"])
        self.assertEqual(result["diagnostics"][0]["code"], "asset_contract")

    def test_font_inventory_exposes_exact_editable_glyphs(self) -> None:
        detail = self.application.fonts.detail("game/font16")
        self.assertEqual(detail["name"], "FONT16 - General Text (16px Source)")
        self.assertEqual(detail["file"], "FONT16.FON")
        self.assertTrue(detail["can_edit"])
        self.assertTrue(detail["can_rebuild"])
        self.assertEqual(detail["slot_page"]["physical"], 1872)
        self.assertEqual(detail["slot_counts"]["replaceable"], 88)
        self.assertGreater(detail["slot_counts"]["defined"], 1500)
        self.assertGreater(detail["slot_counts"]["suggested"], 300)
        self.assertTrue(detail["slots"][0]["image"].startswith("data:image/png"))
        replaced = next(slot for slot in detail["slots"] if slot["code"] == 173)
        self.assertTrue(replaced["original_image"].startswith("data:image/png"))
        self.assertTrue(replaced["modified_image"].startswith("data:image/png"))
        self.assertNotEqual(
            replaced["original_image"], replaced["modified_image"]
        )
        self.assertEqual(replaced["replacement"], "-")
        self.assertTrue(detail["atlases"]["original"].startswith("data:image/png"))
        self.assertTrue(detail["atlases"]["modified"].startswith("data:image/png"))

    def test_font_inventory_hides_icon_resource(self) -> None:
        rows = self.application.fonts.inventory()["fonts"]
        saturn_rows = [row for row in rows if row["platform"] == "saturn"]
        psp_rows = [row for row in rows if row["platform"] == "psp"]
        names = {row["file"] for row in saturn_rows}
        self.assertNotIn("ICON.FON", names)
        self.assertEqual(
            {row["name"] for row in saturn_rows},
            {
                "FNT8x12 - Battle Console (12x8 Source Fixed)",
                "FNT12x12 - Battle Console Kanji (12x12 Source Fixed)",
                "FONT12 - Fusion Text (12px Source)",
                "FONT16 - General Text (16px Source)",
                "FONT6 - HP/MP Text",
                "FONT8 - Menu Text (8px Source)",
                "KANJI - Name Entry Grid Text (16px Source)",
                "FONT16 2nd - Compendium Text",
                "TITLE Prompt - PRESS START BUTTON Raster",
                "TITLE Menu - START / OPTION Raster",
            },
        )
        self.assertEqual(len(psp_rows), 12)
        self.assertIn("regdata.bin member 3", {row["file"] for row in psp_rows})
        self.assertEqual(
            {row["id"] for row in psp_rows if row["confidence"] == "runtime_proven"},
            {"psp/eve_kanji_dialogue", "psp/datapack_font16_pages"},
        )

    def test_title_visual_fonts_expose_the_proved_positional_runs(self) -> None:
        prompt = self.application.fonts.detail("game/title_prompt")
        menu = self.application.fonts.detail("game/title_menu")

        self.assertEqual(prompt["slot_page"]["physical"], 16)
        self.assertEqual(
            "".join(slot["source_value"] for slot in prompt["slots"]),
            "PRESSSTARTBUTTON",
        )
        self.assertEqual(prompt["surfaces"], ["title.press_start"])
        self.assertFalse(prompt["can_import"])
        self.assertFalse(prompt["can_rebuild"])

        self.assertEqual(menu["slot_page"]["physical"], 11)
        self.assertEqual(
            "".join(slot["source_value"] for slot in menu["slots"]),
            "STARTOPTION",
        )
        self.assertEqual(menu["slots"][8]["record_width"], 8)
        self.assertEqual(
            menu["surfaces"], ["title.menu_start", "title.menu_option"]
        )

    def test_title_text_surfaces_preview_with_visual_rasters(self) -> None:
        for entry_id, surface_name in (
            ("ui/title.json#press_start_button.text", "title.press_start"),
            ("ui/title.json#start.text", "title.menu_start"),
            ("ui/title.json#option.text", "title.menu_option"),
        ):
            entry = self.application.catalog.entry(entry_id)
            result = self.application.evaluate(entry_id, entry["translation"])
            preview = result["surfaces"][0]["preview"]
            self.assertEqual(preview["surface"], surface_name)
            self.assertEqual(preview["fidelity"], "exact-visual-font")
            self.assertTrue(preview["data_url"].startswith("data:image/png"))

    def test_title_visual_font_generation_is_explicitly_locked(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile-specific"):
            self.application.fonts.update_plan("game/title_prompt")

    def test_elevator_definition_previews_the_composed_floor_label(self) -> None:
        entry = self.application.catalog.entry(
            "field/elevator.json#floor_definition.text"
        )
        result = self.application.evaluate(entry["id"], entry["translation"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["surfaces"][0]["name"], "field.elevator_floor")
        self.assertEqual(result["surfaces"][0]["lines"], [{"text": "B1F", "width": 20}])

    def test_font8_alphabet_is_owned_by_each_corpus_field(self) -> None:
        command = self.application.catalog.entry(
            "battle/commands.json#go.name"
        )
        inventory = self.application.catalog.entry(
            "facilities/shop.json#inventory_label.text"
        )
        self.assertEqual(command["font8_alphabet"], "original")
        self.assertTrue(command["font8_configurable"])
        self.assertEqual(inventory["font8_alphabet"], "replaced")
        self.assertTrue(inventory["font8_configurable"])
        evaluation = self.application.evaluate(
            inventory["id"], inventory["translation"], "replaced"
        )
        self.assertTrue(evaluation["valid"])
        self.assertEqual(evaluation["surfaces"][0]["lines"][0]["width"], 15)


class FontMappingTests(unittest.TestCase):
    def test_remap_preserves_original_glyph_identity(self) -> None:
        source_path = Path("saturn/font/config/game/font16.json")
        document = json.loads(source_path.read_text(encoding="utf-8"))
        original = replace_glyph_mapping(document, 11, "É")
        self.assertEqual(original, "A")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "font16.json"
            candidate.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            definition = load_definition(candidate, "game")
        self.assertEqual(definition.glyphs[11], "A")
        self.assertEqual(definition.replacements[11], "É")
        rebuilt = repack_font(definition.source_path.read_bytes(), definition)
        metrics = json.loads(rebuilt.metrics or "{}")
        self.assertIn("É", {row["text"] for row in metrics["glyphs"]})

    def test_source_correction_preserves_replacement(self) -> None:
        source_path = Path("saturn/font/config/game/font16.json")
        document = json.loads(source_path.read_text(encoding="utf-8"))
        original = replace_source_mapping(document, 173, "あ")
        self.assertIsNotNone(original)
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "font16.json"
            candidate.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            definition = load_definition(candidate, "game")
        self.assertEqual(definition.glyphs[173], "あ")
        self.assertEqual(definition.replacements[173], "-")

    def test_source_mapping_can_define_an_unknown_physical_cell(self) -> None:
        source_path = Path("saturn/font/config/game/font6.json")
        document = json.loads(source_path.read_text(encoding="utf-8"))
        original = replace_source_mapping(document, 0, "Blank")
        self.assertIsNone(original)
        self.assertIn("mapped_source", document["atlas"]["groups"])
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "font6.json"
            candidate.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            definition = load_definition(candidate, "game")
        self.assertEqual(definition.glyphs[0], "Blank")

    def test_automatic_language_mapping_preserves_basic_latin_first(self) -> None:
        definition = load_definition(
            Path("saturn/font/config/game/font16.json"), "game"
        )
        mappings = FontService.automatic_mappings(
            definition,
            "éçœ",
            {character: 0 for character in definition.replacements.values()},
        )
        self.assertEqual(set(mappings.values()), {"é", "ç", "œ"})
        displaced = {
            definition.replacements[int(code)] for code in mappings
        }
        self.assertTrue(displaced.isdisjoint(set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))


class LanguageProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "en.json").write_text(
            Path("assets/languages/en.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.languages = LanguageService(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_and_edit_language_project(self) -> None:
        created = self.languages.create("fr", "French", "fr-FR", "éèçœ")
        self.assertEqual(created["base"], "en")
        self.assertEqual(created["characters"], "éèçœ")
        updated = self.languages.update(
            "fr", "Français", "fr-FR", "éèçœà", created["file_hash"]
        )
        self.assertEqual(updated["label"], "Français")
        self.assertEqual(updated["characters"], "éèçœà")

    def test_english_project_is_built_in(self) -> None:
        detail = self.languages.detail("en")
        self.assertTrue(detail["built_in"])
        with self.assertRaisesRegex(ValueError, "cannot be edited"):
            self.languages.update(
                "en", "English", "en", "é", detail["file_hash"]
            )

    def test_typeface_import_builds_isolated_language_font(self) -> None:
        self.languages.create("fr", "French", "fr-FR", "éçœ")
        asset_fonts = self.root / "font-assets"
        generated = self.root / "generated"
        atlases = self.root / "atlases"
        typeface = Path(
            "assets/font/ark-pixel/ark-pixel-12px-proportional-latin.otf"
        )
        service = FontService(CorpusCatalog(), self.languages)
        with (
            patch("tools.editor.fonts.ASSET_FONT_ROOT", asset_fonts),
            patch("tools.editor.fonts.GENERATED_ROOT", generated),
            patch("tools.editor.fonts.ATLAS_ROOT", atlases),
            patch("saturn.font.util.definitions.ASSET_FONT_ROOT", asset_fonts),
        ):
            detail = service.import_typeface(
                "fr", "game/font16", typeface.name, typeface.read_bytes()
            )
            self.assertTrue(detail["customized"])
            self.assertEqual(detail["language"], "fr")
            self.assertTrue(
                detail["atlases"]["modified"].startswith("data:image/png")
            )
            self.assertTrue(
                (generated / "languages/fr/game/FONT16.FON").is_file()
            )
            imported = self.languages.detail("fr")["fonts"]["game/font16"]
            self.assertGreater(len(imported["mappings"]), 3)
            plan = service.update_plan("game/font16", "fr")
            self.assertTrue({"é", "ç", "œ"} <= set(plan["mappings"].values()))
            self.assertGreater(plan["audit"]["required_uses"], 0)
            service.apply_update(
                "game/font16",
                "fr",
                plan["base_hash"],
                confirm_required=True,
            )
            self.assertTrue(
                {"é", "ç", "œ"}
                <= set(
                    self.languages.detail("fr")["fonts"]["game/font16"][
                        "mappings"
                    ].values()
                )
            )

    def test_source_values_are_written_to_the_font_definition(self) -> None:
        config_root = self.root / "config"
        (config_root / "game").mkdir(parents=True)
        (config_root / "compendium").mkdir()
        source = Path("saturn/font/config/game/fnt8x12.json")
        target = config_root / "game/fnt8x12.json"
        target.write_bytes(source.read_bytes())
        with (
            patch("tools.editor.fonts.CONFIG_ROOT", config_root),
            patch("saturn.font.util.definitions.CONFIG_ROOT", config_root),
        ):
            service = FontService(CorpusCatalog(), self.languages)
            before = service.detail("game/fnt8x12", query="0x000B")
            saved = service.save_source_value(
                "game/fnt8x12", 11, "?", before["source_hash"]
            )
            self.assertEqual(saved["source_status"], "defined")
            after = service.detail("game/fnt8x12", query="0x000B")
            self.assertEqual(after["slots"][0]["source_value"], "?")
            self.assertEqual(after["slots"][0]["source_status"], "defined")
            corrected = service.save_source_value(
                "game/fnt8x12",
                1,
                "{mag\\_symbol}",
                after["source_hash"],
            )
            self.assertEqual(corrected["source_status"], "defined")
            final = service.detail("game/fnt8x12", query="0x0001")
            self.assertEqual(
                final["slots"][0]["source_value"], "{mag_symbol}"
            )
        definition = load_definition(target, "game")
        self.assertEqual(definition.glyphs[11], "?")
        self.assertEqual(definition.glyphs[1], "{mag_symbol}")

    def test_english_replacement_typeface_is_stored_in_base_definition(self) -> None:
        config_root = self.root / "config"
        (config_root / "game").mkdir(parents=True)
        (config_root / "compendium").mkdir()
        target = config_root / "game/font16.json"
        target.write_bytes(
            Path("saturn/font/config/game/font16.json").read_bytes()
        )
        asset_fonts = self.root / "font-assets"
        generated = self.root / "generated"
        atlases = self.root / "atlases"
        (generated / "game").mkdir(parents=True)
        (generated / "game/FONT16.FON").write_bytes(
            Path("saturn/font/generated/game/FONT16.FON").read_bytes()
        )
        typeface = Path(
            "assets/font/ark-pixel/ark-pixel-12px-proportional-latin.otf"
        )
        with (
            patch("tools.editor.fonts.CONFIG_ROOT", config_root),
            patch("tools.editor.fonts.ASSET_FONT_ROOT", asset_fonts),
            patch("tools.editor.fonts.GENERATED_ROOT", generated),
            patch("tools.editor.fonts.ATLAS_ROOT", atlases),
            patch("saturn.font.util.definitions.CONFIG_ROOT", config_root),
            patch("saturn.font.util.definitions.ASSET_FONT_ROOT", asset_fonts),
            patch("saturn.font.util.definitions.GENERATED_ROOT", generated),
            patch("saturn.font.util.definitions.ATLAS_ROOT", atlases),
        ):
            service = FontService(CorpusCatalog(), self.languages)
            detail = service.import_typeface(
                "en", "game/font16", "My Typeface.otf", typeface.read_bytes()
            )
            self.assertIn("imported/en/My-Typeface-", detail["source"])
            self.assertTrue(detail["can_import"])
            document = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(document["repack"]["source"], detail["source"])
            self.assertTrue((generated / "game/FONT16.FON").is_file())


class SavingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.asset_root = root / "assets"
        self.binding_root = root / "bindings"
        self.asset_root.mkdir()
        self.binding_root.mkdir()
        self.asset_path = self.asset_root / "sample.json"
        self.asset_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "kind": "entity_catalog",
                    "entries": {
                        "greeting": {
                            "text": {
                                "reference": "こんにちは",
                                "translation": "Hello",
                            }
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.binding_root / "sample.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "asset": "sample.json",
                    "records": {"game.sample.p00": "greeting.text"},
                    "field_surfaces": {"text": ["event.dialogue"]},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        catalog = CorpusCatalog(
            asset_root=self.asset_root, binding_root=self.binding_root
        )
        self.application = EditorApplication(catalog)
        self.entry_id = "sample.json#greeting.text"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_save_is_atomic_and_refreshes_hash(self) -> None:
        before = self.application.catalog.entry(self.entry_id)
        result = self.application.save(self.entry_id, "Welcome", before["file_hash"])
        self.assertEqual(result["entry"]["translation"], "Welcome")
        document = json.loads(self.asset_path.read_text(encoding="utf-8"))
        self.assertEqual(
            document["entries"]["greeting"]["text"]["translation"], "Welcome"
        )
        self.assertEqual(
            result["entry"]["file_hash"],
            hashlib.sha256(self.asset_path.read_bytes()).hexdigest(),
        )

    def test_entry_browser_reports_and_filters_by_surface(self) -> None:
        result = self.application.catalog.list_entries(
            surface="event.dialogue"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["matching_total"], 1)
        self.assertEqual(
            result["surface_counts"],
            [{"name": "event.dialogue", "count": 1}],
        )
        self.assertEqual(result["entries"][0]["id"], self.entry_id)

        other = self.application.catalog.list_entries(surface="battle.command")
        self.assertEqual(other["total"], 0)
        self.assertEqual(other["matching_total"], 1)
        self.assertEqual(other["surface_counts"], result["surface_counts"])

    def test_font8_alphabet_defaults_to_replaced_and_can_be_saved(self) -> None:
        before = self.application.catalog.entry(self.entry_id)
        self.assertEqual(before["font8_alphabet"], "replaced")
        result = self.application.save(
            self.entry_id,
            before["translation"],
            before["file_hash"],
            "original",
        )
        self.assertEqual(result["entry"]["font8_alphabet"], "original")
        document = json.loads(self.asset_path.read_text(encoding="utf-8"))
        self.assertEqual(
            document["entries"]["greeting"]["text"]["font8_alphabet"],
            "original",
        )

    def test_stale_hash_does_not_overwrite_external_edit(self) -> None:
        before = self.application.catalog.entry(self.entry_id)
        self.asset_path.write_text(
            self.asset_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
        )
        with self.assertRaisesRegex(RuntimeError, "changed on disk"):
            self.application.save(self.entry_id, "Welcome", before["file_hash"])

    def test_font_audit_uses_bound_surface_and_ignores_function_tokens(self) -> None:
        audit = self.application.catalog.font_usage_audit(
            "game/font16", {"{original_a}"}
        )
        self.assertEqual(audit["required"], {"H": 1, "e": 1, "l": 2, "o": 1})
        self.assertEqual(sum(audit["preferred"].values()), 5)

    def test_font_audit_does_not_require_replaced_source_compounds(self) -> None:
        audit = self.application.catalog.font_usage_audit(
            "game/font16",
            {"He", "l", "o"},
            {"H", "e", "l", "o"},
        )
        self.assertEqual(audit["required"], {"H": 1, "e": 1, "l": 2, "o": 1})
        self.assertEqual(
            CorpusCatalog._glyph_counts("Hello", {"He", "l", "o"}),
            {"He": 1, "l": 2, "o": 1},
        )


if __name__ == "__main__":
    unittest.main()
