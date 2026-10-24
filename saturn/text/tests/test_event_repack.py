from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


TEXT_ROOT = Path(__file__).resolve().parents[1]
SATURN_ROOT = TEXT_ROOT.parent
if str(TEXT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEXT_ROOT))
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from repack import EVENT_BUILD_PATH, build_event_outputs  # noqa: E402
from util.event_codec import load_event_dictionary  # noqa: E402


MATURE_HASHES = {
    "MESFILE.EVE": "d573382945b418155213f79ec1bef185623f27b3dd8cabe42d7f96a1b5f66aa2",
    "EVFILE_0.EVE": "265eea4bc410a5c019a7039e31293a6be30e1ad172e17f2098bbb043dd80bf58",
    "EVFILE_1.EVE": "866b851f4c7b3e70576bd2ab536d0a04d53c7bfa6386fbb121a5b2242af25b25",
    "EVFILE_2.EVE": "6d2899086bf23f951f71cd2a7f4bfe08c219e6d2e5d3dd24440cf8aa32542d3d",
}


class GeneralEventRepackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs = build_event_outputs()

    def test_all_four_banks_match_the_mature_saturn_output(self) -> None:
        actual = {
            path.name: hashlib.sha256(value).hexdigest()
            for path, value in self.outputs.items()
            if path.suffix == ".EVE"
        }
        self.assertEqual(actual, MATURE_HASHES)

    def test_build_manifest_binds_every_output_and_surface(self) -> None:
        document = json.loads(self.outputs[EVENT_BUILD_PATH])
        self.assertEqual(document["surface"], "event.dialogue")
        self.assertEqual(document["records"], 2028)
        self.assertEqual(set(document["outputs"]), set(MATURE_HASHES))
        self.assertEqual(
            {name: row["sha256"] for name, row in document["outputs"].items()},
            MATURE_HASHES,
        )

    def test_dictionary_round_trips_mixed_glyph_and_control_words(self) -> None:
        dictionary = load_event_dictionary(TEXT_ROOT / "config" / "event_codec.json")
        codes = [11, 38, 267, 55, 0x8006, 12, 39, 40]
        encoded = dictionary.encode_codes(codes)
        self.assertEqual(dictionary.decode_words(encoded), codes)
        self.assertEqual(len(dictionary.runtime_table()), 57 * 8)


if __name__ == "__main__":
    unittest.main()
