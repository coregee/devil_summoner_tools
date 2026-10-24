from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from repack import _stock_files  # noqa: E402
from util.battle_negotiation import (  # noqa: E402
    CHOICE_WIDTH,
    NEGOTIATION_EVE_SOURCES,
    TWO_CHOICE_WIDTH,
    negotiation_choice_messages,
)
from util.sources import load_manifest, manifest_path  # noqa: E402


SURFACE_WIDTHS = {
    "battle.negotiation_choice": CHOICE_WIDTH,
    "battle.negotiation_two_choice": TWO_CHOICE_WIDTH,
}
_RECORD_RE = re.compile(r"game\.([a-z0-9_]+)\.m([0-9]{4})\.p00\Z")


def _script(statements: list[list[int]], table_offset: int = 0x4800) -> bytes:
    words = [0] * (table_offset // 2)
    cursor = 0
    starts = []
    for statement in statements:
        starts.append(cursor)
        words[0x400 + cursor : 0x400 + cursor + len(statement)] = statement
        cursor += len(statement)
    starts.append(cursor)
    words[0x10 : 0x10 + len(starts) + 1] = [*starts, 0xFFFF]
    return b"".join(word.to_bytes(2, "big") for word in words)


class ChoiceParserTests(unittest.TestCase):
    def test_finds_two_three_and_four_way_choices(self) -> None:
        stock = _script(
            [
                [0x0000, 0x0007, 0x0001, 0x0000, 0x0008, 0x0010, 0x0009, 0x000A, 0x0011, 0x0001, 0x0002],
                [0x0000, 0x000B, 0x0012, 0x000C, 0x000D, 0x000E, 0x0013, 0x0001, 0x0002, 0x0003],
                [0x0014, 0x000C, 0x000F, 0x0020, 0x0021, 0x0015, 0x0001, 0x0002, 0x0003, 0x0004],
            ]
        )
        self.assertEqual(
            negotiation_choice_messages(stock, 0x4800),
            {
                0x09: TWO_CHOICE_WIDTH,
                0x0A: TWO_CHOICE_WIDTH,
                0x0C: CHOICE_WIDTH,
                0x0D: CHOICE_WIDTH,
                0x0E: CHOICE_WIDTH,
                0x0F: CHOICE_WIDTH,
                0x20: CHOICE_WIDTH,
                0x21: CHOICE_WIDTH,
            },
        )

    def test_ignores_choice_opcodes_used_as_operands(self) -> None:
        stock = _script(
            [
                [0x0000, 0x0012, 0x0001, 0x0084],
                [0x0018, 0x0012, 0x0013, 0x0014, 0x0015],
                [0x0048, 0x0010, 0x0011],
            ]
        )
        self.assertEqual(negotiation_choice_messages(stock, 0x4800), {})

    def test_bank_without_a_script_has_no_choices(self) -> None:
        self.assertEqual(negotiation_choice_messages(bytes(0x4800), 0x4800), {})


class ChoiceBindingTests(unittest.TestCase):
    """The binding tags must match the choices in the original scripts."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest = load_manifest(manifest_path("game"))
        sources = {source.name: source for source in manifest.sources}
        paths = {
            name: manifest.files[sources[name].container["file"]].path
            for name in NEGOTIATION_EVE_SOURCES
        }
        stock = _stock_files(tuple(paths.values()))
        cls.parsed = {
            f"game.{name}.m{message:04d}.p00": width
            for name, path in paths.items()
            for message, width in negotiation_choice_messages(
                stock[path], int(sources[name].container["table_offset"], 16)
            ).items()
        }

    def test_binding_tags_match_the_original_scripts(self) -> None:
        tagged: dict[str, int] = {}
        for path in sorted((TEXT_ROOT / "bindings").glob("negotiation_*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for record, surfaces in document.get("record_surfaces", {}).items():
                widths = [SURFACE_WIDTHS[surface] for surface in surfaces if surface in SURFACE_WIDTHS]
                if widths:
                    self.assertRegex(record, _RECORD_RE)
                    tagged[record] = min(widths)
        self.assertEqual(tagged, self.parsed)

    def test_choice_counts(self) -> None:
        widths = list(self.parsed.values())
        self.assertEqual(widths.count(CHOICE_WIDTH), 1370)
        self.assertEqual(widths.count(TWO_CHOICE_WIDTH), 480)


if __name__ == "__main__":
    unittest.main()
