"""Generate reference atlases from the original Saturn font files."""

from __future__ import annotations

import argparse

from util.codec import glyph_count, png_bytes, render_atlas
from util.definitions import select_definitions, verify_file


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
        help="font filename or stem to extract; may be repeated",
    )
    parser.add_argument(
        "--check", action="store_true", help="verify existing atlases without writing"
    )
    arguments = parser.parse_args()

    try:
        for definition in select_definitions(arguments.discs, arguments.fonts):
            for target_name, target in zip(
                definition.targets, definition.target_paths, strict=True
            ):
                verify_file(
                    target,
                    definition.sha256,
                    f"{definition.disc} font target {target_name}",
                )
            source = definition.source_path.read_bytes()
            atlas = png_bytes(render_atlas(source, definition))
            output = definition.original_atlas_path
            if arguments.check:
                if not output.is_file() or output.read_bytes() != atlas:
                    raise ValueError(f"stale original atlas: {output}")
                action = "verified"
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(atlas)
                action = "extracted"
            print(
                f"[{definition.disc}] {definition.file}: {action} "
                f"{glyph_count(source, definition):,} glyphs -> {output}"
            )
    except (KeyError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
