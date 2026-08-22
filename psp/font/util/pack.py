"""Compatibility reader for the shared Atlus PSP resource-pack codec."""

from __future__ import annotations

from psp.archive.pack import PackMember, PspPack


def read_members(data: bytes) -> tuple[PackMember, ...]:
    return PspPack.parse(data).members
