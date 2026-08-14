"""Extract the game and compendium Saturn discs into editable file mirrors."""

from __future__ import annotations

import argparse
from pathlib import Path

from util.catalog import (
    EXTRACTED_ROOT,
    load_catalog,
    select_discs,
    validate_source,
)
from util.workflows import extract_disc, list_iso_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "discs",
        nargs="*",
        metavar="DISC",
        help="game, compendium, or all (default: all)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXTRACTED_ROOT,
        help="parent directory for per-disc mirrors",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--list", action="store_true", help="validate sources and list ISO files"
    )
    action.add_argument(
        "--check", action="store_true", help="verify mirrors without writing"
    )
    action.add_argument(
        "--overwrite",
        action="store_true",
        help="restore extracted files that differ from the source disc",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        catalog = load_catalog()
        discs = select_discs(args.discs, catalog)
        for spec in discs:
            print(f"[{spec.disc_id}] validating {spec.title}")
            validated = validate_source(spec)
            output = args.output_root.resolve() / spec.disc_id
            if args.list:
                entries = list_iso_files(validated)
                for entry in entries:
                    print(
                        f"{spec.disc_id:10} {entry.path} "
                        f"({entry.size:,} bytes, LBA {entry.extent})"
                    )
                print(
                    f"[{spec.disc_id}] {len(entries):,} files / "
                    f"{sum(entry.size for entry in entries):,} bytes"
                )
                continue

            result = extract_disc(
                validated,
                output,
                check=args.check,
                overwrite=args.overwrite,
            )
            action = "verified" if args.check else "extracted"
            print(
                f"[{spec.disc_id}] {action} {result.files:,} files / "
                f"{result.total_bytes:,} bytes: {result.written:,} written, "
                f"{result.current:,} already current"
            )
            if result.extra:
                print(
                    f"[{spec.disc_id}] warning: left {result.extra:,} extra local "
                    "file(s) untouched; repacking requires an exact mirror"
                )
            print(f"[{spec.disc_id}] mirror: {output}")
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(error) from error


if __name__ == "__main__":
    main()
