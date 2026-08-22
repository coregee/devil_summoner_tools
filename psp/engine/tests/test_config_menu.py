from __future__ import annotations

import unittest

from psp.engine.surfaces.config_menu import _fingerprint, _source
from psp.engine.surfaces.config_menu_runtime import (
    CONFIG_TRIANGLE,
    CONFIG_TRIANGLE_ADVANCE,
    CONFIG_TRIANGLE_CODE,
    build_config_menu_patch,
)


class ConfigMenuRuntimeTests(unittest.TestCase):
    def test_readable_emitter_retains_the_legacy_reference_fingerprint(self) -> None:
        source = _source()
        visible16 = tuple(
            sorted(set("".join(source.ark16_records)) - {" ", CONFIG_TRIANGLE})
        )
        first_code = 0x0672
        codes16 = {
            " ": 0,
            CONFIG_TRIANGLE: CONFIG_TRIANGLE_CODE,
            **{
                character: first_code + index
                for index, character in enumerate(visible16)
            },
        }
        advances16 = {
            " ": 4,
            CONFIG_TRIANGLE: CONFIG_TRIANGLE_ADVANCE,
            **{character: 5 + index % 6 for index, character in enumerate(visible16)},
        }
        visible12 = tuple(sorted(set("".join(source.modes)) - {" "}))
        codes12 = {
            " ": 0,
            **{character: 11 + index for index, character in enumerate(visible12)},
        }
        advances12 = {
            " ": 4,
            **{character: 5 + index % 4 for index, character in enumerate(visible12)},
        }
        result = build_config_menu_patch(
            source,
            codes16,
            advances16,
            codes12,
            advances12,
            ark16_advance_first_code=first_code,
            draw_code_limit=first_code + len(visible16),
        )
        self.assertEqual(len(result.writes), 45)
        self.assertEqual(
            _fingerprint(result.writes),
            "00fd7a3c165883f270e5d48be4049437fd6c2828a30692c8f583884ef53c99a1",
        )


if __name__ == "__main__":
    unittest.main()
