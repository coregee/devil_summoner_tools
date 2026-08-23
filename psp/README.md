# PSP package status

PSP implementation has begun with the original UMD font catalogue under
[`font/`](font/README.md), checked movie compilation under [`fmv/`](fmv/README.md),
and the ported runtime surfaces under [`engine/`](engine/README.md). The font package defines all twelve logical font
roles recovered from the original PSP project, including their twenty physical
archive or embedded targets, storage formats, hashes, confidence levels, and
cell grids. The engine package now owns the readable Allegrex title-help VWF
patch and readable CONFIG emitter, with exact source guards and focused tests.

The PSP-owned build pipeline now composes the complete English title-help,
CONFIG, command-help, battle-console, and START2 subtitle slices. It compiles
six title records, all 57 CONFIG/command-help slots, and 313 active BTL_MES
rows into `regdata.bin` while preserving
45 native empty rows; compiles nine canonical START2 cues after validating the
unchanged PMF; renders the checked Ark12/Ark16 allocations in `datapack.bin`
and the 95-glyph printable-ASCII bank in `eve_files.bin`; transactionally
rebuilds all five standard EVENT members from 2,830 canonical page bindings
plus the expanded 319-name insertion table; builds the title VWF,
29 CONFIG runtime rows, the retained-EVE command-help adapter, two guarded
battle-console body-offset instructions, and the lossless subtitle overlay into
BOOT/EBOOT. The stock-safe EVENT VWF runtime consumes those packed banks and
shares the command-help EVE advance table. The pipeline publishes a same-size
ISO by replacing only the six verified resource or executable extents.
Remaining text surfaces, engine patches, fonts, and visual assets still need
to be ported. The
font catalogue intentionally does not infer a live reader from a
Saturn-equivalent filename or bitmap.

```powershell
python -B psp/build.py default --plan
python -B psp/build.py default
python -B psp/build.py default --check
```

The current image is still an incomplete translation rather than a release, but
all six current slices are complete from authored English through text, font,
runtime, and ISO publication. The checked battle-console geometry, codec, and
runtime acceptance target are documented in [`docs/btl_mes.md`](docs/btl_mes.md);
the corresponding START2 contracts are in
[`docs/fmv_subtitles.md`](docs/fmv_subtitles.md).
Command-help storage, font, and retained-handle contracts are documented in
[`docs/command_menu_help.md`](docs/command_menu_help.md).
The reusable EVENT runtime boundary is documented in
[`docs/event_window.md`](docs/event_window.md).
