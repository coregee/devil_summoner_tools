"""Small data types shared by the visual workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ImageAsset:
    source: str
    image: str
    offset: int
    width: int
    height: int
    layout: str = "linear"
    encoding: str = "rgb555"
    palette_offset: int | None = None
    palette_entries: int | None = None

    @property
    def byte_length(self) -> int:
        return (
            self.width
            * self.height
            * {"rgb555": 2, "rgb888": 4, "indexed8": 1}[self.encoding]
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, object]) -> ImageAsset:
        return cls(
            source=str(row["source"]),
            image=str(row["image"]),
            offset=int(row["offset"]),
            width=int(row["width"]),
            height=int(row["height"]),
            layout=str(row.get("layout", "linear")),
            encoding=str(row.get("encoding", "rgb555")),
            palette_offset=(
                None
                if row.get("palette_offset") is None
                else int(row["palette_offset"])
            ),
            palette_entries=(
                None
                if row.get("palette_entries") is None
                else int(row["palette_entries"])
            ),
        )


@dataclass(frozen=True)
class ImageView:
    path: str
    layout: str
    targets: tuple[ImageAsset, ...]

    @property
    def size(self) -> tuple[int, int]:
        if self.layout == "identity":
            return self.targets[0].width, self.targets[0].height
        return sum(target.width for target in self.targets), self.targets[0].height
