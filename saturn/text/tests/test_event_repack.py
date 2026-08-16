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
    "MESFILE.EVE": "8be7a195458cea294429dad0d5abecd882e9405fa1e4bb0e03090e705923d2f2",
    "EVFILE_0.EVE": "9e16d42d13bca647056e6c226af2857f00fabd5e6829b0e003c67e90ec2ed236",
    "EVFILE_1.EVE": "1447128b01fc4e9fde30f83e93c7d9ecd98eb88dc2ce47d63164597f87d9e022",
    "EVFILE_2.EVE": "4716f03f2155bbe47ad75839afe7db9a0c31ab379437b4daba17076844571566",
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
