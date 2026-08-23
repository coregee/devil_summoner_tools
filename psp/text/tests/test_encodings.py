from __future__ import annotations

import unittest

from psp.font.util.eve_ascii import glyph_code
from psp.font.util.title_help import load_config as load_title_font_config
from psp.text.util.event_packed import (
    ASCII_FIRST,
    ASCII_LAST,
    decode_ascii,
    encode_ascii,
    glyph_code_for_character,
    normalize_ascii,
)
from psp.text.util.title_help import load_config as load_title_text_config


class SharedEncodingTests(unittest.TestCase):
    def test_eve_font_and_text_use_one_printable_ascii_assignment(self) -> None:
        text = "".join(chr(code) for code in range(ASCII_FIRST, ASCII_LAST + 1))
        self.assertEqual(decode_ascii(encode_ascii(text)), text)
        self.assertEqual(
            tuple(glyph_code(character) for character in text),
            tuple(glyph_code_for_character(character) for character in text),
        )

    def test_shared_normalization_is_surface_neutral(self) -> None:
        self.assertEqual(
            normalize_ascii("‘Caf\u00e9’—test…\u3000value\r\n"),
            "'Cafe'-test... value\n",
        )

    def test_title_font_subset_is_derived_from_the_text_encoding(self) -> None:
        text_codes = dict(load_title_text_config().encoding)
        font_codes = dict(load_title_font_config().glyphs)
        self.assertTrue(font_codes.keys() <= text_codes.keys())
        self.assertEqual(font_codes, {key: text_codes[key] for key in font_codes})


if __name__ == "__main__":
    unittest.main()
