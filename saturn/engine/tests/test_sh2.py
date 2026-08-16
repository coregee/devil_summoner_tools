from __future__ import annotations

import sys
import unittest
from pathlib import Path


SATURN_ROOT = Path(__file__).resolve().parents[2]
if str(SATURN_ROOT) not in sys.path:
    sys.path.insert(0, str(SATURN_ROOT))

from engine.core.sh2 import AssemblyError, assemble  # noqa: E402


class Sh2AssemblerTests(unittest.TestCase):
    def test_instructions_are_emitted_big_endian(self) -> None:
        result = assemble("mov #-31, r6\nnop", 0x06020000)
        self.assertEqual(result.data, bytes.fromhex("e6e10009"))
        self.assertEqual(result.warnings, ())

    def test_labels_and_literal_pools_are_resolved_at_the_patch_address(self) -> None:
        result = assemble(
            "mov.l =TARGET, r0\njmp @r0\nnop\n.pool",
            0x06033C9C,
            {"TARGET": 0x060209BC},
        )
        self.assertEqual(result.data, bytes.fromhex("d001402b00090000060209bc"))
        self.assertEqual(result.warnings, ())

    def test_unknown_syntax_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssemblyError, "unknown or unsupported"):
            assemble("frob r1, r2", 0x06020000)
        with self.assertRaisesRegex(AssemblyError, "undefined symbol"):
            assemble("mov.l =MISSING, r0", 0x06020000)

    def test_delay_slot_hazards_are_reported(self) -> None:
        result = assemble("rts\n.pool", 0x06020000)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
