"""Rebuild Saturn fonts and their modified reference atlases."""

from __future__ import annotations

import argparse
from pathlib import Path

from util.codec import glyph_count, png_bytes, repack_font
from util.definitions import select_definitions, sha256, verify_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "discs",
        nargs="*",
        metavar="DISC",
        help="game, compendium, or all (default: all)",
    )
    parser.add_argument(
        "--font",
        dest="fonts",
        action="append",
        default=[],
        metavar="FONT",
        help="font filename or stem to repack; may be repeated",
    )
    parser.add_argument(
        "--check", action="store_true", help="verify generated outputs without writing"
    )
    arguments = parser.parse_args()

    try:
        for definition in select_definitions(arguments.discs, arguments.fonts):
            source_is_original = (
                definition.source_path.is_file()
                and sha256(definition.source_path) == definition.sha256
            )
            source_is_installed = (
                arguments.check
                and definition.generated_path.is_file()
                and definition.source_path.is_file()
                and definition.source_path.read_bytes()
                == definition.generated_path.read_bytes()
            )
            if not source_is_original and not source_is_installed:
                verify_file(
                    definition.source_path,
                    definition.sha256,
                    f"{definition.file} source",
                )
            for target_name, target in zip(
                definition.targets[1:], definition.target_paths[1:], strict=True
            ):
                target_is_original = (
                    target.is_file() and sha256(target) == definition.sha256
                )
                target_is_installed = (
                    arguments.check
                    and definition.generated_path.is_file()
                    and target.is_file()
                    and target.read_bytes() == definition.generated_path.read_bytes()
                )
                if not target_is_original and not target_is_installed:
                    verify_file(
                        target,
                        definition.sha256,
                        f"{definition.file} mirror {target_name}",
                    )
            if definition.source_font is not None:
                verify_file(
                    definition.source_font,
                    definition.source_sha256 or "",
                    f"{definition.file} source typeface",
                )
            source = definition.source_path.read_bytes()
            result = repack_font(source, definition)
            atlas = png_bytes(result.atlas)

            outputs: list[tuple[Path, bytes]] = [
                (definition.generated_path, result.data),
                (definition.modified_atlas_path, atlas),
            ]
            if result.metrics is not None:
                outputs.append(
                    (definition.metrics_path, result.metrics.encode("utf-8"))
                )

            if arguments.check:
                stale = [
                    path
                    for path, value in outputs
                    if not path.is_file() or path.read_bytes() != value
                ]
                if stale:
                    raise ValueError(
                        "stale generated font outputs:\n  "
                        + "\n  ".join(str(path) for path in stale)
                    )
                action = "verified"
            else:
                for path, value in outputs:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(value)
                action = "repacked"

            changed = sum(
                left != right for left, right in zip(source, result.data, strict=True)
            )
            print(
                f"[{definition.disc}] {definition.file}: {action} "
                f"{glyph_count(source, definition):,} glyphs / "
                f"{changed:,} changed bytes -> {definition.generated_path}"
            )
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
