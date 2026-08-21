# PSP fonts

The PSP font package follows the Saturn package's definition-first layout while
retaining PSP container ownership:

- `config/game/` contains one complete checked definition per logical font.
- `util/` validates definitions, reads Atlus PSP packs, decodes raw tiles and
  indexed/direct-color GIM pages, and normalizes their cells for comparison.
- `original/game/` contains ignored, locally imported target payloads.
- `atlas/game/` contains ignored reference sheets generated from those payloads.
- `generated/game/` is reserved for guarded repacked resources.

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

Only the EVE source-blank `0x1E20..0x1E7E` range is declared as an initial
editable raster domain. It maps all 95 printable ASCII characters to the
Ark Pixel 12 source face. The frontend currently keeps its rebuild control
locked because the new repository does not yet own the guarded `eve_files.bin`
publisher and runtime width-table install. The seven-page FONT16 atlas is
runtime-proven but also remains raster-locked: the old project divided its
English allocations among title help, CONFIG, START2, MAP2D, and other
feature-local guards, which must be ported rather than flattened into one
unsafe global replacement map.

This distinction is deliberate: a byte-identical Saturn-named resource is
format evidence, not proof that its PSP reader is live or interchangeable.

