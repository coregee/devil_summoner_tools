"""Discover the two Saturn discs' structurally defined image records."""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

from .codec import decode, pixel_hash
from .model import ImageAsset, ImageView
from .paths import SPECIAL_VIEWS_PATH, rom_root

LOAD_BASE = 0x250000

ROOT_IMAGES = {
    "BAD_P1.CHR": (0, 64, 64, "tiled8"),
    "BAD_P2.CHR": (0, 64, 64, "tiled8"),
    "GOMI.CHR": (0, 96, 56, "tiled8"),
    "P_PANEL.CHR": (0, 144, 112, "linear"),
    "TUKI.CHR": (0, 184, 128, "tiled8"),
    "HP_M.CHR": (0, 24, 3, "linear"),
    "EACHR.COF": (0, 320, 96, "tiled8"),
    "COMBDATA/TESTBG.BIN": (0, 320, 224, "linear"),
    "MMP/MMBG00.COF": (0x84, 352, 224, "tiled8"),
    "MMP/NAMEBG.COF": (0x84, 352, 224, "tiled8"),
}

TEX3D_MODELS = {
    "ARCA_CHR": "ARCADE",
    "ASU_CHR": "ASU",
    "CHI_CHR": "CHI",
    "CYU_CHR": "CYU",
    "DOUT_CHR": "DOUT00",
    "EX_CHR": "EX",
    "GIRL_CHR": "GIRL00",
    "HAKU_CHR": "HAKU",
    "HBIN_CHR": "HBIN00",
    "HDAI_CHR": "HDAI00",
    "HDEN_CHR": "HDEN00",
    "HGIN_CHR": "HGIN00",
    "HHAK_CHR": "HHAK00",
    "HMAN_CHR": "HMAN00",
    "HOUT_CHR": "HOUT00",
    "HST_CHR": "HST00",
    "HTOS_CHR": "HTOS00",
    "HYA_CHR": "HYA00",
    "ICYU_CHR": "ICYU",
    "IDAI_CHR": "IDAI00",
    "IDEN_CHR": "IDEN00",
    "IGIN_CHR": "IGIN00",
    "IMAN_CHR": "IMAN00",
    "IST_CHR": "IST00",
    "ITOS_CHR": "ITOS00",
    "ITV_CHR": "ITV00",
    "IYA_CHR": "IYA00",
    "IYOZ_CHR": "IYOZ00",
    "KO_CHR": "KO",
    "KOUJ_CHR": "KOUJI00",
    "KUMI_CHR": "KUMI",
    "KYOZ_CHR": "KYOZ00",
    "MU_CHR": "MU",
    "SHI_CHR": "SHI00",
    "ZATU_CHR": "ZATU00",
    "ZATUFCHR": "ZATU_F",
}


TITLE_INDEXED_ASSETS = (
    ImageAsset(
        "TITLE.BIN",
        "TITLE/devil_summoner.png",
        0x16644,
        288,
        53,
        encoding="indexed8",
        palette_offset=0x1A1E4,
        palette_entries=198,
    ),
    ImageAsset(
        "TITLE.BIN",
        "TITLE/shin_megami_tensei.png",
        0x1A3E4,
        288,
        36,
        encoding="indexed8",
        palette_offset=0x1CC64,
        palette_entries=64,
    ),
    ImageAsset(
        "TITLE.BIN",
        "TITLE/emblems.png",
        0x1CE64,
        120,
        28,
        encoding="indexed8",
        palette_offset=0x1DB84,
        palette_entries=64,
    ),
)

TITLE_PRESS_START_GLYPHS = tuple(
    ImageAsset(
        "TITLE.BIN",
        f"TITLE/press_start_button/{index:02d}_{letter.lower()}.png",
        offset,
        16,
        12,
    )
    for index, (letter, offset) in enumerate(
        zip(
            "PRESSSTARTBUTTON",
            (
                0x1DD84,
                0x1DF04,
                0x1E084,
                0x1E204,
                0x1E384,
                0x1E504,
                0x1E684,
                0x1E804,
                0x1E984,
                0x1EB04,
                0x1EC84,
                0x1EE04,
                0x1F104,
                0x1EF84,
                0x1F284,
                0x1F404,
            ),
            strict=True,
        )
    )
)

