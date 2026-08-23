"""Build or verify shared title and maze images as PSP pack members."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)

from psp.visual.util.workflow import repack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disc", nargs="?", choices=("game", "all"), default="all")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        document = repack(check=arguments.check)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    action = "verified" if arguments.check else "built"
    summary = document["summary"]
    print(
        f"PSP visuals {action}: {summary['shared_assets']} shared assets / "
        f"{summary['encoded_members']} encoded members / "
        f"{summary['physical_bindings']} physical bindings"
    )


if __name__ == "__main__":
    main()
