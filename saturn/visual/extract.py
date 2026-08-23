"""Extract Saturn image baselines and validate bound replacement assets."""

import argparse
import json

from util.paths import DISCS
from util.workflow import extract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disc",
        nargs="?",
        choices=(*DISCS, "all"),
        default="all",
        help="disc to extract (default: all)",
    )
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the extracted baseline; never replaces shared assets",
    )
    args = parser.parse_args()
    try:
        for disc in DISCS if args.disc == "all" else (args.disc,):
            total, replacements = extract(
                disc, check=args.check, overwrite=args.overwrite
            )
            action = "verified" if args.check else "extracted"
            print(f"{disc} visual images: {action} {total:,} logical images")
            print(
                f"{disc} visual images: found {replacements:,} bound replacements"
            )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
