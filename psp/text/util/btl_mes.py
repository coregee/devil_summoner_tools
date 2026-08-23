"""Build the PSP battle-console message table from canonical authored assets."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from psp.archive.pack import PspPack
from psp.text.util.assets import ASSET_ROOT, load_asset_field


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "btl_mes.json"
_TOKEN = re.compile(r"\{(?:(OP|GLYPH):([0-9a-fA-F]{2})|([A-Z][A-Z0-9_]*))\}")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class Encoding:
    terminator: int
    max_encoded_cells: int
    glyphs: dict[str, int]
    named_controls: dict[str, int]
    verified_operations: frozenset[int]


@dataclass(frozen=True, slots=True)
class BtlMesConfig:
    iso_path: str
    source_size: int
    source_sha256: str
    member_count: int
    member_index: int
    member_offset: int
    member_size: int
    member_sha256: str
    record_count: int
    pointer_sentinel_offset: int
    pointer_sentinel: int
    source_body_offset: int
    output_body_offset: int
    font_member_index: int
    font_offset: int
    font_size: int
    font_sha256: str
    encoding: Encoding
    bindings: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class BtlMesRecord:
    index: int
    asset_identity: str | None
    reference: str
    translation: str

    @property
    def translated(self) -> bool:
        return bool(self.translation)


@dataclass(frozen=True, slots=True)
class BtlMesBuild:
    data: bytes
    member: bytes
    records: tuple[BtlMesRecord, ...]
    source_sha256: str
    output_sha256: str
    source_member_sha256: str
    output_member_sha256: str
    translated_record_count: int
    preserved_record_count: int
    body_offset: int
    body_size: int
    body_capacity: int
    free_bytes: int
    changed_member_indices: tuple[int, ...]
    changed_byte_count: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{context} must be an integer >= {minimum}")
    return value


def _hex(value: object, context: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"{context} must be 0x-prefixed hexadecimal text")
    try:
        result = int(value, 16)
    except ValueError as error:
        raise ValueError(f"{context} is not hexadecimal") from error
    if result < 0:
        raise ValueError(f"{context} cannot be negative")
    return result


def _digest(value: object, context: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _encoding(document: object, context: str) -> Encoding:
    raw = _object(document, context)
    if set(raw) != {
        "terminator",
        "max_encoded_cells",
        "ranges",
        "glyphs",
        "named_controls",
        "verified_operations",
    }:
        raise ValueError(f"{context}: encoding fields changed")
    terminator = _hex(raw["terminator"], f"{context}.terminator")
    maximum = _integer(
        raw["max_encoded_cells"], f"{context}.max_encoded_cells", minimum=1
    )
    glyphs: dict[str, int] = {}

    def add(character: str, code: int, row_context: str) -> None:
        if len(character) != 1 or character in glyphs:
            raise ValueError(f"{row_context}: duplicate or invalid character")
        if not 0 <= code < terminator:
            raise ValueError(f"{row_context}: glyph code is outside the glyph range")
        glyphs[character] = code

    ranges = raw["ranges"]
    if not isinstance(ranges, list) or not ranges:
        raise ValueError(f"{context}.ranges must be a nonempty array")
    for index, value in enumerate(ranges):
        row_context = f"{context}.ranges[{index}]"
        row = _object(value, row_context)
        if set(row) != {"start", "characters"}:
            raise ValueError(f"{row_context}: fields changed")
        start = _hex(row["start"], f"{row_context}.start")
        characters = row["characters"]
        if not isinstance(characters, str) or not characters:
            raise ValueError(f"{row_context}.characters must be nonempty text")
        for offset, character in enumerate(characters):
            add(character, start + offset, row_context)

    rows = raw["glyphs"]
    if not isinstance(rows, list):
        raise ValueError(f"{context}.glyphs must be an array")
    for index, value in enumerate(rows):
        row_context = f"{context}.glyphs[{index}]"
        row = _object(value, row_context)
        if set(row) != {"code", "characters"}:
            raise ValueError(f"{row_context}: fields changed")
        code = _hex(row["code"], f"{row_context}.code")
        characters = row["characters"]
        if not isinstance(characters, str) or not characters:
            raise ValueError(f"{row_context}.characters must be nonempty text")
        for character in characters:
            add(character, code, row_context)

    raw_controls = _object(raw["named_controls"], f"{context}.named_controls")
    named_controls = {
        name: _hex(value, f"{context}.named_controls.{name}")
        for name, value in raw_controls.items()
        if isinstance(name, str) and name
    }
    if len(named_controls) != len(raw_controls) or any(
        value < terminator for value in named_controls.values()
    ):
        raise ValueError(f"{context}.named_controls contains an invalid control")
    operations = raw["verified_operations"]
    if not isinstance(operations, list):
        raise ValueError(f"{context}.verified_operations must be an array")
    verified_operations = frozenset(
        _hex(value, f"{context}.verified_operations") for value in operations
    )
    if len(verified_operations) != len(operations) or any(
        value < terminator for value in verified_operations
    ):
        raise ValueError(f"{context}.verified_operations contains an invalid byte")
    if set(glyphs.values()) != set(range(72)) - {11}:
        raise ValueError(f"{context}: FNT8X12 glyph coverage changed")
    return Encoding(
        terminator,
        maximum,
        glyphs,
        named_controls,
        verified_operations,
    )


def load_config(path: Path = CONFIG_PATH) -> BtlMesConfig:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid PSP BTL_MES configuration: {path}") from error
    root = _object(document, str(path))
    if set(root) != {
        "version",
        "surface",
        "source",
        "member",
        "font",
        "encoding",
        "bindings",
    } or root.get("version") != 1 or root.get("surface") != "battle_console.text":
        raise ValueError(f"{path}: unsupported PSP BTL_MES configuration")

    source = _object(root["source"], f"{path}.source")
    member = _object(root["member"], f"{path}.member")
    font = _object(root["font"], f"{path}.font")
    if set(source) != {"iso_path", "size", "sha256", "member_count"}:
        raise ValueError(f"{path}: BTL_MES source fields changed")
    if set(member) != {
        "index",
        "offset",
        "size",
        "sha256",
        "record_count",
        "pointer_sentinel_offset",
        "pointer_sentinel",
        "source_body_offset",
        "output_body_offset",
    }:
        raise ValueError(f"{path}: BTL_MES member fields changed")
    if set(font) != {"member_index", "offset", "size", "sha256"}:
        raise ValueError(f"{path}: BTL_MES font fields changed")
    iso_path = source["iso_path"]
    relative = PurePosixPath(iso_path) if isinstance(iso_path, str) else None
    if (
        relative is None
        or relative.is_absolute()
        or "\\" in iso_path
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"{path}: invalid BTL_MES ISO path")

    bindings = root["bindings"]
    if not isinstance(bindings, list) or any(
        value is not None and (not isinstance(value, str) or not value)
        for value in bindings
    ):
        raise ValueError(f"{path}: BTL_MES bindings must be text or null")
    config = BtlMesConfig(
        iso_path,
        _integer(source["size"], f"{path}.source.size", minimum=1),
        _digest(source["sha256"], f"{path}.source.sha256"),
        _integer(source["member_count"], f"{path}.source.member_count", minimum=1),
        _integer(member["index"], f"{path}.member.index"),
        _integer(member["offset"], f"{path}.member.offset"),
        _integer(member["size"], f"{path}.member.size", minimum=1),
        _digest(member["sha256"], f"{path}.member.sha256"),
        _integer(member["record_count"], f"{path}.member.record_count", minimum=1),
        _integer(
            member["pointer_sentinel_offset"],
            f"{path}.member.pointer_sentinel_offset",
        ),
        _hex(member["pointer_sentinel"], f"{path}.member.pointer_sentinel"),
        _integer(
            member["source_body_offset"], f"{path}.member.source_body_offset"
        ),
        _integer(
            member["output_body_offset"], f"{path}.member.output_body_offset"
        ),
        _integer(font["member_index"], f"{path}.font.member_index"),
        _integer(font["offset"], f"{path}.font.offset"),
        _integer(font["size"], f"{path}.font.size", minimum=1),
        _digest(font["sha256"], f"{path}.font.sha256"),
        _encoding(root["encoding"], f"{path}.encoding"),
        tuple(bindings),
    )
    if (
        config.source_size != 248_592
        or config.member_count != 32
        or (config.member_index, config.member_offset, config.member_size)
        != (18, 0x2C0A0, 5_082)
        or config.record_count != 358
        or config.pointer_sentinel_offset != config.record_count * 2
        or config.pointer_sentinel != 0xFFFF
        or config.source_body_offset != 0x800
        or config.output_body_offset != 0x400
        or (config.font_member_index, config.font_offset, config.font_size)
        != (15, 0x2A4D0, 864)
        or len(config.bindings) != config.record_count
    ):
        raise ValueError(f"{path}: PSP BTL_MES physical contract changed")
    return config


def asset_paths(
    config: BtlMesConfig | None = None,
    *,
    asset_root: Path = ASSET_ROOT,
) -> tuple[Path, ...]:
    plan = load_config() if config is None else config
    paths = {
        asset_root / Path(*PurePosixPath(identity.split("#", 1)[0]).parts)
        for identity in plan.bindings
        if identity is not None
    }
    return tuple(sorted(paths))


def load_records(
    config: BtlMesConfig | None = None,
    *,
    asset_root: Path = ASSET_ROOT,
) -> tuple[BtlMesRecord, ...]:
    plan = load_config() if config is None else config
    records = []
    for index, identity in enumerate(plan.bindings):
        if identity is None:
            reference = translation = ""
        else:
            reference, translation = load_asset_field(
                identity,
                asset_root=asset_root,
            )
            if bool(reference) != bool(translation):
                raise ValueError(
                    f"PSP BTL_MES slot {index} has incomplete authored text"
                )
            if translation:
                try:
                    _encode_message(translation, plan.encoding)
                except ValueError as error:
                    raise ValueError(f"PSP BTL_MES slot {index}: {error}") from error
        records.append(BtlMesRecord(index, identity, reference, translation))
    return tuple(records)


def _encode_message(text: str, encoding: Encoding) -> bytes:
    if not isinstance(text, str):
        raise TypeError("PSP BTL_MES text must be text")
    if not text:
        raise ValueError("PSP BTL_MES text cannot be empty")
    output = bytearray()
    position = 0
    while position < len(text):
        token = _TOKEN.match(text, position)
        if token is not None:
            kind, raw_value, name = token.groups()
            if name is not None:
                try:
                    value = encoding.named_controls[name]
                except KeyError as error:
                    raise ValueError(
                        f"BTL_MES named control {name!r} is not verified"
                    ) from error
            else:
                assert kind is not None and raw_value is not None
                value = int(raw_value, 16)
                if kind == "OP" and value < encoding.terminator:
                    raise ValueError(
                        f"BTL_MES operation {value:#04x} is in the glyph range"
                    )
                if kind == "OP" and value not in encoding.verified_operations:
                    raise ValueError(
                        f"BTL_MES operation {value:#04x} is not verified"
                    )
                if kind == "GLYPH" and value >= encoding.terminator:
                    raise ValueError(
                        f"BTL_MES glyph {value:#04x} is in the control range"
                    )
                if kind == "GLYPH" and value >= 72:
                    raise ValueError(
                        f"BTL_MES glyph {value:#04x} is outside FNT8X12"
                    )
            output.append(value)
            position = token.end()
            continue
        character = text[position]
        try:
            output.append(encoding.glyphs[character])
        except KeyError as error:
            raise ValueError(
                f"BTL_MES character {character!r} at {position} has no "
                "verified FNT8X12 glyph"
            ) from error
        position += 1
    if len(output) > encoding.max_encoded_cells:
        raise ValueError(
            f"BTL_MES text uses {len(output)}/"
            f"{encoding.max_encoded_cells} encoded cells"
        )
    output.append(encoding.terminator)
    return bytes(output)


def encode_message(
    text: str,
    config: BtlMesConfig | None = None,
) -> bytes:
    plan = load_config() if config is None else config
    return _encode_message(text, plan.encoding)


def _source_messages(source: bytes, config: BtlMesConfig) -> tuple[bytes, ...]:
    if len(source) != config.member_size or _sha256(source) != config.member_sha256:
        raise ValueError("PSP BTL_MES source member changed")
    pointers = struct.unpack_from(f">{config.record_count}H", source)
    sentinel = struct.unpack_from(">H", source, config.pointer_sentinel_offset)[0]
    if sentinel != config.pointer_sentinel:
        raise ValueError("PSP BTL_MES pointer sentinel changed")
    if any(
        source[
            config.pointer_sentinel_offset + 2 : config.source_body_offset
        ]
    ):
        raise ValueError("PSP BTL_MES unused pointer-table tail changed")
    if pointers[0] != 0 or any(
        left >= right for left, right in zip(pointers, pointers[1:])
    ):
        raise ValueError("PSP BTL_MES source pointers are not strictly increasing")
    body = source[config.source_body_offset :]
    messages = []
    for index, start in enumerate(pointers):
        end = pointers[index + 1] if index + 1 < len(pointers) else len(body)
        if not start < end <= len(body):
            raise ValueError(f"PSP BTL_MES source pointer {index} is out of range")
        message = body[start:end]
        if (
            message[-1] != config.encoding.terminator
            or config.encoding.terminator in message[:-1]
        ):
            raise ValueError(f"PSP BTL_MES source message {index} is malformed")
        messages.append(message)
    return tuple(messages)


def repack_member(
    source: bytes,
    records: tuple[BtlMesRecord, ...],
    config: BtlMesConfig | None = None,
) -> tuple[bytes, int]:
    plan = load_config() if config is None else config
    originals = _source_messages(source, plan)
    if len(records) != plan.record_count:
        raise ValueError("PSP BTL_MES authored record inventory changed")
    messages = []
    for index, (record, original) in enumerate(
        zip(records, originals, strict=True)
    ):
        if record.index != index:
            raise ValueError(f"PSP BTL_MES record {index} identity changed")
        if record.translation:
            message = _encode_message(record.translation, plan.encoding)
        else:
            if original != bytes((plan.encoding.terminator,)):
                raise ValueError(
                    f"PSP BTL_MES preserved slot {index} is not source-empty"
                )
            message = original
        messages.append(message)
    body = b"".join(messages)
    capacity = len(source) - plan.output_body_offset
    if len(body) > capacity:
        raise ValueError(f"PSP BTL_MES body uses {len(body)}/{capacity} bytes")
    output = bytearray(source)
    output[plan.output_body_offset :] = bytes(capacity)
    cursor = 0
    for index, message in enumerate(messages):
        struct.pack_into(">H", output, index * 2, cursor)
        cursor += len(message)
    struct.pack_into(
        ">H",
        output,
        plan.pointer_sentinel_offset,
        plan.pointer_sentinel,
    )
    output[plan.output_body_offset : plan.output_body_offset + len(body)] = body
    rebuilt = bytes(output)
    if len(rebuilt) != len(source):
        raise ValueError("PSP BTL_MES rebuild changed member size")
    rebuilt_pointers = struct.unpack_from(f">{plan.record_count}H", rebuilt)
    expected_offsets = []
    cursor = 0
    for message in messages:
        expected_offsets.append(cursor)
        cursor += len(message)
    if rebuilt_pointers != tuple(expected_offsets):
        raise ValueError("PSP BTL_MES rebuilt pointers are inconsistent")
    if (
        rebuilt[plan.output_body_offset : plan.output_body_offset + len(body)]
        != body
        or any(rebuilt[plan.output_body_offset + len(body) :])
    ):
        raise ValueError("PSP BTL_MES rebuilt body is inconsistent")
    return rebuilt, len(body)


def build_btl_mes(
    source: bytes,
    *,
    config_path: Path = CONFIG_PATH,
    asset_root: Path = ASSET_ROOT,
) -> BtlMesBuild:
    if not isinstance(source, bytes):
        raise TypeError("PSP regdata source must be bytes")
    config = load_config(config_path)
    if len(source) != config.source_size or _sha256(source) != config.source_sha256:
        raise ValueError("PSP BTL_MES regdata source changed")
    archive = PspPack.parse(source)
    if len(archive.members) != config.member_count or archive.rebuild() != source:
        raise ValueError("PSP BTL_MES source pack changed")
    font = archive.members[config.font_member_index]
    if (
        font.offset != config.font_offset
        or font.size != config.font_size
        or _sha256(font.data) != config.font_sha256
    ):
        raise ValueError("PSP BTL_MES FNT8X12 source member changed")
    member = archive.members[config.member_index]
    if (
        member.offset != config.member_offset
        or member.size != config.member_size
        or _sha256(member.data) != config.member_sha256
    ):
        raise ValueError("PSP BTL_MES source member geometry changed")
    records = load_records(config, asset_root=asset_root)
    rebuilt_member, body_size = repack_member(member.data, records, config)
    rebuilt = archive.rebuild({config.member_index: rebuilt_member})
    if len(rebuilt) != len(source):
        raise ValueError("PSP BTL_MES build changed regdata size")
    reparsed = PspPack.parse(rebuilt)
    changed_members = tuple(
        before.index
        for before, after in zip(archive.members, reparsed.members, strict=True)
        if before != after
    )
    if changed_members != (config.member_index,):
        raise ValueError("PSP BTL_MES build changed an unowned pack member")
    translated = sum(record.translated for record in records)
    capacity = config.member_size - config.output_body_offset
    return BtlMesBuild(
        data=rebuilt,
        member=rebuilt_member,
        records=records,
        source_sha256=_sha256(source),
        output_sha256=_sha256(rebuilt),
        source_member_sha256=_sha256(member.data),
        output_member_sha256=_sha256(rebuilt_member),
        translated_record_count=translated,
        preserved_record_count=len(records) - translated,
        body_offset=config.output_body_offset,
        body_size=body_size,
        body_capacity=capacity,
        free_bytes=capacity - body_size,
        changed_member_indices=changed_members,
        changed_byte_count=sum(
            before != after for before, after in zip(source, rebuilt, strict=True)
        ),
    )


__all__ = [
    "CONFIG_PATH",
    "BtlMesBuild",
    "BtlMesConfig",
    "BtlMesRecord",
    "Encoding",
    "asset_paths",
    "build_btl_mes",
    "encode_message",
    "load_config",
    "load_records",
    "repack_member",
]
