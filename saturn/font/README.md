# Saturn fonts

The font package supports the game and Akuma Zensho compendium discs. Its four
directories are divided by disc:

- `atlas/<disc>/` contains generated `FONT_original.png` and
  `FONT_modified.png` reference sheets.
- `config/<disc>/` contains one complete JSON definition per Saturn font. Each
  definition owns its packed format, atlas glyph map, preview layout,
  replacement map, source typeface, metrics settings, and physical targets.
- `util/` contains the shared binary codec and definition loader.
- `generated/<disc>/` contains ignored repacked `.FON` files and derived
  metrics such as advance tables.

Open-source typefaces and their licenses live outside the platform package at
`../../assets/font/<font>/`.

The scripts require Pillow and read original fonts from
`../rom/extracted/<disc>/`. Run them from the project root:

```powershell
python -B saturn/font/extract.py all
python -B saturn/font/repack.py all
python -B saturn/font/extract.py all --check
python -B saturn/font/repack.py all --check
```

`all` is the default when no disc is supplied. Pass `game` or `compendium` for
one disc. Use repeatable `--font` options for focused work:

```powershell
python -B saturn/font/extract.py game --font FONT16.FON
python -B saturn/font/repack.py all --font font16
```

A font name applies to every selected disc containing that name. Selecting
`font16` with `all` therefore processes the distinct game and compendium
definitions.

Definitions validate the original font and source-typeface hashes. Repacking
starts from each disc's font, preserves every unmapped glyph, and writes only
generated outputs. The game `KANJI.FON` definition has two verified physical
targets, `KANJI.FON` and `MMP/KANJI.FON`; the parent build installs its one
generated result at both paths.

A definition may also expose a named `reference_set` for stock cells that must
remain addressable after repacking. Game `FONT8.FON` publishes cells 0-62 as
`stock_latin`: the original space, digits, uppercase letters, and lowercase
letters. It also publishes the source-preserved punctuation cells 174, 176, and
198 under the ASCII aliases `-`, `.`, and `/`. A `reference_sets[].aliases` entry changes
only the character name published to that named consumer map; it does not
change the base source decoding or take ownership of the glyph bitmap. These
cells are not replacements and are asserted byte-preserved. Generated FONT8
metrics therefore contain both the normal narrow-English map and this
separately named stock map; consumers must choose the stock map explicitly
rather than resolving duplicate Latin characters by accident.

Game `KANJI.FON` likewise publishes the name-entry grid's `stock_latin` set:
the exact retail uppercase and lowercase alphabets, digits, punctuation,
interpunct, and selectable-blank cell used across the stock codename page and
English replacement grids. Repacking remains byte-for-byte identical; its
generated metrics only give those preserved cells stable names, codes, and
measured advances.
`name_entry.grid_row` selects this map through a dedicated text glyph handler,
so engine code does not need to reconstruct the code ranges. The grid's END
control is a different boundary: `FONT16.FON` names its original two-cell image
compound as `{input_end_prefix}` and `{input_end_symbol}` without replacing
either raster. Left/right and END action semantics stay authored text, while a
different visible raster still requires coordinated font and engine work.

Run extraction and `extract.py --check` against mirrors restored from the
original discs. They deliberately reject generated fonts installed by a build.

The compendium `FONT16.FON` definition is deliberately identity-only. It shares
the game's 16x16 binary cell format but has a different glyph layout and must
not inherit the game's replacement map or embedded advance table.

After a parent build installs generated fonts into a disc mirror,
`repack.py --check` also accepts target files byte-identical to the generated
output and verifies that rebuilding them is idempotent.
