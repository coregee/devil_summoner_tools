"""Small immutable values shared by the editor services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsumerUse:
    record_id: str
    surface: str | None


@dataclass(frozen=True, slots=True)
class EntryKey:
    asset: str
    entry: str
    field: str

    @property
    def asset_ref(self) -> str:
        return f"{self.entry}.{self.field}"

    @property
    def id(self) -> str:
        return f"{self.asset}#{self.asset_ref}"

    @classmethod
    def parse(cls, value: str) -> "EntryKey":
        try:
            asset, asset_ref = value.split("#", 1)
            entry, field = asset_ref.rsplit(".", 1)
        except ValueError as error:
            raise ValueError("invalid editor entry id") from error
        if (
            not asset.endswith(".json")
            or not entry
            or not field
            or "\\" in asset
            or asset.startswith("/")
            or any(part in {"", ".", ".."} for part in asset.split("/"))
        ):
            raise ValueError("invalid editor entry id")
        return cls(asset, entry, field)

