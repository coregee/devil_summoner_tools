"""Repack only Saturn images that differ from the extraction manifest."""

import argparse
import json

from util.paths import DISCS
from util.workflow import repack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disc",
        nargs="?",
        choices=(*DISCS, "all"),
        default="all",
        help="disc to repack (default: all)",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list changes only")
    action.add_argument(
        "--check", action="store_true", help="verify changes are repacked"
    )
    args = parser.parse_args()
    try:
        for disc in DISCS if args.disc == "all" else (args.disc,):
            views, targets, sources = repack(
                disc, check=args.check, list_only=args.list
            )
            verb = "verified" if args.check else "found" if args.list else "repacked"
            print(
                f"{disc} visual images: {verb} {views:,} changed views / "
                f"{targets:,} targets / {sources:,} sources"
            )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
