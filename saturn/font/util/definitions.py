"""Load the combined binary, atlas, and repack definition for each disc font."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

FONT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = FONT_ROOT.parents[1]
CONFIG_ROOT = FONT_ROOT / "config"
ATLAS_ROOT = FONT_ROOT / "atlas"
GENERATED_ROOT = FONT_ROOT / "generated"
ASSET_FONT_ROOT = PROJECT_ROOT / "assets" / "font"
SOURCE_ROOT = FONT_ROOT.parent / "rom" / "extracted"
DISC_IDS = ("game", "compendium")
_REFERENCE_SET_RE = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True)
class FontFormat:
    width: int
    height: int
    bpp: int
    row_stride: int
    glyph_stride: int


@dataclass(frozen=True)
class AtlasOptions:
    columns: int
    scale: int


@dataclass(frozen=True)
class GlyphOffset:
    characters: str
    offset_x: int = 0
    offset_y: int = 0


@dataclass(frozen=True)
class RenderOptions:
    size: int
    face_index: int = 0
    placement: str = "center"
    anchor: str = "mm"
    offset_x: int = 0
    offset_y: int = 0
    stroke_width: int = 0
    antialias: bool = True
    compose_from_glyphs: bool = False
    glyph_offsets: tuple[GlyphOffset, ...] = ()


@dataclass(frozen=True)
class AdvanceTable:
    storage_glyph: int
    code_limit: int


@dataclass(frozen=True)
class MetricsOptions:
    code_limit: int
    measurement: str = "source"
    space_advance: int | None = None


@dataclass(frozen=True)
class FontDefinition:
    disc: str
    file: str
    targets: tuple[str, ...]
    sha256: str
    format: FontFormat
    atlas: AtlasOptions
    glyphs: dict[int, str]
    replacements: dict[int, str]
    source_consumers: dict[str, tuple[str, ...]]
    reference_sets: dict[str, dict[str, int]]
    source_font: Path | None
    source_sha256: str | None
    render: RenderOptions | None
    advance_table: AdvanceTable | None
    metrics: MetricsOptions | None

    @property
    def stem(self) -> str:
        return Path(self.file).stem

    @property
    def source_path(self) -> Path:
        return SOURCE_ROOT / self.disc / self.file

    @property
    def target_paths(self) -> tuple[Path, ...]:
        return tuple(SOURCE_ROOT / self.disc / target for target in self.targets)

    @property
    def generated_path(self) -> Path:
        return GENERATED_ROOT / self.disc / self.file

    @property
    def metrics_path(self) -> Path:
        return GENERATED_ROOT / self.disc / f"{self.stem}_metrics.json"

    @property
    def original_atlas_path(self) -> Path:
        return ATLAS_ROOT / self.disc / f"{self.stem}_original.png"

    @property
    def modified_atlas_path(self) -> Path:
        return ATLAS_ROOT / self.disc / f"{self.stem}_modified.png"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"{label} SHA-256 is {actual}, expected {expected_sha256}")


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{context} must be an integer >= {minimum}")
    return value


def _sha256(value: Any, context: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{context} must be lowercase SHA-256 text")
    return value


def _index(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a nonnegative glyph index")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as error:
            raise ValueError(f"{context} must be a glyph index") from error
    else:
        raise ValueError(f"{context} must be a glyph index")
    if result < 0:
        raise ValueError(f"{context} cannot be negative")
    return result


def _atlas_mappings(groups: Any, context: str) -> tuple[dict[int, str], dict[int, str]]:
    if not isinstance(groups, dict):
        raise ValueError(f"{context} must be an object")
    glyphs: dict[int, str] = {}
    replacements: dict[int, str] = {}

    def add(index: int, original: str, replacement: str | None) -> None:
        if index in glyphs:
            raise ValueError(f"{context} maps glyph {index} more than once")
        glyphs[index] = original
        if replacement is not None:
            replacements[index] = replacement

    for group_name, entries in groups.items():
        group_context = f"{context}.{group_name}"
        if not isinstance(group_name, str) or not group_name:
            raise ValueError(f"{context} group names must be nonempty text")
        if not isinstance(entries, list):
            raise ValueError(f"{group_context} must be an array")
        for entry_number, entry in enumerate(entries):
            entry_context = f"{group_context}[{entry_number}]"
            if not isinstance(entry, dict) or not entry:
                raise ValueError(f"{entry_context} must be a nonempty object")
            replace = entry.get("replace", False)
            if not isinstance(replace, bool):
                raise ValueError(f"{entry_context}.replace must be boolean")

            if "start" in entry:
                values = entry.get("characters", entry.get("glyphs"))
                if isinstance(values, str):
                    characters = tuple(values)
                elif isinstance(values, list) and all(
                    isinstance(value, str) and value for value in values
                ):
                    characters = tuple(values)
                else:
                    raise ValueError(
                        f"{entry_context} needs characters or a glyph string array"
                    )
                start = _index(entry["start"], f"{entry_context}.start")
                for offset, character in enumerate(characters):
                    add(start + offset, character, character if replace else None)
                continue

            mappings = {key: value for key, value in entry.items() if key != "replace"}
            if not mappings:
                raise ValueError(f"{entry_context} has no glyph mappings")
            for raw_index, value in mappings.items():
                index = _index(raw_index, f"{entry_context}.{raw_index}")
                if isinstance(value, str) and value:
                    original = value
                    replacement = value if replace else None
                elif isinstance(value, dict) and len(value) == 1:
                    original, mapped = next(iter(value.items()))
                    if not isinstance(original, str) or not original:
                        raise ValueError(
                            f"{entry_context}.{raw_index} has an invalid original glyph"
                        )
                    if mapped is not None and not isinstance(mapped, str):
                        raise ValueError(
                            f"{entry_context}.{raw_index} has an invalid replacement"
                        )
                    replacement = mapped if replace and mapped else None
                else:
                    raise ValueError(f"{entry_context}.{raw_index} is not a glyph")
                add(index, original, replacement)
    return glyphs, replacements


def _reference_sets(
    value: Any,
    glyphs: dict[int, str],
    replacements: dict[int, str],
    context: str,
) -> dict[str, dict[str, int]]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    output: dict[str, dict[str, int]] = {}
    for name, raw_entries in value.items():
        if not isinstance(name, str) or _REFERENCE_SET_RE.fullmatch(name) is None:
            raise ValueError(f"{context} names must be lowercase identifiers")
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError(f"{context}.{name} must be a nonempty array")
        references: dict[str, int] = {}
        used_codes: set[int] = set()
        for entry_number, raw_entry in enumerate(raw_entries):
            entry_context = f"{context}.{name}[{entry_number}]"
            if (
                not isinstance(raw_entry, dict)
                or not {"start", "characters"} <= set(raw_entry)
                or not set(raw_entry) <= {"start", "characters", "aliases"}
            ):
                raise ValueError(
                    f"{entry_context} needs start, characters, and optional aliases"
                )
            start = _index(raw_entry["start"], f"{entry_context}.start")
            characters = raw_entry["characters"]
            if not isinstance(characters, str) or not characters:
                raise ValueError(f"{entry_context}.characters must be nonempty text")
            aliases = raw_entry.get("aliases", characters)
            if not isinstance(aliases, str) or len(aliases) != len(characters):
                raise ValueError(
                    f"{entry_context}.aliases must match characters in length"
                )
            for offset, (character, exposed) in enumerate(
                zip(characters, aliases, strict=True)
            ):
                code = start + offset
                if exposed in references:
                    raise ValueError(
                        f"{entry_context} repeats reference character {exposed!r}"
                    )
                if code in used_codes:
                    raise ValueError(f"{entry_context} repeats glyph {code}")
                if glyphs.get(code) != character:
                    raise ValueError(
                        f"{entry_context} expects glyph {code} to be {character!r}"
                    )
                if code in replacements:
                    raise ValueError(
                        f"{entry_context} selects replaced glyph {code}; reference "
                        "sets must preserve stock cells"
                    )
                references[exposed] = code
                used_codes.add(code)
        output[name] = references
    return output


def _source_consumers(
    value: Any,
    glyphs: dict[int, str],
    context: str,
) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    known = set(glyphs.values())
    output: dict[str, tuple[str, ...]] = {}
    for name, raw_glyphs in value.items():
        if not isinstance(name, str) or _REFERENCE_SET_RE.fullmatch(name) is None:
            raise ValueError(f"{context} names must be lowercase identifiers")
        if (
            not isinstance(raw_glyphs, list)
            or not raw_glyphs
            or not all(isinstance(glyph, str) and glyph for glyph in raw_glyphs)
        ):
            raise ValueError(f"{context}.{name} must be a nonempty glyph array")
        unknown = [glyph for glyph in raw_glyphs if glyph not in known]
        if unknown:
            raise ValueError(
                f"{context}.{name} references unknown source glyph {unknown[0]!r}"
            )
        output[name] = tuple(raw_glyphs)
    return output


def load_definition(path: Path, disc: str) -> FontDefinition:
    if disc not in DISC_IDS:
        raise ValueError(f"unsupported disc {disc!r}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    file = data.get("file")
    if not isinstance(file, str) or not file or Path(file).name != file:
        raise ValueError(f"{path}.file must be a filename")
    digest = _sha256(data.get("sha256"), f"{path}.sha256")

    targets_data = data.get("targets", [file])
    if (
        not isinstance(targets_data, list)
        or not targets_data
        or not all(isinstance(target, str) and target for target in targets_data)
    ):
        raise ValueError(f"{path}.targets must be a nonempty filename array")
    targets: list[str] = []
    for target in targets_data:
        relative = Path(target)
        if (
            relative.is_absolute()
            or relative.drive
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.suffix.casefold() != ".fon"
        ):
            raise ValueError(f"{path}.targets contains an unsafe path: {target}")
        normalized = relative.as_posix()
        if normalized.casefold() in {item.casefold() for item in targets}:
            raise ValueError(f"{path}.targets contains {target} more than once")
        targets.append(normalized)
    if targets[0].casefold() != file.casefold():
        raise ValueError(f"{path}.targets must begin with {file}")

    format_data = data.get("format")
    atlas_data = data.get("atlas")
    repack_data = data.get("repack")
    if not isinstance(format_data, dict) or not isinstance(atlas_data, dict):
        raise ValueError(f"{path} needs format and atlas objects")
    if not isinstance(repack_data, dict):
        raise ValueError(f"{path}.repack must be an object")

    font_format = FontFormat(
        width=_integer(format_data.get("width"), f"{path}.format.width", minimum=1),
        height=_integer(format_data.get("height"), f"{path}.format.height", minimum=1),
        bpp=_integer(format_data.get("bpp"), f"{path}.format.bpp", minimum=1),
        row_stride=_integer(
            format_data.get("row_stride"),
            f"{path}.format.row_stride",
            minimum=1,
        ),
        glyph_stride=_integer(
            format_data.get("glyph_stride"),
            f"{path}.format.glyph_stride",
            minimum=1,
        ),
    )
    if font_format.bpp not in {1, 2, 4}:
        raise ValueError(f"{path}.format.bpp must be 1, 2, or 4")
    if font_format.row_stride * 8 < font_format.width * font_format.bpp:
        raise ValueError(f"{path}.format.row_stride cannot hold one row")
    if font_format.glyph_stride < font_format.row_stride * font_format.height:
        raise ValueError(f"{path}.format.glyph_stride cannot hold one glyph")

    atlas = AtlasOptions(
        columns=_integer(atlas_data.get("columns"), f"{path}.atlas.columns", minimum=1),
        scale=_integer(atlas_data.get("scale"), f"{path}.atlas.scale", minimum=1),
    )
    glyphs, replacements = _atlas_mappings(
        atlas_data.get("groups"), f"{path}.atlas.groups"
    )
    source_consumers = _source_consumers(
        data.get("source_consumers"),
        glyphs,
        f"{path}.source_consumers",
    )
    reference_sets = _reference_sets(
        data.get("reference_sets", {}),
        glyphs,
        replacements,
        f"{path}.reference_sets",
    )

    source_font = None
    source_digest = None
    render = None
    if "source" in repack_data:
        source = repack_data.get("source")
        source_digest = _sha256(
            repack_data.get("source_sha256"), f"{path}.repack.source_sha256"
        )
        render_data = repack_data.get("render")
        if not isinstance(source, str) or not source:
            raise ValueError(f"{path}.repack.source must be nonempty text")
        source_font = (ASSET_FONT_ROOT / source).resolve()
        if not source_font.is_relative_to(ASSET_FONT_ROOT.resolve()):
            raise ValueError(f"{path}.repack.source escapes assets/font")
        if not isinstance(render_data, dict):
            raise ValueError(f"{path}.repack.render must be an object")
        offsets = tuple(
            GlyphOffset(
                characters=offset["characters"],
                offset_x=offset.get("offset_x", 0),
                offset_y=offset.get("offset_y", 0),
            )
            for offset in render_data.get("glyph_offsets", ())
        )
        render = RenderOptions(
            size=_integer(
                render_data.get("size"), f"{path}.repack.render.size", minimum=1
            ),
            face_index=render_data.get("face_index", 0),
            placement=render_data.get("placement", "center"),
            anchor=render_data.get("anchor", "mm"),
            offset_x=render_data.get("offset_x", 0),
            offset_y=render_data.get("offset_y", 0),
            stroke_width=render_data.get("stroke_width", 0),
            antialias=render_data.get("antialias", True),
            compose_from_glyphs=render_data.get("compose_from_glyphs", False),
            glyph_offsets=offsets,
        )
        if not replacements:
            raise ValueError(f"{path} configures a source font but no replacements")

    advance_table = None
    if table := repack_data.get("advance_table"):
        advance_table = AdvanceTable(
            storage_glyph=_integer(
                table.get("storage_glyph"),
                f"{path}.repack.advance_table.storage_glyph",
            ),
            code_limit=_integer(
                table.get("code_limit"),
                f"{path}.repack.advance_table.code_limit",
                minimum=1,
            ),
        )

    metrics = None
    if metrics_data := repack_data.get("metrics"):
        measurement = metrics_data.get("measurement", "source")
        if measurement not in {"source", "ink"}:
            raise ValueError(f"{path}.repack.metrics.measurement is invalid")
        space_advance = metrics_data.get("space_advance")
        if space_advance is not None:
            space_advance = _integer(
                space_advance, f"{path}.repack.metrics.space_advance", minimum=1
            )
        metrics = MetricsOptions(
            code_limit=_integer(
                metrics_data.get("code_limit"),
                f"{path}.repack.metrics.code_limit",
                minimum=1,
            ),
            measurement=measurement,
            space_advance=space_advance,
        )

    return FontDefinition(
        disc=disc,
        file=file,
        targets=tuple(targets),
        sha256=digest,
        format=font_format,
        atlas=atlas,
        glyphs=glyphs,
        replacements=replacements,
        source_consumers=source_consumers,
        reference_sets=reference_sets,
        source_font=source_font,
        source_sha256=source_digest,
        render=render,
        advance_table=advance_table,
        metrics=metrics,
    )


def load_definitions() -> tuple[FontDefinition, ...]:
    definitions: list[FontDefinition] = []
    for disc in DISC_IDS:
        paths = sorted(
            (CONFIG_ROOT / disc).glob("*.json"), key=lambda path: path.name.casefold()
        )
        definitions.extend(load_definition(path, disc) for path in paths)
    if not definitions:
        raise ValueError(f"no font definitions found under {CONFIG_ROOT}")
    identities = [
        (definition.disc, definition.file.casefold()) for definition in definitions
    ]
    if len(identities) != len(set(identities)):
        raise ValueError(f"duplicate disc/font pair under {CONFIG_ROOT}")
    targets: dict[tuple[str, str], FontDefinition] = {}
    for definition in definitions:
        for target in definition.targets:
            key = (definition.disc, target.casefold())
            if key in targets:
                raise ValueError(
                    f"duplicate {definition.disc} font target {target!r} in "
                    f"{targets[key].file} and {definition.file}"
                )
            targets[key] = definition
    return tuple(definitions)


def select_definitions(
    discs: Sequence[str], names: Sequence[str]
) -> tuple[FontDefinition, ...]:
    requested_discs = tuple(discs) or ("all",)
    if "all" in requested_discs:
        if len(requested_discs) != 1:
            raise ValueError("'all' cannot be combined with individual discs")
        selected_discs = DISC_IDS
    else:
        unknown = [disc for disc in requested_discs if disc not in DISC_IDS]
        if unknown:
            raise ValueError(
                f"unknown disc(s): {', '.join(unknown)}; choose from "
                f"{', '.join(DISC_IDS)} or all"
            )
        if len(requested_discs) != len(set(requested_discs)):
            raise ValueError("the same disc was selected more than once")
        selected_discs = requested_discs

    definitions = tuple(
        definition
        for definition in load_definitions()
        if definition.disc in selected_discs
    )
    if not names:
        return definitions
    selected: list[FontDefinition] = []
    for name in names:
        key = name.casefold()
        matches = [
            definition
            for definition in definitions
            if key in {definition.file.casefold(), definition.stem.casefold()}
        ]
        if not matches:
            choices = ", ".join(
                f"{item.disc}:{item.file}" for item in definitions
            )
            raise ValueError(f"unknown font {name!r}; choose from {choices}")
        selected.extend(matches)
    identities = [(item.disc, item.file.casefold()) for item in selected]
    if len(identities) != len(set(identities)):
        raise ValueError("the same font was selected more than once")
    return tuple(selected)
