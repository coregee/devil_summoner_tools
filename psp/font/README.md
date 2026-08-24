# PSP fonts

The PSP font package follows the Saturn package's definition-first layout while
retaining PSP container ownership:

- `config/game/` contains one complete checked definition per logical font.
- `util/` validates definitions, reads Atlus PSP packs, decodes raw tiles and
  indexed/direct-color GIM pages, and normalizes their cells for comparison.
- `original/game/` contains ignored, locally imported target payloads.
- `atlas/game/` contains ignored reference sheets generated from those payloads.
- `generated/game/` contains guarded runtime inputs and, as raster publishers
  are ported, will contain repacked resources.

The catalogue covers twelve logical resources and twenty physical targets:
the EVE KANJI atlas, UNIT FONT12, two embedded FONT8 mirrors, DATAPACK FONT8,
two DATAPACK FONT12 pages, seven DATAPACK FONT16 pages, and six REGDATA raw
resources (FONT16, FONT6, FONT8, ICON, FNT8X12, and FNT12X12).

## Import and verification

Extract the original UMD to a directory containing `PSP_GAME`, then run from
the project root:

```powershell
python -B psp/font/extract.py --source-root C:\path\to\extracted-umd
python -B psp/font/extract.py --check
```

Use repeatable `--font` options for a focused import or check. Import validates
every selected physical size, archive-member offset, and SHA-256 before writing
the ignored logical sources. GIM pages are decoded with their real palettes and
swizzle order; the generated atlas is a review view, not a replacement image.

## Editing boundary

The browser editor lists all twelve PSP resources alongside the Saturn fonts.
Every physical cell can be inspected, searched, and assigned a reviewed source
identity in its checked definition. Definitions show whether the original
project proved a runtime reader or only an unresolved archive relationship.

Only the EVE source-blank `0x1E20..0x1E7E` range is declared as a generic
editable raster domain. The guarded publisher maps all 95 printable ASCII
characters to the Ark Pixel 12 source face, preserves every unowned tile and
palette record, and emits both `eve_files.bin` and the runtime advance table
shared by command help and the EVENT VWF foundation.
The COMP six-card panel adds a second, smaller Ark Pixel 10 raster in the
disjoint blank range `0x1155..0x11b3`. It uses the same 95-byte packed storage
order as EVENT/help; only its glyph pixels and screen-local advances differ.
FONT16 remains feature-owned rather than globally editable. The composed
publisher owns the title-help Ark12 cells,
the proved START2 Ark16 base allocation, CONFIG's twelve new Ark16 cells, its
shared 74-character low-code Ark12 alphabet used by title help, CONFIG modes,
battle names, the live NAME alphabet, and full demon names, plus the maze
location display's Ark Pixel 12 alphabet. START2 owns codes `0x0672..0x0690`,
compiled directly from the canonical timed-text character inventory; CONFIG
extends the same checked page through `0x069c`. MAP2D fills the reserved
`0x069d..0x06af` cells with its native prompt and choice rows, while the maze
display retains the original `0x06b0..0x06e3` allocation.

MAP2D also fills a disjoint EVE bank at `0x1d60..0x1dfe` with Ark12 fixed
destinations/prompts, two blank four-cell scaling strips, and an Ark16 dynamic
name projection. The Ark16 cells reuse the common packed printable-ASCII
permutation; this is a screen-specific raster and advance table, not another
stored-text encoding.

The ported BTL_MES battle console validates the stock 72-cell FNT8X12 member
as codec and source-order evidence, but does not rewrite that member or broaden
its unresolved runtime-reader claim.

This distinction is deliberate: a byte-identical Saturn-named resource is
format evidence, not proof that its PSP reader is live or interchangeable.

## Runtime metrics

The composed font stage generates the title-help, EVE Ark12, COMP Ark10, and
MAP2D advance tables, a same-size `datapack.bin`, and a same-size
`eve_files.bin` from pinned Ark Pixel faces and checked PSP raster geometry:

```powershell
python -B psp/font/repack.py all
python -B psp/font/repack.py all --check
```

The publisher verifies the source pack, member 9 and member 15 GIM geometry and palette,
every owned glyph code, the MAP2D and maze allocations, both changed-byte inventories, and
the exact legacy output hashes. The manifest exports the START2 and EVE
mappings plus the shared Ark12 and CONFIG Ark16 mappings, advance table, and draw
limit for later build stages.
