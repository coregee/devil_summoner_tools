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
FONT16 remains feature-owned rather than globally editable. The composed
publisher owns the title-help Ark12 cells,
the proved START2 Ark16 base allocation, CONFIG's twelve new Ark16 cells, and
its three Ark12 mode-label cells. START2 owns codes `0x0672..0x0690`, compiled
directly from the canonical timed-text character inventory; CONFIG extends the
same checked page through `0x069c`. MAP2D and the other allocations remain
locked until their local guards are ported.

The ported BTL_MES battle console validates the stock 72-cell FNT8X12 member
as codec and source-order evidence, but does not rewrite that member or broaden
its unresolved runtime-reader claim.

This distinction is deliberate: a byte-identical Saturn-named resource is
format evidence, not proof that its PSP reader is live or interchangeable.

## Runtime metrics

The composed font stage generates the title-help and EVE 95-entry advance
tables, a same-size `datapack.bin`, and a same-size `eve_files.bin` from pinned
Ark Pixel faces and checked PSP raster geometry:

```powershell
python -B psp/font/repack.py all
python -B psp/font/repack.py all --check
```

The publisher verifies the source pack, member 9 and member 15 GIM geometry and palette,
every owned glyph code, all unowned cells, both changed-byte inventories, and
the exact legacy output hashes. The manifest exports the START2 and EVE
mappings plus CONFIG's composed Ark12/Ark16 mapping, advance table, and draw
limit for later build stages.
