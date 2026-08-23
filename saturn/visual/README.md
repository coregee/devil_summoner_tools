# Saturn visuals

This package owns Saturn image discovery, binary layouts, and repacking. The
editable replacement pixels live in the repository-wide image catalog so PSP
can reuse genuinely identical art without copying it.

```text
extracted/game/          generated game-disc PNGs
extracted/compendium/    generated compendium-disc PNGs
modified/game/           tracked game extraction manifest
modified/compendium/     tracked compendium extraction manifest
bindings/game.json       shared assets mapped to Saturn game views
bindings/compendium.json shared assets mapped to Saturn compendium views
util/                    discovery, codecs, and exceptional view definitions
extract.py               extract and validate either or both working sets
repack.py                patch changed images into the selected disc mirrors
```

`extracted/` is ignored because it can be recreated from the original discs.
Each tracked `modified/<disc>/manifest.json` records the decoded pixel hashes;
the legacy directory name is retained because engine ownership checks consume
those manifests. Replacement PNGs and their semantic metadata are tracked under
`assets/image/`, while this package's bindings retain Saturn view paths.

## Extract

From the project root:

```powershell
python -B saturn/visual/extract.py
python -B saturn/visual/extract.py game --check
python -B saturn/visual/extract.py compendium --check
```

The optional positional selector is `game`, `compendium`, or `all`; it defaults
to `all`. Extraction never creates, replaces, or removes shared assets. Use
`--overwrite` only after restoring the selected `rom/extracted/<disc>` mirror
from its original disc. It replaces that disc's extracted baseline and
manifest while preserving every shared replacement asset and binding.

The game catalog contains 2,365 logical images. It discovers the standalone
rasters plus every model-described TEX3D and MMP texture.

The current compendium catalog deliberately contains only the 295 structures
whose complete pixel spans are known:

- 292 `DVL_*.DAT` profile images: 512x480 RGB555 pixels at offset zero; and
- `NOAREA.CHR`, `NOSAVE.CHR`, and `TI.CHR`: 512x384 RGB555 screens.

The 0x1dc-byte non-image tail of every profile file is left untouched. The
`DVLDATA/*.CHR`, `A_TITLE.BIN`, `A_DIC.BIN` raster regions, and `ATL_LOGO.BIN`
formats are not yet sufficiently classified and are intentionally excluded from
the visual catalogue. This does not leave `A_DIC.BIN` text unowned:
`engine/build.py compendium.text` rebuilds every proved name, race-description,
and fusion-help text span independently. The CPK files belong to the future FMV
workflow. The seven `OMAKE/*.BMP` files are already ordinary bonus-disc images
and have not been shown to be runtime patch targets.

## Repack

```powershell
python -B saturn/visual/repack.py --list
python -B saturn/visual/repack.py game
python -B saturn/visual/repack.py compendium --check
```

An absent binding means that the original image is preserved. The manifest
compares decoded pixels rather than PNG file bytes, so metadata or compression
changes do not trigger a rebuild. Repacking starts with each current ROM file
and changes only bound assets whose pixels differ from the baseline.
Unrelated binary changes in the same file, including compendium profile text,
are preserved. Run `saturn/rom/repack.py` for each disc afterward.

To add a replacement, copy the extracted PNG into the appropriate semantic
folder under `assets/image/`, register its stable ID and dimensions in
`assets/image/catalog.json`, and bind that ID to the Saturn view in
`bindings/<disc>.json`. Reuse an existing ID only when the required pixels and
dimensions are identical. Similar wording with a different sheet layout remains
a distinct platform-layout asset.

The exceptional game layouts are declared in `util/special_views.json`:

- eight two-texture images are stitched horizontally for editing and split at
  their original widths during repacking;
- identical SAVE/LOAD and CYU/ICYU images share one editable PNG; and
- the three indexed `TITLE.BIN` overlays retain their individual runtime RGB555
  palettes. Changed overlays are quantized back into those palette budgets,
  including transparent and opaque black handling.

`TITLE.BIN` also contains two contiguous positional glyph runs. The visual
catalogue extracts sixteen 16x12 records spelling `PRESS START BUTTON` and
eleven 16/8x9 records spelling `START` plus `OPTION`. The translation editor
exposes these runs as the read-only `TITLE Prompt` and `TITLE Menu` Saturn
fonts. Every physical position is mapped, but only ten and eight distinct
capital letters respectively exist in the source; there is no unused alphabet
storage in these spans.

Structural and byte-for-byte checks do not establish in-game presentation.
Changed title, save/load, TEX3D, profile, and compendium warning screens still
need emulator or hardware review after building the relevant disc.

The package currently has no ownership of MSGR, MAP2D, END_ROLL, HOSI, SNDTEST,
or TEST3D; their visible text is generated by the text/engine packages. SAVE and
LOAD are the deliberate mixed-owner case: engine text/runtime bytes are
installed first, then the eight catalogued selector-image spans are applied and
verified without allowing either package to overwrite the other's regions.