TITLE_MENU_GLYPHS = tuple(
    ImageAsset(
        "TITLE.BIN",
        f"TITLE/start_button/{index:02d}_{letter.lower()}.png",
        offset,
        width,
        9,
    )
    for index, (letter, offset, width) in enumerate(
        zip(
            "STARTOPTION",
            (
                0x1F584,
                0x1F6A4,
                0x1F7C4,
                0x1F8E4,
                0x1FA04,
                0x1FB24,
                0x1FC44,
                0x1FD64,
                0x1FE84,
                0x1FF14,
                0x20034,
            ),
            (16, 16, 16, 16, 16, 16, 16, 16, 8, 16, 16),
            strict=True,
        )
    )
)

TITLE_COPYRIGHT_ASSET = ImageAsset(
    "TITLE.BIN", "TITLE/copyright_atlus_1995.png", 0x20154, 120, 15
)


def _title_assets() -> list[ImageAsset]:
    return [
        *TITLE_INDEXED_ASSETS,
        TITLE_COPYRIGHT_ASSET,
        *TITLE_PRESS_START_GLYPHS,
        *TITLE_MENU_GLYPHS,
        ImageAsset(
            "TESTLOGO.COF",
            "TITLE/full_title_screen.png",
            0,
            352,
            240,
            encoding="rgb888",
        ),
    ]


def _saveload_assets() -> list[ImageAsset]:
    rows = {
        "SAVE.BIN": {
            "internal_selected": 0x383F0,
            "internal_idle": 0x37070,
            "cartridge_selected": 0x3FD30,
            "cartridge_idle": 0x34970,
        },
        "LOAD.BIN": {
            "internal_selected": 0x380EC,
            "internal_idle": 0x36D6C,
            "cartridge_selected": 0x3FA2C,
            "cartridge_idle": 0x3466C,
        },
    }
    return [
        ImageAsset(source, f"{Path(source).stem}/storage/{name}.png", offset, 104, 24)
        for source, records in rows.items()
        for name, offset in records.items()
    ]


def _archive(
    root: Path, source: str, model: str, count: int, dimensions: int
) -> list[ImageAsset]:
    texture_data = (root / source).read_bytes()
    model_data = (root / model).read_bytes()
    header_size = count * 8
    stem = Path(source).with_suffix("").as_posix()
    assets = []
    for index in range(count):
        row = index * 8
        declared, copies, address = struct.unpack_from(">HHI", texture_data, row)
        if (declared, copies) != (index, 1):
            raise ValueError(f"{source}: invalid texture record {index}")
        offset = address - LOAD_BASE
        width, height = struct.unpack_from(">HH", model_data, dimensions + row)
        next_offset = (
            struct.unpack_from(">I", texture_data, row + 12)[0] - LOAD_BASE
            if index + 1 < count
            else len(texture_data)
        )
        if offset < header_size or next_offset - offset != width * height * 2:
            raise ValueError(
                f"{source}: texture {index} does not match {width}x{height}"
            )
        assets.append(
            ImageAsset(source, f"{stem}/{index:03d}.png", offset, width, height)
        )
    return assets


def _game_assets(root: Path) -> list[ImageAsset]:
    assets = [
        ImageAsset(
            source,
            f"{Path(source).with_suffix('').as_posix()}.png",
            offset,
            width,
            height,
            layout,
        )
        for source, (offset, width, height, layout) in ROOT_IMAGES.items()
    ]
    assets.extend(_title_assets())
    assets.extend(_saveload_assets())
    actual_tex3d = {path.stem for path in (root / "TEX3D").glob("*.BIN")}
    if actual_tex3d != set(TEX3D_MODELS):
        raise ValueError("TEX3D source set does not match the supported game revision")
    for texture, model in sorted(TEX3D_MODELS.items()):
        model_path = f"MDL3D/{model}.BIN"
        count = struct.unpack_from("<I", (root / model_path).read_bytes())[0]
        assets.extend(
            _archive(root, f"TEX3D/{texture}.BIN", model_path, count, 0x20)
        )
    for texture in sorted((root / "MMP").glob("*CHR.COF")):
        model = texture.with_name(texture.name.replace("CHR.COF", "MDL.COF"))
        if not model.is_file():
            raise ValueError(f"{texture.name}: matching model file is missing")
        count = struct.unpack_from(">H", model.read_bytes(), 6)[0]
        assets.extend(
            _archive(
                root,
                texture.relative_to(root).as_posix(),
                model.relative_to(root).as_posix(),
                count,
                0x48,
            )
        )
    return assets


