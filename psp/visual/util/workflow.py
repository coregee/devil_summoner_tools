"""Compose shared title and maze art into fixed-size PSP pack members."""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import tempfile
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from PIL import Image

from psp.archive.pack import PspPack
from psp.formats.gim import Gim, INDEX4, INDEX8, pixel_sha256
from psp.rom.util.catalog import load_catalog, validate_source
from psp.rom.util.iso9660 import read_iso9660_file


VISUAL_ROOT = Path(__file__).resolve().parents[1]
PSP_ROOT = VISUAL_ROOT.parent
REPOSITORY_ROOT = PSP_ROOT.parent
IMAGE_ROOT = REPOSITORY_ROOT / "assets" / "image"
IMAGE_CATALOG_PATH = IMAGE_ROOT / "catalog.json"
TITLE_BINDINGS_PATH = VISUAL_ROOT / "bindings" / "title.json"
MAZE_BINDINGS_PATH = VISUAL_ROOT / "bindings" / "maze.json"
SAVE_ICON_BINDINGS_PATH = VISUAL_ROOT / "bindings" / "save_icon.json"
GENERATED_ROOT = VISUAL_ROOT / "generated" / "game"
MANIFEST_PATH = GENERATED_ROOT / "psp.visual.json"
TEXTURE_LOAD_BASE = 0x00250000


@dataclass(frozen=True, slots=True)
class SharedImage:
    id: str
    path: Path
    width: int
    height: int

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


@dataclass(frozen=True, slots=True)
class TextureSlot:
    index: int
    offset: int
    width: int
    height: int

    @property
    def size(self) -> int:
        return self.width * self.height * 2


@dataclass(frozen=True, slots=True)
class MemberOutput:
    key: str
    filename: str
    data: bytes
    source_sha256: str
    asset_ids: tuple[str, ...]
    targets: tuple[tuple[str, int | None], ...]
    report: dict[str, object]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, kind: str) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("version") != 1
        or document.get("kind") != kind
        or document.get("platform") not in {None, "psp"}
    ):
        raise ValueError(f"{path}: unsupported {kind}")
    return document


def _shared_images() -> dict[str, SharedImage]:
    document = _json(IMAGE_CATALOG_PATH, "image_catalog")
    rows = document.get("images")
    if not isinstance(rows, dict):
        raise ValueError(f"{IMAGE_CATALOG_PATH}: images must be an object")
    output = {}
    for asset_id, row in rows.items():
        if not isinstance(asset_id, str) or not isinstance(row, dict):
            raise ValueError(f"{IMAGE_CATALOG_PATH}: malformed image entry")
        relative = PurePosixPath(str(row.get("path", "")))
        width, height = row.get("width"), row.get("height")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix.casefold() != ".png"
            or type(width) is not int
            or width <= 0
            or type(height) is not int
            or height <= 0
        ):
            raise ValueError(f"{IMAGE_CATALOG_PATH}: invalid image {asset_id!r}")
        output[asset_id] = SharedImage(
            asset_id, IMAGE_ROOT.joinpath(*relative.parts), width, height
        )
    return output


def _image(asset: SharedImage) -> Image.Image:
    if not asset.path.is_file() or asset.path.is_symlink():
        raise ValueError(f"shared image is missing: {asset.path}")
    with Image.open(asset.path) as opened:
        opened.load()
        result = opened.copy()
    if result.size != asset.size:
        raise ValueError(f"{asset.id}: shared image dimensions changed")
    return result


