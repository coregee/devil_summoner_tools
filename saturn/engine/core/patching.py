"""Small, explicit binary-patch model shared by Saturn engine surfaces."""

from __future__ import annotations

from dataclasses import dataclass


class PatchError(ValueError):
    """A patch did not match its exact stock binary contract."""


@dataclass(frozen=True, slots=True)
class Patch:
    group: str
    name: str
    address: int
    expected: bytes
    replacement: bytes

    def __post_init__(self) -> None:
        if not self.group or not self.name:
            raise ValueError("patch group and name must be nonempty")
        if self.address < 0 or not self.expected:
            raise ValueError(f"{self.group}/{self.name}: invalid patch site")
        if len(self.expected) != len(self.replacement):
            raise ValueError(
                f"{self.group}/{self.name}: expected/replacement sizes differ"
            )


def apply_patches(original: bytes, load_address: int, patches: tuple[Patch, ...]) -> bytes:
    """Validate every site and overlap before applying any replacement."""
    sites: list[tuple[int, int, Patch]] = []
    names: set[tuple[str, str]] = set()
    for patch in patches:
        identity = (patch.group, patch.name)
        if identity in names:
            raise PatchError(f"duplicate patch name {patch.group}/{patch.name}")
        names.add(identity)
        start = patch.address - load_address
        end = start + len(patch.expected)
        if start < 0 or end > len(original):
            raise PatchError(
                f"{patch.group}/{patch.name} at {patch.address:#010x} lies "
                "outside the target"
            )
        sites.append((start, end, patch))
    sites.sort(key=lambda row: (row[0], row[1]))
    for previous, current in zip(sites, sites[1:]):
        if current[0] < previous[1]:
            raise PatchError(
                f"patches {previous[2].group}/{previous[2].name} and "
                f"{current[2].group}/{current[2].name} overlap"
            )
    for start, end, patch in sites:
        actual = original[start:end]
        if actual != patch.expected:
            raise PatchError(
                f"{patch.group}/{patch.name} did not match at "
                f"{patch.address:#010x}; expected {patch.expected.hex()}, "
                f"found {actual.hex()}"
            )
    output = bytearray(original)
    for start, end, patch in sites:
        output[start:end] = patch.replacement
    return bytes(output)
