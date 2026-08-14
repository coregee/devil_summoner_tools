"""Rebuild Saturn BIN/CUE sets from the editable extracted disc mirrors."""

from __future__ import annotations

import argparse
from pathlib import Path

from util.catalog import (
    BUILD_ROOT,
    EXTRACTED_ROOT,
    load_catalog,
    select_discs,
    validate_source,
)
from util.workflows import plan_repack, repack_disc, verify_repack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "discs",
        nargs="*",
        metavar="DISC",
        help="game, compendium, or all (default: all)",
    )
    parser.add_argument(
        "--extracted-root",
        type=Path,
        default=EXTRACTED_ROOT,
        help="parent directory containing editable per-disc mirrors",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=BUILD_ROOT,
        help="parent directory for rebuilt per-disc BIN/CUE sets",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--list", action="store_true", help="show changed files without rebuilding"
    )
    action.add_argument(
        "--check", action="store_true", help="verify existing rebuilt discs"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="transactionally replace a populated per-disc build directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.check and args.overwrite:
        raise SystemExit("--check and --overwrite cannot be combined")
    try:
        catalog = load_catalog()
        discs = select_discs(args.discs, catalog)
        for spec in discs:
            print(f"[{spec.disc_id}] validating {spec.title}")
            validated = validate_source(spec)
            extracted = args.extracted_root.resolve() / spec.disc_id
            output = args.output_root.resolve() / spec.disc_id
            plan = plan_repack(validated, extracted)
            changed = [item for item in plan if item.changed]
            for item in changed:
                size_note = (
                    f", source size {item.entry.size:,}" if item.size_changed else ""
                )
                print(
                    f"[{spec.disc_id}] replace {item.relative} "
                    f"({item.size:,}/{item.entry.capacity:,} bytes{size_note})"
                )
            print(
                f"[{spec.disc_id}] plan: {len(changed):,} changed / "
                f"{len(plan):,} total files"
            )
            if args.list:
                continue
            if args.check:
                result = verify_repack(validated, output, plan)
                print(
                    f"[{spec.disc_id}] verified {result.files:,} files and "
                    f"{result.raw_changed_sectors:,} permitted raw-sector changes"
                )
                print(f"[{spec.disc_id}] disc: {result.output_cue}")
                continue

            result = repack_disc(
                validated,
                extracted,
                output,
                overwrite=args.overwrite,
            )
            print(
                f"[{spec.disc_id}] rebuilt {result.files:,} files; "
                f"rewrote {result.rewritten_sectors:,} sectors; "
                f"verified {result.raw_changed_sectors:,} raw-sector changes"
            )
            print(f"[{spec.disc_id}] disc: {result.output_cue}")
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(error) from error


if __name__ == "__main__":
    main()
