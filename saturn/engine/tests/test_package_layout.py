from __future__ import annotations

import unittest
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]


class EnginePackageLayoutTests(unittest.TestCase):
    def test_package_root_contains_only_the_build_entrypoint(self) -> None:
        modules = {path.name for path in ENGINE_ROOT.glob("*.py")}

        self.assertEqual(modules, {"__init__.py", "build.py"})


if __name__ == "__main__":
    unittest.main()