def _black_matte_binary(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    source = rgba.tobytes()
    output = bytearray(len(source))
    for offset in range(0, len(source), 4):
        red, green, blue, alpha = source[offset : offset + 4]
        output[offset : offset + 4] = bytes(
            (
                (red * alpha + 127) // 255,
                (green * alpha + 127) // 255,
                (blue * alpha + 127) // 255,
                255 if alpha else 0,
            )
        )
    return Image.frombytes("RGBA", rgba.size, bytes(output))


def _effective_title(
    image: Image.Image, source: Image.Image, alpha_mode: str
) -> Image.Image:
    if alpha_mode == "preserve":
        return image.copy()
    if alpha_mode == "source_mask":
        output = image.convert("RGBA")
        output.putalpha(source.convert("RGBA").getchannel("A"))
        return output
    if alpha_mode == "black_matte_binary":
        return _black_matte_binary(image)
    raise ValueError(f"unsupported PSP title alpha mode: {alpha_mode}")


def _png_chunks(data: bytes) -> tuple[tuple[bytes, bytes], ...]:
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        raise ValueError("PNG signature is missing")
    chunks = []
    cursor = len(signature)
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("PNG chunk header is truncated")
        size = struct.unpack_from(">I", data, cursor)[0]
        end = cursor + 12 + size
        if end > len(data):
            raise ValueError("PNG chunk exceeds its file")
        kind = data[cursor + 4 : cursor + 8]
        payload = data[cursor + 8 : cursor + 8 + size]
        expected_crc = struct.unpack_from(">I", data, cursor + 8 + size)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError(f"PNG {kind!r} chunk CRC is invalid")
        chunks.append((kind, payload))
        cursor = end
        if kind == b"IEND":
            break
    if cursor != len(data) or not chunks or chunks[-1][0] != b"IEND":
        raise ValueError("PNG chunk boundaries are invalid")
    return tuple(chunks)


def _png_bytes(chunks: tuple[tuple[bytes, bytes], ...]) -> bytes:
    output = bytearray(b"\x89PNG\r\n\x1a\n")
    for kind, payload in chunks:
        output.extend(struct.pack(">I", len(payload)))
        output.extend(kind)
        output.extend(payload)
        output.extend(struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
    return bytes(output)


def _encode_png_same_size(image: Image.Image, source_data: bytes) -> bytes:
    source_chunks = _png_chunks(source_data)
    with Image.open(io.BytesIO(source_data)) as opened:
        source_size = opened.size
    if image.size != source_size:
        raise ValueError("PSP save icon dimensions changed")
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema() != (255, 255):
        raise ValueError("PSP save icon must remain fully opaque")
    generated = io.BytesIO()
    rgba.convert("RGB").save(generated, format="PNG", optimize=True, compress_level=9)
    generated_chunks = _png_chunks(generated.getvalue())
    preserved_types = {
        b"cHRM",
        b"gAMA",
        b"iCCP",
        b"iTXt",
        b"pHYs",
        b"sRGB",
        b"tEXt",
        b"tIME",
        b"zTXt",
    }
    already_present = {kind for kind, _payload in generated_chunks}
    preserved = tuple(
        (kind, payload)
        for kind, payload in source_chunks
        if kind in preserved_types and kind not in already_present
    )
    combined = []
    inserted = False
    for kind, payload in generated_chunks:
        if kind == b"IDAT" and not inserted:
            combined.extend(preserved)
            inserted = True
        combined.append((kind, payload))
    encoded = _png_bytes(tuple(combined))
    if len(encoded) > len(source_data):
        raise ValueError("encoded PSP save icon exceeds its fixed capacity")
    padding = len(source_data) - len(encoded)
    if padding:
        if padding < 12:
            raise ValueError("PSP save icon leaves too little room for PNG padding")
        padded = []
        for kind, payload in combined:
            if kind == b"IEND":
                padded.append((b"npAd", bytes(padding - 12)))
            padded.append((kind, payload))
        encoded = _png_bytes(tuple(padded))
    if len(encoded) != len(source_data):
        raise AssertionError("PSP save icon padding changed fixed size")
    with Image.open(io.BytesIO(encoded)) as checked:
        if pixel_sha256(checked) != pixel_sha256(image):
            raise ValueError("PSP save icon encoding changed authored pixels")
    return encoded


def _save_icon_output(
    source_path: Path, assets: dict[str, SharedImage]
) -> MemberOutput:
    config = _json(SAVE_ICON_BINDINGS_PATH, "psp_save_icon_bindings")
    asset_id = config.get("asset")
    contract = config.get("source")
    targets = config.get("targets")
    if asset_id not in assets or not isinstance(contract, dict) or not isinstance(
        targets, list
    ):
        raise ValueError(f"{SAVE_ICON_BINDINGS_PATH}: malformed bindings")
    payloads = []
    resolved_targets = []
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError(f"{SAVE_ICON_BINDINGS_PATH}: malformed target")
        iso_path = target.get("iso_path")
        member_index = target.get("member_index")
        if not isinstance(iso_path, str) or not (
            member_index is None or type(member_index) is int
        ):
            raise ValueError(f"{SAVE_ICON_BINDINGS_PATH}: invalid target")
        _extent, entry = read_iso9660_file(source_path, iso_path)
        if member_index is None:
            payload = entry
        else:
            pack = PspPack.parse(entry)
            try:
                payload = pack.members[member_index].data
            except IndexError:
                raise ValueError(f"{iso_path}: save-icon member is missing") from None
        if len(payload) != contract.get("size") or _sha256(payload) != contract.get(
            "sha256"
        ):
            raise ValueError(f"{iso_path}: save-icon source contract changed")
        with Image.open(io.BytesIO(payload)) as opened:
            actual = (opened.size, pixel_sha256(opened))
        expected = (
            (contract.get("width"), contract.get("height")),
            contract.get("pixel_sha256"),
        )
        if actual != expected:
            raise ValueError(f"{iso_path}: save-icon pixels changed")
        payloads.append(payload)
        resolved_targets.append((iso_path, member_index))
    if len({_sha256(payload) for payload in payloads}) != 1:
        raise ValueError("PSP save-icon consumers do not share one source payload")
    authored = _image(assets[asset_id])
    encoded = _encode_png_same_size(authored, payloads[0])
    return MemberOutput(
        key=f"save_icon:{asset_id}",
        filename="save_icon/title.png",
        data=encoded,
        source_sha256=_sha256(payloads[0]),
        asset_ids=(asset_id,),
        targets=tuple(resolved_targets),
        report={
            "authored_pixel_sha256": pixel_sha256(authored),
            "encoded_pixel_sha256": pixel_sha256(authored),
            "quantized": False,
            "lossy_pixel_count": 0,
        },
    )


def _title_outputs(
    source_path: Path, assets: dict[str, SharedImage]
) -> tuple[MemberOutput, ...]:
    config = _json(TITLE_BINDINGS_PATH, "psp_title_bindings")
    iso_path = config.get("iso_path")
    source_contract = config.get("source_pack")
    rows = config.get("replacements")
    if (
        not isinstance(iso_path, str)
        or not isinstance(source_contract, dict)
        or not isinstance(rows, list)
    ):
        raise ValueError(f"{TITLE_BINDINGS_PATH}: malformed title bindings")
    _extent, source_pack = read_iso9660_file(source_path, iso_path)
    if (
        len(source_pack) != source_contract.get("size")
        or _sha256(source_pack) != source_contract.get("sha256")
    ):
        raise ValueError(f"{iso_path}: source pack contract changed")
    pack = PspPack.parse(source_pack)
    if len(pack.members) != source_contract.get("member_count"):
        raise ValueError(f"{iso_path}: member count changed")

    outputs = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("source"), dict):
            raise ValueError(f"{TITLE_BINDINGS_PATH}: malformed replacement")
        asset_id = str(row.get("asset", ""))
        index = row.get("member_index")
        contract = row["source"]
        if asset_id not in assets or type(index) is not int or index in seen:
            raise ValueError(f"{TITLE_BINDINGS_PATH}: invalid title replacement")
        seen.add(index)
        try:
            member = pack.members[index].data
        except IndexError:
            raise ValueError(f"{iso_path}: title member {index} is missing") from None
        if len(member) != contract.get("size") or _sha256(member) != contract.get(
            "sha256"
        ):
            raise ValueError(f"{iso_path} member {index}: source changed")
        gim = Gim.parse(member)
        source_image = gim.decode()
        actual = (
            source_image.size,
            gim.image.format,
            gim.image.order,
            pixel_sha256(source_image),
        )
        expected = (
            (contract.get("width"), contract.get("height")),
            contract.get("format"),
            contract.get("order"),
            contract.get("pixel_sha256"),
        )
        if actual != expected or gim.size != len(member):
            raise ValueError(f"{iso_path} member {index}: GIM contract changed")
        authored = _image(assets[asset_id])
        effective = _effective_title(
            authored, source_image, str(row.get("alpha_mode", ""))
        )
        palette_mode = (
            "rebuild" if gim.image.format in {INDEX4, INDEX8} else "strict"
        )
        encoded = gim.encode_with_report(effective, palette_mode=palette_mode)
        if len(encoded.data) != len(member):
            raise AssertionError("PSP title GIM changed fixed member size")
        outputs.append(
            MemberOutput(
                key=f"title:{asset_id}",
                filename=f"title/{asset_id.removeprefix('title.')}.gim",
                data=encoded.data,
                source_sha256=_sha256(member),
                asset_ids=(asset_id,),
                targets=((iso_path, index),),
                report={
                    "authored_pixel_sha256": pixel_sha256(authored),
                    "encoded_pixel_sha256": encoded.report.encoded_pixel_sha256,
                    "quantized": encoded.report.quantized,
                    "lossy_pixel_count": encoded.report.lossy_pixel_count,
                },
            )
        )
    return tuple(outputs)


def _texture_slots(
    model: bytes, texture: bytes, context: str
) -> tuple[TextureSlot, ...]:
    if len(model) < 4:
        raise ValueError(f"{context}: MDL3D member is truncated")
    count = struct.unpack_from("<I", model)[0]
    table_size = count * 8
    if not count or count > 10_000 or len(model) < 0x20 + table_size:
        raise ValueError(f"{context}: invalid texture count")
    slots = []
    for index in range(count):
        row = index * 8
        declared, copies, address = struct.unpack_from(">HHI", texture, row)
        offset = address - TEXTURE_LOAD_BASE
        next_offset = (
            struct.unpack_from(">I", texture, row + 12)[0] - TEXTURE_LOAD_BASE
            if index + 1 < count
            else len(texture)
        )
        width, height = struct.unpack_from(">HH", model, 0x20 + row)
        if (
            declared != index
            or copies != 1
            or not width
            or not height
            or offset < table_size
            or next_offset - offset != width * height * 2
        ):
            raise ValueError(f"{context}: invalid texture slot {index}")
        slots.append(TextureSlot(index, offset, width, height))
    return tuple(slots)


def _flatten_black(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def _encode_rgb555(texture: bytearray, slot: TextureSlot, image: Image.Image) -> None:
    if image.size != (slot.width, slot.height):
        raise ValueError(f"maze texture {slot.index}: replacement dimensions changed")
    pixels = _flatten_black(image).tobytes()
    for index in range(slot.width * slot.height):
        pixel = index * 3
        offset = slot.offset + index * 2
        original = struct.unpack_from(">H", texture, offset)[0]
        red = (pixels[pixel] * 31 + 127) // 255
        green = (pixels[pixel + 1] * 31 + 127) // 255
        blue = (pixels[pixel + 2] * 31 + 127) // 255
        struct.pack_into(
            ">H", texture, offset, (original & 0x8000) | red | green << 5 | blue << 10
        )


def _pieces(
    image: Image.Image, slots: tuple[TextureSlot, ...]
) -> tuple[Image.Image, ...]:
    if len(slots) == 1:
        if image.size != (slots[0].width, slots[0].height):
            raise ValueError("maze replacement dimensions do not match its slot")
        return (image.copy(),)
    if (
        len(slots) != 2
        or slots[0].width != slots[1].width
        or slots[0].height != slots[1].height
        or image.size != (slots[0].width * 2, slots[0].height)
    ):
        raise ValueError("maze composite is not two equal horizontal slots")
    width, height = slots[0].width, slots[0].height
    return (
        image.crop((0, 0, width, height)),
        image.crop((width, 0, width * 2, height)),
    )


def _maze_outputs(
    source_path: Path, assets: dict[str, SharedImage]
) -> tuple[MemberOutput, ...]:
    config = _json(MAZE_BINDINGS_PATH, "psp_maze_bindings")
    archives = config.get("archives")
    replacements = config.get("replacements")
    model_member = config.get("model_member")
    texture_member = config.get("texture_member")
    if (
        not isinstance(archives, list)
        or not isinstance(replacements, list)
        or type(model_member) is not int
        or type(texture_member) is not int
    ):
        raise ValueError(f"{MAZE_BINDINGS_PATH}: malformed maze bindings")

    families = {}
    for row in archives:
        name, paths, source_hash = (
            row.get("archive"),
            row.get("psp_iso_paths"),
            row.get("sha256"),
        )
        if not isinstance(name, str) or not isinstance(paths, list) or not paths:
            raise ValueError(f"{MAZE_BINDINGS_PATH}: malformed archive")
        first_model = first_texture = None
        for iso_path in paths:
            _extent, source_pack = read_iso9660_file(source_path, iso_path)
            pack = PspPack.parse(source_pack)
            if max(model_member, texture_member) >= len(pack.members):
                raise ValueError(f"{iso_path}: maze members are missing")
            model = pack.members[model_member].data
            texture = pack.members[texture_member].data
            if _sha256(texture) != source_hash:
                raise ValueError(f"{iso_path}: maze texture source changed")
            if first_model is None:
                first_model, first_texture = model, texture
            elif model != first_model or texture != first_texture:
                raise ValueError(f"{name}: duplicate maze members differ")
        assert first_model is not None and first_texture is not None
        families[name] = {
            "paths": tuple(paths),
            "source": first_texture,
            "edited": bytearray(first_texture),
            "slots": _texture_slots(first_model, first_texture, name),
            "assets": set(),
        }

    logical_count = physical_count = 0
    claimed: set[tuple[str, int]] = set()
    for row in replacements:
        asset_id, targets = row.get("asset"), row.get("targets")
        if asset_id not in assets or not isinstance(targets, list) or not targets:
            raise ValueError(f"{MAZE_BINDINGS_PATH}: malformed asset binding")
        authored = _image(assets[asset_id])
        for target in targets:
            archive, indices = target.get("archive"), target.get("texture_indices")
            if archive not in families or not isinstance(indices, list) or not indices:
                raise ValueError(f"{asset_id}: invalid maze target")
            family = families[archive]
            slots = tuple(family["slots"][index] for index in indices)
            pieces = _pieces(authored, slots)
            for index, slot, piece in zip(indices, slots, pieces, strict=True):
                identity = (archive, index)
                if identity in claimed:
                    raise ValueError(f"duplicate maze target: {archive}/{index}")
                claimed.add(identity)
                _encode_rgb555(family["edited"], slot, piece)
            family["assets"].add(asset_id)
            logical_count += len(indices)
            physical_count += len(indices) * len(family["paths"])

    expected = (
        config.get("asset_binding_count"),
        config.get("logical_target_count"),
        config.get("physical_binding_count"),
    )
    actual = (len(replacements), logical_count, physical_count)
    if actual != expected:
        raise ValueError(f"PSP maze fan-out is {actual}; expected {expected}")

    outputs = []
    for name, family in sorted(families.items()):
        if not family["assets"]:
            continue
        source = family["source"]
        data = bytes(family["edited"])
        if len(data) != len(source) or data == source:
            raise ValueError(f"{name}: maze replacement is empty or changed size")
        outputs.append(
            MemberOutput(
                key=f"maze:{name}",
                filename=f"maze/{name}.tex3d.bin",
                data=data,
                source_sha256=_sha256(source),
                asset_ids=tuple(sorted(family["assets"])),
                targets=tuple((path, texture_member) for path in family["paths"]),
                report={"logical_asset_count": len(family["assets"])},
            )
        )
    return tuple(outputs)


def compose() -> tuple[dict[Path, bytes], dict[str, object]]:
    disc = load_catalog()["game"]
    source_path = validate_source(disc, verify_hash=True)
    assets = _shared_images()
    outputs = (
        *_title_outputs(source_path, assets),
        _save_icon_output(source_path, assets),
        *_maze_outputs(source_path, assets),
    )
    files = {GENERATED_ROOT / row.filename: row.data for row in outputs}
    document = {
        "version": 1,
        "surface": "psp.visual",
        "source": {
            "filename": disc.source_filename,
            "size": disc.source_size,
            "sha256": disc.source_sha256,
        },
        "inputs": {
            path.relative_to(REPOSITORY_ROOT).as_posix(): _sha256(path.read_bytes())
            for path in (
                IMAGE_CATALOG_PATH,
                TITLE_BINDINGS_PATH,
                MAZE_BINDINGS_PATH,
                SAVE_ICON_BINDINGS_PATH,
                *(assets[asset].path for row in outputs for asset in row.asset_ids),
            )
        },
        "outputs": {
            row.key: {
                "filename": row.filename,
                "size": len(row.data),
                "sha256": _sha256(row.data),
                "source_sha256": row.source_sha256,
                "assets": list(row.asset_ids),
                "targets": [
                    {"iso_path": path, "member_index": index}
                    for path, index in row.targets
                ],
                "report": row.report,
            }
            for row in outputs
        },
        "summary": {
            "shared_assets": len({asset for row in outputs for asset in row.asset_ids}),
            "encoded_members": len(outputs),
            "physical_bindings": sum(len(row.targets) for row in outputs),
        },
    }
    manifest = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    files[MANIFEST_PATH] = manifest
    return files, document


def _publish(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def repack(*, check: bool) -> dict[str, object]:
    files, document = compose()
    for path, data in files.items():
        if check:
            if not path.is_file() or path.read_bytes() != data:
                raise ValueError(f"PSP visual output is missing or stale: {path}")
        else:
            _publish(path, data)
    return document
