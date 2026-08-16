from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.core.patch_recipes import ASSEMBLY_ROOT  # noqa: E402
from engine.surfaces.dungeon_locations import (  # noqa: E402
    MAZE_TARGET,
    build_dungeon_locations,
)
from engine.surfaces.field_messages import (  # noqa: E402
    CAVE_LIMIT,
    CHOICE_BITMAPS,
    CHOICE_CELLS,
    COMPOSITOR,
    CONFIG_PATH,
    CURRENCY_MAG_CODE,
    CURRENCY_YEN_CODE,
    DIRECT_RECORDS,
    DYNAMIC_TEMPLATES,
    FONT16_METRICS_PATH,
    ITEM_TEMPLATES,
    LOAD_ADDRESS,
    MESSAGE_BUFFER_WORDS,
    PROMPT_CODE,
    STATIC_FIELDS,
    TARGET,
    _bound_terms,
    _build_runtime,
    _configuration,
    _encode,
    _source_maze,
    _template_data,
    _templates,
    _validate_geometry,
    _validate_inputs,
    build_field_messages,
)
from text.util.event_repack import FontMetrics  # noqa: E402


STOCK_OUTPUT_SHA256 = (
    "9445d8e80974910101c0c6dc028f3c8cba75a434f1d3e073c81989d60968d4f4"
)
LOCATION_BASE_SHA256 = (
    "9e3b197ece3556a573c6078e09a9a8f3550647f6d7b51b741cccde14364a615a"
)
COMPOSED_OUTPUT_SHA256 = (
    "b94dd9321f556c1daeeff220149d08581d996fac77ac147f7fe1ee5f62a265e2"
)
DIRECT_HASHES = {
    "operation_disabled": (
        "05da2a0487c737d7e7287e3b5cf5049601fb4fb285175add8c9c5ca6f08dc053"
    ),
    "nothing_notable": (
        "09850b8f81087312b59508f4a29dc516101fc887fb075e092baeabfa4470889e"
    ),
    "nothing_found": (
        "0d70a088c6808d5fa9098a79781a406ef5e516b232950e8dccbd288e9a149e25"
    ),
    "inventory_full": (
        "dc9027dcc2138d8daefbee48c0b6bd5f20279cf7ebb8d4ff0a4d136ced077262"
    ),
    "auto_recover_on": (
        "a9bb5b26920f68c7df298cbc92a4d491027de76e2d9fd0b27282b8e0c1a34374"
    ),
    "no_effect": (
        "46f4f450a0756f3ac29d449e20c34506d9a440d116048e427a3e38d558ee54ff"
    ),
}
ASSEMBLY_INPUTS = {
    "field_messages/choice_draw.s",
    "field_messages/compositor.s",
    "field_messages/display.s",
    "field_messages/item_hook.s",
    "field_messages/item_templates.s",
}
PLACEHOLDER_SPANS = (0x251D0, 0x251DC, 0x251E8, 0x251F4)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FieldMessagesEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = _source_maze()
        cls.config = _configuration()
        cls.result = build_field_messages(cls.stock)
        cls.patches = {item.name: item for item in cls.result.patches}
        cls.runtime = _build_runtime(cls.config)
        cls.terms = _bound_terms()
        cls.templates = _templates()
        cls.metrics = FontMetrics.load(FONT16_METRICS_PATH)
        cls.location_build = build_dungeon_locations()
        cls.location_base = cls.location_build.outputs[MAZE_TARGET]
        cls.composed = build_field_messages(cls.location_base)

    def test_stock_and_location_composition_are_deterministic(self) -> None:
        self.assertEqual(len(self.result.data), 169_264)
        self.assertEqual(_sha256(self.result.data), STOCK_OUTPUT_SHA256)
        self.assertEqual(_sha256(self.location_base), LOCATION_BASE_SHA256)
        self.assertEqual(_sha256(self.composed.data), COMPOSED_OUTPUT_SHA256)
        self.assertEqual(len(self.result.patches), 43)
        self.assertEqual(len(self.composed.patches), 43)

        location_cave = next(
            patch
            for patch in self.location_build.patches[MAZE_TARGET]
            if patch.name == "renderer_cave"
        )
        start = location_cave.address - LOAD_ADDRESS
        end = start + len(location_cave.replacement)
        self.assertEqual(
            self.composed.data[start:end], self.location_base[start:end]
        )

    def test_six_direct_records_match_the_mature_oracle(self) -> None:
        self.assertEqual(set(DIRECT_RECORDS), set(DIRECT_HASHES))
        for name, digest in DIRECT_HASHES.items():
            with self.subTest(record=name):
                self.assertEqual(
                    _sha256(self.patches[name].replacement), digest
                )

    def test_long_direct_edit_uses_stock_selector_and_cave_string(self) -> None:
        text = "i" * 29
        self.assertLessEqual(self.metrics.measure(text), 224)
        terms = dict(self.terms)
        terms["game.maze_messages.o025124"] = text
        with patch(
            "engine.surfaces.field_messages._bound_terms", return_value=terms
        ):
            changed = build_field_messages(self.stock)

        patches = {item.name: item for item in changed.patches}
        self.assertEqual(
            patches["operation_disabled"].replacement,
            patches["operation_disabled"].expected,
        )
        codes = _encode(text, self.metrics, "long direct edit")
        self.assertIn(
            struct.pack(f">{len(codes) + 1}H", *codes, 0),
            patches["message_strings"].replacement,
        )

    def test_recipe_and_readable_source_inventory_is_exact(self) -> None:
        recipes = self.config.patches[TARGET]
        self.assertEqual(
            Counter(recipe.replacement.kind for recipe in recipes),
            {"assembly": 7, "generated": 15, "linked_pointer": 21},
        )
        self.assertEqual(
            Counter(recipe.group for recipe in recipes),
            {
                "field_message_runtime": 11,
                "field_message_dispatch": 26,
                "field_message_records": 6,
            },
        )
        sources = {
            source.relative_to(ASSEMBLY_ROOT).as_posix()
            for recipe in recipes
            for source in recipe.replacement.sources
        }
        self.assertEqual(sources, ASSEMBLY_INPUTS)
        self.assertEqual(
            {
                path.relative_to(ASSEMBLY_ROOT).as_posix()
                for path in self.result.assembly_files
            },
            ASSEMBLY_INPUTS,
        )
        config_source = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"replacement"', config_source)
        self.assertEqual(json.loads(config_source)["version"], 2)

    def test_placeholder_fragments_remain_byte_neutral(self) -> None:
        patched_ranges = tuple(
            (
                patch.address - LOAD_ADDRESS,
                patch.address - LOAD_ADDRESS + len(patch.replacement),
            )
            for patch in self.result.patches
        )
        for offset in PLACEHOLDER_SPANS:
            with self.subTest(offset=f"{offset:#x}"):
                self.assertEqual(
                    self.result.data[offset : offset + 12],
                    self.stock[offset : offset + 12],
                )
                self.assertFalse(
                    any(start < offset + 12 and offset < end for start, end in patched_ranges)
                )

    def test_item_paths_call_three_distinct_authored_templates(self) -> None:
        targets = (
            ITEM_TEMPLATES,
            ITEM_TEMPLATES + 6,
            ITEM_TEMPLATES + 12,
        )
        selected: list[int] = []
        for name in ("item_found_hook", "item_obtained_hook", "item_full_hook"):
            matches = [
                target
                for target in targets
                if struct.pack(">I", target) in self.patches[name].replacement
            ]
            self.assertEqual(len(matches), 1, name)
            selected.extend(matches)
        self.assertEqual(tuple(selected), targets)

    def test_every_dynamic_template_rebuilds_runtime_data(self) -> None:
        edited = {
            "item_found": ("Located ", "!"),
            "item_obtained": ("Received ", "!"),
            "item_full": ("No room for ", "!"),
            "currency_yen": ("Cash ", " yen."),
            "currency_mag": ("MAG ", " acquired!"),
        }
        with patch(
            "engine.surfaces.field_messages._templates", return_value=edited
        ):
            changed = _build_runtime(self.config)
        self.assertNotEqual(
            changed.generated["dynamic_templates"],
            self.runtime.generated["dynamic_templates"],
        )
        self.assertNotEqual(
            changed.assembly["item_templates"],
            self.runtime.assembly["item_templates"],
        )
        self.assertNotEqual(
            changed.assembly["message_compositor"],
            self.runtime.assembly["message_compositor"],
        )

        data, labels, counts = _template_data(edited, self.metrics)
        for name, (prefix, suffix) in edited.items():
            for role, text in (("prefix", prefix), ("suffix", suffix)):
                key = f"{name}_{role}"
                codes = _encode(text, self.metrics, key)
                start = labels[key] - DYNAMIC_TEMPLATES
                self.assertEqual(
                    struct.unpack_from(f">{len(codes)}H", data, start), codes
                )
                self.assertEqual(counts[key], len(codes))

        compositor = changed.assembly["message_compositor"]
        for key in (
            "currency_yen_prefix",
            "currency_yen_suffix",
            "currency_mag_prefix",
            "currency_mag_suffix",
        ):
            self.assertIn(struct.pack(">I", labels[key]), compositor)

        digits = _encode("123", self.metrics, "currency digits")
        yen = (
            *_encode(edited["currency_yen"][0], self.metrics, "yen prefix"),
            CURRENCY_YEN_CODE,
            *digits,
            *_encode(edited["currency_yen"][1], self.metrics, "yen suffix"),
        )
        mag = (
            *_encode(edited["currency_mag"][0], self.metrics, "MAG prefix"),
            CURRENCY_MAG_CODE,
            *digits,
            *_encode(edited["currency_mag"][1], self.metrics, "MAG suffix"),
        )
        self.assertEqual(yen[len(_encode("Cash ", self.metrics, "yen"))], 0xC0)
        self.assertEqual(mag[len(_encode("MAG ", self.metrics, "MAG"))], 0xC1)
        self.assertNotEqual(yen[: -len(digits)], mag[: -len(digits)])

    def test_currency_parser_requires_symbol_before_amount_and_keeps_suffix(self) -> None:
        values = {
            ("item_found.text", None): "Found {item}.",
            ("item_obtained.text", None): "Obtained {item}.",
            ("item_full.text", None): "No room for {item}.",
            ("currency_obtained.text", None): (
                "Cash {yen_symbol}{currency_amount} yen."
            ),
            ("currency_obtained.text", "magnetite"): (
                "MAG {mag_symbol}{currency_amount} acquired!"
            ),
        }

        def authored(asset_ref: str, variant: str | None = None) -> str:
            return values[(asset_ref, variant)]

        with patch(
            "engine.surfaces.field_messages._asset_translation",
            side_effect=authored,
        ):
            parsed = _templates()
        self.assertEqual(parsed["currency_yen"], ("Cash ", " yen."))
        self.assertEqual(parsed["currency_mag"], ("MAG ", " acquired!"))

        values[("currency_obtained.text", None)] = (
            "Cash {currency_amount}{yen_symbol} yen."
        )
        with patch(
            "engine.surfaces.field_messages._asset_translation",
            side_effect=authored,
        ), self.assertRaisesRegex(ValueError, "exactly one"):
            _templates()

    def test_four_character_choice_uses_bitmap_and_stock_selector(self) -> None:
        terms = dict(self.terms)
        terms["game.maze_speech_choices_static.o0250d0"] = "Okay"
        self.assertGreater(len(_encode("Okay", self.metrics, "choice")), CHOICE_CELLS)
        self.assertLessEqual(self.metrics.measure("Okay"), CHOICE_CELLS * 16)
        with patch(
            "engine.surfaces.field_messages._bound_terms", return_value=terms
        ):
            changed = _build_runtime(self.config)
        selector = next(
            recipe for recipe in self.config.patches[TARGET] if recipe.name == "choice_yes"
        )
        self.assertEqual(changed.generated["choice_yes"], selector.expected)
        self.assertNotEqual(
            changed.generated["choice_bitmaps"][:96],
            self.runtime.generated["choice_bitmaps"][:96],
        )
        self.assertEqual(
            changed.generated["choice_bitmaps"][96:],
            self.runtime.generated["choice_bitmaps"][96:],
        )

    def test_width_and_buffer_limits_fail_closed(self) -> None:
        too_wide = dict(self.terms)
        too_wide["game.maze_messages.o0252d0"] = "W" * 30
        with patch(
            "engine.surfaces.field_messages._bound_terms", return_value=too_wide
        ), self.assertRaisesRegex(ValueError, "limit is 224px"):
            _build_runtime(self.config)

        wide_choice = dict(self.terms)
        wide_choice["game.maze_speech_choices_static.o0250d0"] = "W" * 6
        with patch(
            "engine.surfaces.field_messages._bound_terms", return_value=wide_choice
        ), self.assertRaisesRegex(ValueError, "three-cell renderer"):
            _build_runtime(self.config)

        narrow_templates = dict(self.templates)
        narrow_templates["item_found"] = (" " * 54, "")
        space = self.metrics.by_text[" "].code
        with self.assertRaisesRegex(ValueError, "runtime buffer"):
            _validate_geometry(
                self.terms,
                narrow_templates,
                self.metrics,
                ((space,) * 10,),
            )

    def test_cave_components_are_bounded_and_nonoverlapping(self) -> None:
        cave = sorted(
            (
                recipe.address,
                recipe.address + len(recipe.expected),
                recipe.name,
            )
            for recipe in self.config.patches[TARGET]
            if recipe.group == "field_message_runtime"
        )
        self.assertEqual(cave[0][0], COMPOSITOR)
        self.assertEqual(cave[-1][1], 0x060237E6)
        self.assertLessEqual(cave[-1][1], CAVE_LIMIT)
        for previous, current in zip(cave, cave[1:]):
            self.assertLessEqual(previous[1], current[0])
        for start, end, name in cave:
            self.assertEqual(
                len(self.patches[name].replacement), end - start, name
            )
            self.assertEqual(self.patches[name].expected, bytes(end - start))

        location_end = (
            next(
                patch
                for patch in self.location_build.patches[MAZE_TARGET]
                if patch.name == "renderer_cave"
            ).address
            + len(self.location_build.runtime_used[MAZE_TARGET])
        )
        self.assertLessEqual(location_end, COMPOSITOR)
        self.assertLess(CHOICE_BITMAPS + 192, CAVE_LIMIT)

    def test_runtime_contains_no_player_visible_prose_literals(self) -> None:
        module = (
            SATURN_ROOT / "engine" / "surfaces" / "field_messages.py"
        ).read_text(encoding="utf-8")
        assembly = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ASSEMBLY_ROOT / "field_messages").glob("*.s"))
        )
        for literal in (
            "Found ",
            "Obtained ",
            "Cannot hold more",
            " is full",
            "Delete?",
            "(No data)",
            "Someone is here",
        ):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, module)
                self.assertNotIn(literal, assembly)
        self.assertNotIn("bytes.fromhex", module)
        self.assertNotIn(".ascii", assembly)
        self.assertNotIn(".string", assembly)

    def test_itemname_is_bound_to_its_text_build(self) -> None:
        _validate_inputs(self.config, self.stock, self.stock)
        manifest_path = SATURN_ROOT / "text" / "generated" / "game" / "battle_ui_build.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["outputs"]["ITEMNAME.DAT"]["sha256"] = "0" * 64
        with patch(
            "engine.surfaces.field_messages.read_json", return_value=manifest
        ), self.assertRaisesRegex(ValueError, "does not match its text build"):
            _validate_inputs(self.config, self.stock, self.stock)

    def test_prompt_retains_the_stock_leading_substitution_cell(self) -> None:
        prompt = _encode(
            self.terms["game.maze_messages.o0250e4"],
            self.metrics,
            "talk prompt",
        )
        self.assertEqual(prompt[0], PROMPT_CODE)
        self.assertEqual(
            struct.unpack_from(">H", self.runtime.generated["message_strings"])[0],
            PROMPT_CODE,
        )
        self.assertEqual(len(STATIC_FIELDS), 11)
        self.assertEqual(MESSAGE_BUFFER_WORDS, 64)


if __name__ == "__main__":
    unittest.main()
