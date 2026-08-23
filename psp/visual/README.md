# PSP visuals

This package encodes the shared title and maze replacement art for PSP while
keeping PSP-specific pack membership, palettes, swizzling, alpha behavior, and
fan-out under `psp/visual`.

```text
bindings/title.json   four fixed-size datatit GIM targets
bindings/save_icon.json one PNG shared by archive and direct-ISO targets
bindings/maze.json    37 shared images mapped through 15 TEX3D families
util/workflow.py      checked GIM/RGB555 composition
generated/game/       20 unique encoded members/files and one manifest
repack.py             build or verify the generated members
```

From the repository root:

```powershell
python -B psp/visual/repack.py all
python -B psp/visual/repack.py all --check
python -m unittest discover -s psp/visual/tests -v
```

The title slice uses three cross-platform catalog images plus the PSP-specific
114x25 Shin Megami Tensei overlay. It preserves the PSP source alpha mask for
the diamond-kanji overlay, applies the proved black-matte treatment to the Devil
Summoner overlay, and quantizes the complete title screen into its fixed INDEX8
palette. All four encoded GIM members retain their original byte sizes.

The maze slice reuses 37 catalog images across 45 logical texture slots. Two
CYU textures also bind to their identical ICYU slots. The fifteen unique RGB555
TEX3D members fan out through 83 PSP maze packs, representing 153 physical
texture placements.

The 144x80 PSP save/game icon is encoded once into its fixed 10,522-byte PNG
capacity, then bound both to `savedata.bin` member 1 and to the direct
`PSP_GAME/ICON0.PNG` entry. Its pixels round-trip losslessly.

Only the 20 unique encoded members/files are generated. The ROM composer applies
them to one title pack, 83 maze packs, the savedata pack, and the direct icon,
producing 86 same-size ISO extent replacements without storing duplicate
rebuilt packs. Tests pin the
aggregate encoded-member fingerprint to the mature project output.

Other PSP menu, status, facility, automap, name-entry, and loading
sheets have different layouts or no Saturn equivalent. They remain future
platform-layout assets and must not reuse a shared ID merely because their text
or role is similar.
