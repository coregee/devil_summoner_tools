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
editable raster domain. It maps all 95 printable ASCII characters to the Ark
Pixel 12 source face. The frontend currently keeps its rebuild control locked
because the new repository does not yet own the guarded `eve_files.bin`
publisher and runtime width-table install. FONT16 remains feature-owned rather
than globally editable: the title-help publisher now owns its exact 26 visible
Latin cells in page 0, while CONFIG, START2, MAP2D, and the other allocations
remain locked until their local guards are ported.

This distinction is deliberate: a byte-identical Saturn-named resource is
format evidence, not proof that its PSP reader is live or interchangeable.

## Runtime metrics

The title-help slice generates its 95-entry Allegrex advance table and a
same-size `datapack.bin` containing the authored surface's FONT16 cells directly
from the pinned Ark Pixel 12px face and checked PSP raster geometry:

```powershell
python -B psp/font/repack.py title_help
python -B psp/font/repack.py title_help --check
```

The publisher verifies the source pack, member 9 GIM geometry and palette,
every owned glyph code, all unowned cells, the 1,139 changed-byte inventory,
and the exact legacy output hashes. Until the shared EVENT font publisher is
ported, the runtime table retains its proved 95-entry fallback advances and
overrides only the title-owned glyphs.
