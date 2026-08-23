# Shared image assets

This directory owns canonical editable raster art that may be consumed by more
than one platform. `catalog.json` gives each image a stable semantic ID, its
relative PNG path, dimensions, and its known portability boundary.

Platform packages continue to own binary layout. Saturn binds catalog assets to
decoded manifest views in `saturn/visual/bindings/`; PSP may bind the same asset
ID when its required pixels are identical, or add a platform-layout variant when
the sheet geometry differs. A common subject or English phrase does not by
itself make two differently arranged sheets the same asset.

The current catalog contains the 44 active Saturn replacements plus three
assets used directly by PSP:

- 37 maze textures whose translated pixels are also suitable for PSP;
- three title images whose translated pixels are shared with PSP;
- one lower-resolution title overlay using a PSP-specific layout;
- one PSP save/game icon shared by its archive and direct-ISO consumers;
- one title-emblem sheet with shared semantics but platform-specific layout; and
- four Saturn-layout SAVE/LOAD selector images.

Generated extraction baselines, encoding rules, palettes, binary offsets, and
repacking logic remain platform-owned. Add replacement art here only after
giving it a catalog entry and an explicit platform binding.