def _compendium_assets(root: Path) -> list[ImageAsset]:
    profiles = sorted(root.glob("DVL_*.DAT"), key=lambda path: path.name.casefold())
    malformed = [
        profile.name
        for profile in profiles
        if re.fullmatch(r"DVL_[0-9A-F]{3}\.DAT", profile.name) is None
    ]
    if malformed:
        raise ValueError(f"compendium has malformed DVL profile names: {malformed}")
    if len(profiles) != 292:
        raise ValueError(
            "compendium DVL profile set does not match the supported disc revision"
        )
    assets: list[ImageAsset] = []
    for profile in profiles:
        if profile.stat().st_size != 0x781DC:
            raise ValueError(f"{profile.name}: expected a 0x781dc-byte profile")
        assets.append(
            ImageAsset(
                profile.name,
                f"profiles/{profile.stem}.png",
                0,
                512,
                480,
            )
        )
    for source in ("NOAREA.CHR", "NOSAVE.CHR", "TI.CHR"):
        path = root / source
        if not path.is_file():
            raise ValueError(f"{source}: compendium screen is missing")
        if path.stat().st_size != 0x60000:
            raise ValueError(f"{source}: expected a 0x60000-byte screen")
        assets.append(
            ImageAsset(source, f"screens/{Path(source).stem}.png", 0, 512, 384)
        )
    return assets


def discover_assets(disc: str) -> tuple[ImageAsset, ...]:
    root = rom_root(disc)
    assets = _game_assets(root) if disc == "game" else _compendium_assets(root)
    assets.sort(
        key=lambda asset: (
            asset.source.casefold(),
            asset.offset,
            asset.image.casefold(),
        )
    )
    if len({asset.image.casefold() for asset in assets}) != len(assets):
        raise ValueError("image discovery produced duplicate paths")
    for asset in assets:
        source_size = (root / asset.source).stat().st_size
        if asset.offset < 0 or asset.offset + asset.byte_length > source_size:
            raise ValueError(f"{asset.image}: pixels fall outside {asset.source}")
    return tuple(assets)


def discover_views(
    disc: str, assets: tuple[ImageAsset, ...]
) -> tuple[ImageView, ...]:
    by_image = {asset.image.casefold(): asset for asset in assets}
    document = (
        json.loads(SPECIAL_VIEWS_PATH.read_text(encoding="utf-8"))
        if disc == "game"
        else {"views": []}
    )
    root = rom_root(disc)
    claimed: set[str] = set()
    views: list[ImageView] = []
    for row in document["views"]:
        targets = tuple(by_image[str(path).casefold()] for path in row["targets"])
        keys = {target.image.casefold() for target in targets}
        if claimed & keys:
            raise ValueError(f"{row['path']}: target appears in two special views")
        claimed.update(keys)
        view = ImageView(str(row["path"]), str(row["layout"]), targets)
        if len({target.height for target in targets}) != 1:
            raise ValueError(f"{view.path}: targets have different heights")
        if view.layout == "identity":
            if len({(target.width, target.height) for target in targets}) != 1:
                raise ValueError(f"{view.path}: identity targets have different sizes")
            hashes = {
                pixel_hash(decode((root / target.source).read_bytes(), target))
                for target in targets
            }
            if len(hashes) != 1:
                raise ValueError(f"{view.path}: identity targets have different pixels")
        elif view.layout != "horizontal":
            raise ValueError(f"{view.path}: unsupported layout {view.layout}")
        views.append(view)
    views.extend(
        ImageView(asset.image, "identity", (asset,))
        for asset in assets
        if asset.image.casefold() not in claimed
    )
    views.sort(key=lambda view: view.path.casefold())
    if len({view.path.casefold() for view in views}) != len(views):
        raise ValueError("editable view paths are not unique")
    return tuple(views)
