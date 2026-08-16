"""Build translated Saturn text outputs from shared authored assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path, PurePosixPath


TEXT_ROOT = Path(__file__).resolve().parent
SATURN_ROOT = TEXT_ROOT.parent
if str(SATURN_ROOT) not in sys.path:
    sys.path.append(str(SATURN_ROOT))

from rom.util.catalog import load_catalog, validate_source  # noqa: E402
from rom.util.workflows import read_source_files  # noqa: E402
from util.event_codec import load_event_dictionary  # noqa: E402
from util.battle_negotiation import (  # noqa: E402
    NEGOTIATION_EVE_SOURCES,
    compile_combat_fixed_text,
    compile_negotiation_banks,
    load_negotiation_translations,
)
from util.battle_ui import (  # noqa: E402
    compile_btl_help,
    compile_btl_mes,
    compile_catalog,
    compile_indexed_words,
)
from util.event_repack import (  # noqa: E402
    GENERAL_EVENT_SOURCES,
    SHOP_EVENT_SOURCES,
    FontMetrics,
    compile_event_banks,
    compile_event_sources,
    load_event_source_translations,
    load_event_translations,
)
from util.sources import load_manifest, manifest_path  # noqa: E402


GENERATED_ROOT = TEXT_ROOT / "generated" / "game"
CODEC_PATH = TEXT_ROOT / "config" / "event_codec.json"
FONT16_METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT16_metrics.json"
FONT12_METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT12_metrics.json"
FONT8_METRICS_PATH = SATURN_ROOT / "font" / "generated" / "game" / "FONT8_metrics.json"
EVENT_BUILD_PATH = GENERATED_ROOT / "event_build.json"
NEGOTIATION_BUILD_PATH = GENERATED_ROOT / "battle_negotiation_build.json"
SHOPSMP_BUILD_PATH = GENERATED_ROOT / "shopsmp_build.json"
BATTLE_UI_BUILD_PATH = GENERATED_ROOT / "battle_ui_build.json"


def _stock_files(paths: tuple[PurePosixPath, ...]) -> dict[PurePosixPath, bytes]:
    catalog = load_catalog()
    validated = validate_source(catalog["game"])
    source = read_source_files(validated, (path.as_posix() for path in paths))
    return {path: source[path.as_posix()] for path in paths}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except FileNotFoundError as error:
        raise ValueError(f"required generated input is missing: {path}") from error


def _atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def build_event_outputs() -> dict[Path, bytes]:
    manifest = load_manifest(manifest_path("game"))
    selected = {
        source.name: source
        for source in manifest.sources
        if source.name in GENERAL_EVENT_SOURCES
    }
    if set(selected) != set(GENERAL_EVENT_SOURCES):
        raise ValueError("game manifest does not declare every general EVENT bank")
    paths = tuple(
        manifest.files[source.container["file"]].path
        for source in selected.values()
    )
    stock = _stock_files(paths)
    translations = load_event_translations()
    metrics = FontMetrics.load(FONT16_METRICS_PATH)
    dictionary = load_event_dictionary(CODEC_PATH)
    banks = compile_event_banks(
        manifest, stock, translations, metrics, dictionary
    )

    output: dict[Path, bytes] = {
        GENERATED_ROOT.joinpath(*bank.path.parts): bank.data for bank in banks
    }
    manifest_document = {
        "version": 1,
        "surface": "event.dialogue",
        "codec_sha256": _sha256_path(CODEC_PATH),
        "runtime_table_sha256": _sha256_bytes(dictionary.runtime_table()),
        "font16_metrics_sha256": _sha256_path(FONT16_METRICS_PATH),
        "records": len(translations),
        "outputs": {
            bank.path.as_posix(): {
                "sha256": _sha256_bytes(bank.data),
                "messages": bank.messages,
                "pages": bank.pages,
                "body_bytes": bank.body_bytes,
            }
            for bank in banks
        },
    }
    output[EVENT_BUILD_PATH] = (
        json.dumps(manifest_document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return output


def build_negotiation_outputs() -> dict[Path, bytes]:
    manifest = load_manifest(manifest_path("game"))
    selected = {
        source.name: source
        for source in manifest.sources
        if source.name in NEGOTIATION_EVE_SOURCES
    }
    if set(selected) != set(NEGOTIATION_EVE_SOURCES):
        raise ValueError("game manifest does not declare every negotiation EVE bank")
    paths = tuple(
        manifest.files[source.container["file"]].path
        for source in selected.values()
    ) + (PurePosixPath("COMBAT.BIN"), PurePosixPath("ITEMNAME.DAT"))
    stock = _stock_files(paths)
    translations = load_negotiation_translations()
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    dictionary = load_event_dictionary(CODEC_PATH)
    banks = compile_negotiation_banks(
        manifest, stock, translations, font16, dictionary
    )
    combat = compile_combat_fixed_text(stock[PurePosixPath("COMBAT.BIN")], font16)
    itemname_build = compile_catalog(
        stock[PurePosixPath("ITEMNAME.DAT")],
        source="itemname",
        count=287,
        font8=font8,
        font16=font16,
    )
    itemname = itemname_build.data

    output: dict[Path, bytes] = {
        GENERATED_ROOT.joinpath(*bank.path.parts): bank.data for bank in banks
    }
    output[GENERATED_ROOT / "COMBAT.BIN"] = combat
    output[GENERATED_ROOT / "ITEMNAME.DAT"] = itemname
    output_rows = {
        bank.path.as_posix(): {
            "sha256": _sha256_bytes(bank.data),
            "messages": bank.messages,
            "pages": bank.pages,
            "body_bytes": bank.body_bytes,
        }
        for bank in banks
    }
    output_rows["COMBAT.BIN"] = {"sha256": _sha256_bytes(combat)}
    output_rows["ITEMNAME.DAT"] = {"sha256": _sha256_bytes(itemname)}
    document = {
        "version": 1,
        "surface": "battle.negotiation",
        "codec_sha256": _sha256_path(CODEC_PATH),
        "runtime_table_sha256": _sha256_bytes(dictionary.runtime_table()),
        "font16_metrics_sha256": _sha256_path(FONT16_METRICS_PATH),
        "font8_metrics_sha256": _sha256_path(FONT8_METRICS_PATH),
        "records": {
            "dialogue_pages": len(translations),
            "fixed_messages": 117,
            "item_names": itemname_build.translated_names,
            "item_descriptions": 287,
            "translated_item_descriptions": itemname_build.translated_descriptions,
            "total": len(translations) + 117 + 574,
        },
        "outputs": output_rows,
    }
    output[NEGOTIATION_BUILD_PATH] = (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return output


def build_battle_ui_outputs() -> dict[Path, bytes]:
    paths = tuple(
        PurePosixPath(name)
        for name in (
            "BTL_HELP.DAT",
            "BTL_MES.MD8",
            "BTL_SRF.MDT",
            "BUTU_SRF.MDT",
            "ITEMNAME.DAT",
            "MAGNAME.DAT",
        )
    )
    stock = _stock_files(paths)
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font8 = FontMetrics.load(FONT8_METRICS_PATH)
    dictionary = load_event_dictionary(CODEC_PATH)
    btl_help = compile_btl_help(stock[PurePosixPath("BTL_HELP.DAT")], font16)
    btl_mes = compile_btl_mes(stock[PurePosixPath("BTL_MES.MD8")])
    btl_srf = compile_indexed_words(
        stock[PurePosixPath("BTL_SRF.MDT")],
        prefix="game.btl_srf.",
        count=363,
        sentinel_offset=0x2D6,
        metrics=font16,
        dictionary=dictionary,
        wrap_width=176,
        wrap_lines=2,
    )
    butu_srf = compile_indexed_words(
        stock[PurePosixPath("BUTU_SRF.MDT")],
        prefix="game.butu_srf.",
        count=144,
        sentinel_offset=0x120,
        metrics=font16,
        dictionary=dictionary,
        wrap_width=None,
        wrap_lines=None,
    )
    itemname = compile_catalog(
        stock[PurePosixPath("ITEMNAME.DAT")],
        source="itemname",
        count=287,
        font8=font8,
        font16=font16,
    )
    magname = compile_catalog(
        stock[PurePosixPath("MAGNAME.DAT")],
        source="magname",
        count=255,
        font8=font8,
        font16=font16,
    )
    builds = {
        "BTL_HELP.DAT": btl_help,
        "BTL_MES.MD8": btl_mes,
        "BTL_SRF.MDT": btl_srf,
        "BUTU_SRF.MDT": butu_srf,
        "ITEMNAME.DAT": itemname,
        "MAGNAME.DAT": magname,
    }
    outputs = {
        GENERATED_ROOT / name: build.data for name, build in builds.items()
    }
    output_rows: dict[str, object] = {}
    for name, build in builds.items():
        row: dict[str, object] = {
            "sha256": _sha256_bytes(build.data),
            "records": build.records,
        }
        if hasattr(build, "translated_names"):
            row.update(
                {
                    "translated_names": build.translated_names,
                    "translated_descriptions": build.translated_descriptions,
                    "longest_name_bytes": build.longest_name_bytes,
                    "longest_name_pixels": build.longest_name_pixels,
                    "longest_description_words": build.longest_description_words,
                    "free_name_bytes": build.free_name_bytes,
                }
            )
        elif name == "BTL_HELP.DAT":
            row.update(
                {
                    "translated": build.translated,
                    "longest_record_words": build.body_size // 2,
                    "capacity_words": build.body_capacity // 2,
                }
            )
        else:
            row.update(
                {
                    "translated": build.translated,
                    "body_bytes": build.body_size,
                    "capacity_bytes": build.body_capacity,
                }
            )
        output_rows[name] = row
    document = {
        "version": 1,
        "surface": "battle.ui",
        "codec_sha256": _sha256_path(CODEC_PATH),
        "runtime_table_sha256": _sha256_bytes(dictionary.runtime_table()),
        "font16_metrics_sha256": _sha256_path(FONT16_METRICS_PATH),
        "font8_metrics_sha256": _sha256_path(FONT8_METRICS_PATH),
        "outputs": output_rows,
    }
    outputs[BATTLE_UI_BUILD_PATH] = (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return outputs


def build_shopsmp_outputs() -> dict[Path, bytes]:
    manifest = load_manifest(manifest_path("game"))
    sources = {source.name: source for source in manifest.sources}
    try:
        source = sources[SHOP_EVENT_SOURCES[0]]
    except KeyError as error:
        raise ValueError("game manifest does not declare SHOPSMP.EVE") from error
    path = manifest.files[source.container["file"]].path
    stock = _stock_files((path,))
    translations = load_event_source_translations(SHOP_EVENT_SOURCES)
    font16 = FontMetrics.load(FONT16_METRICS_PATH)
    font12 = FontMetrics.load(FONT12_METRICS_PATH)
    dictionary = load_event_dictionary(CODEC_PATH)
    bank = compile_event_sources(
        manifest,
        stock,
        translations,
        font16,
        dictionary,
        SHOP_EVENT_SOURCES,
        font12_metrics=font12,
    )[0]
    document = {
        "version": 1,
        "surface": "event.dialogue",
        "source": "SHOPSMP.EVE",
        "codec_sha256": _sha256_path(CODEC_PATH),
        "runtime_table_sha256": _sha256_bytes(dictionary.runtime_table()),
        "font16_metrics_sha256": _sha256_path(FONT16_METRICS_PATH),
        "font12_metrics_sha256": _sha256_path(FONT12_METRICS_PATH),
        "records": {
            "translated": len(translations),
            "deferred": 0,
            "total": len(translations),
        },
        "deferred": None,
        "outputs": {
            bank.path.as_posix(): {
                "sha256": _sha256_bytes(bank.data),
                "messages": bank.messages,
                "pages": bank.pages,
                "body_bytes": bank.body_bytes,
            }
        },
    }
    return {
        GENERATED_ROOT.joinpath(*bank.path.parts): bank.data,
        SHOPSMP_BUILD_PATH: (
            json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8"),
    }


def publish(outputs: dict[Path, bytes], *, check: bool) -> None:
    stale = [
        path
        for path, expected in outputs.items()
        if not path.is_file() or path.read_bytes() != expected
    ]
    if check:
        if stale:
            raise ValueError(
                "stale text outputs: "
                + ", ".join(str(path.relative_to(SATURN_ROOT)) for path in stale)
            )
        return
    for path, expected in outputs.items():
        if not path.is_file() or path.read_bytes() != expected:
            _atomic_write(path, expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=("event", "shopsmp", "negotiation", "battle", "all"),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        outputs = {}
        if arguments.target in {"event", "all"}:
            outputs.update(build_event_outputs())
        if arguments.target in {"shopsmp", "all"}:
            outputs.update(build_shopsmp_outputs())
        if arguments.target in {"negotiation", "all"}:
            outputs.update(build_negotiation_outputs())
        if arguments.target in {"battle", "all"}:
            outputs.update(build_battle_ui_outputs())
        publish(outputs, check=arguments.check)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    action = "verified" if arguments.check else "built"
    print(f"{action} {arguments.target} text outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
