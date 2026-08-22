# PSP package status

PSP implementation has begun with the original UMD font catalogue under
[`font/`](font/README.md) and the first checked runtime surface under
[`engine/`](engine/README.md). The font package defines all twelve logical font
roles recovered from the original PSP project, including their twenty physical
archive or embedded targets, storage formats, hashes, confidence levels, and
cell grids. The engine package now owns the readable Allegrex title-help VWF
patch and readable CONFIG emitter, with exact source guards and focused tests.

The PSP-owned build pipeline now composes the complete English title-help and
CONFIG slices. It compiles six title records and nine CONFIG help records into
`regdata.bin`; renders their checked Ark12/Ark16 allocations in `datapack.bin`;
builds the title VWF and 29 CONFIG runtime rows into BOOT/EBOOT; and publishes a
same-size ISO by replacing only those four verified extents. Remaining text
surfaces, engine patches, fonts, and visual assets still need to be ported. The
font catalogue intentionally does not infer a live reader from a
Saturn-equivalent filename or bitmap.

```powershell
python -B psp/build.py default --plan
python -B psp/build.py default
python -B psp/build.py default --check
```

The current image is still an incomplete translation rather than a release, but
both current paths are complete from authored English through text, font,
runtime, and ISO publication.
