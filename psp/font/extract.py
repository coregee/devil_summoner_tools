"""Import verified PSP font targets and generate logical reference atlases."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from util.codec import load_cell_data, png_bytes, render_atlas
from util.definitions import load_definitions
from util.pack import read_members


def _payload(root: Path, target: object) -> bytes:
    path = root.joinpath(*target.iso_path.split("/"))
    if not path.is_file():
        raise ValueError(f"extracted PSP file is missing: {path}")
    data = path.read_bytes()
    if target.kind == "pack_member":
        members = read_members(data)
        assert target.member_index is not None
        if target.member_index >= len(members):
            raise ValueError(f"{path} has no member {target.member_index}")
        member = members[target.member_index]
        if member.offset != target.offset:
            raise ValueError(
                f"{path} member {target.member_index} begins at {member.offset}; expected {target.offset}"
            )
        return member.data
    end = target.offset + target.size
    if end > len(data):
        raise ValueError(f"embedded PSP font exceeds {path}")
    return data[target.offset:end]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        help="root of an extracted original UMD (contains PSP_GAME)",
    )
    parser.add_argument("--font", action="append", default=[], help="resource id; repeatable")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        definitions = [
            definition
            for definition in load_definitions()
            if not arguments.font or definition.resource_id in arguments.font
        ]
        if arguments.font and len(definitions) != len(set(arguments.font)):
            raise ValueError("one or more requested PSP font ids are unknown")
        for definition in definitions:
            if arguments.source_root is not None:
                for index, target in enumerate(definition.targets):
                    payload = _payload(arguments.source_root, target)
                    digest = hashlib.sha256(payload).hexdigest()
                    if len(payload) != target.size or digest != target.sha256:
                        raise ValueError(
                            f"{definition.resource_id} target {index} does not match the checked original"
                        )
                    output = definition.source_paths[definition.logical_target_indices.index(index)] if index in definition.logical_target_indices else None
                    if output is not None:
                        if arguments.check:
                            if not output.is_file() or output.read_bytes() != payload:
                                raise ValueError(f"stale PSP font source: {output}")
                        else:
                            output.parent.mkdir(parents=True, exist_ok=True)
                            output.write_bytes(payload)
            data = load_cell_data(definition)
            atlas = png_bytes(render_atlas(data, definition))
            output = definition.original_atlas_path
            if arguments.check:
                if not output.is_file() or output.read_bytes() != atlas:
                    raise ValueError(f"stale PSP font atlas: {output}")
                action = "verified"
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(atlas)
                action = "extracted"
            print(f"[psp] {definition.resource_id}: {action} {definition.glyph_count:,} cells -> {output}")
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

