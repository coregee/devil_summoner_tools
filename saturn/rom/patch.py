"""Create or apply a BPS patch for the translated Saturn game disc.

Only the data track changes, so the patch covers Track 1 of the Rev. B game
disc. The audio track and CUE sheet are used unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import zlib
from pathlib import Path

from util.catalog import BUILD_ROOT, ROM_ROOT, load_catalog, validate_source

PATCH_ROOT = ROM_ROOT / "patch"
SECTOR = 2352
SOURCE_READ = 0
TARGET_READ = 1


def encode_number(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(0x80 | low)
            return bytes(out)
        out.append(low)
        value -= 1


def decode_number(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        byte = data[offset]
        offset += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, offset
        shift <<= 7
        value += shift


def action(command: int, length: int) -> bytes:
    return encode_number(((length - 1) << 2) | command)


def create_patch(source: bytes, target: bytes) -> bytes:
    """Build a linear BPS patch, compared one CD sector at a time."""
    if len(source) != len(target):
        raise ValueError("source and target tracks must be the same size")
    out = bytearray(b"BPS1")
    out += encode_number(len(source))
    out += encode_number(len(target))
    out += encode_number(0)

    run_start = 0
    run_changed = None
    for offset in range(0, len(target) + SECTOR, SECTOR):
        if offset < len(target):
            end = min(offset + SECTOR, len(target))
            changed = source[offset:end] != target[offset:end]
            if changed == run_changed:
                continue
        if run_changed is not None and offset > run_start:
            end = min(offset, len(target))
            if run_changed:
                out += action(TARGET_READ, end - run_start)
                out += target[run_start:end]
            else:
                out += action(SOURCE_READ, end - run_start)
        if offset < len(target):
            run_start = offset
            run_changed = changed

    out += zlib.crc32(source).to_bytes(4, "little")
    out += zlib.crc32(target).to_bytes(4, "little")
    out += zlib.crc32(out).to_bytes(4, "little")
    return bytes(out)


def apply_patch(patch: bytes, source: bytes) -> bytes:
    """Apply a BPS patch, checking all three CRCs."""
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS patch")
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise ValueError("patch file is damaged (patch CRC mismatch)")
    if zlib.crc32(source) != int.from_bytes(patch[-12:-8], "little"):
        raise ValueError(
            "source file does not match the patch; check that it is an "
            "unmodified Rev. B Track 1"
        )
    offset = 4
    source_size, offset = decode_number(patch, offset)
    target_size, offset = decode_number(patch, offset)
    metadata_size, offset = decode_number(patch, offset)
    offset += metadata_size
    if source_size != len(source):
        raise ValueError("source size does not match the patch")

    target = bytearray()
    source_rel = 0
    target_rel = 0
    end = len(patch) - 12
    while offset < end:
        data, offset = decode_number(patch, offset)
        command = data & 3
        length = (data >> 2) + 1
        if command == 0:
            start = len(target)
            target += source[start : start + length]
        elif command == 1:
            target += patch[offset : offset + length]
            offset += length
        elif command == 2:
            delta, offset = decode_number(patch, offset)
            source_rel += -(delta >> 1) if delta & 1 else delta >> 1
            target += source[source_rel : source_rel + length]
            source_rel += length
        else:
            delta, offset = decode_number(patch, offset)
            target_rel += -(delta >> 1) if delta & 1 else delta >> 1
            for _ in range(length):
                target.append(target[target_rel])
                target_rel += 1
    if len(target) != target_size:
        raise ValueError("patched output has the wrong size")
    if zlib.crc32(target) != int.from_bytes(patch[-8:-4], "little"):
        raise ValueError("patched output failed its CRC check")
    return bytes(target)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create(version: str) -> Path:
    spec = load_catalog()["game"]
    validate_source(spec)
    data_track, *other_tracks = spec.tracks
    original = spec.cue_path.parent
    build = BUILD_ROOT / spec.disc_id

    for name in [spec.cue, *(track.file for track in other_tracks)]:
        if (original / name).read_bytes() != (build / name).read_bytes():
            raise ValueError(f"{name} differs from the original; the patch covers Track 1 only")

    source = (original / data_track.file).read_bytes()
    target = (build / data_track.file).read_bytes()
    patch = create_patch(source, target)
    if apply_patch(patch, source) != target:
        raise ValueError("patch did not reproduce the build output")

    PATCH_ROOT.mkdir(exist_ok=True)
    path = PATCH_ROOT / f"devil_summoner_en_v{version}.bps"
    path.write_bytes(patch)
    print(f"wrote {path} ({len(patch):,} bytes)")
    print(f"source Track 1 CRC32 {zlib.crc32(source):08x}  SHA-256 {sha256(source)}")
    print(f"patched Track 1 CRC32 {zlib.crc32(target):08x}  SHA-256 {sha256(target)}")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("create", help="build a patch from saturn/rom/build/game")
    make.add_argument("--version", required=True, help="release version, e.g. 0.1")
    use = commands.add_parser("apply", help="apply a patch to a Track 1 BIN")
    use.add_argument("patch", type=Path)
    use.add_argument("source", type=Path, help="original Rev. B Track 1 BIN")
    use.add_argument("output", type=Path, help="where to write the patched Track 1 BIN")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.command == "create":
            create(args.version)
        else:
            output = apply_patch(args.patch.read_bytes(), args.source.read_bytes())
            args.output.write_bytes(output)
            print(f"wrote {args.output} (SHA-256 {sha256(output)})")
    except (OSError, ValueError) as error:
        raise SystemExit(f"error: {error}") from None


if __name__ == "__main__":
    main()
