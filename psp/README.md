# PSP package status

PSP implementation has begun with the original UMD font catalogue under
[`font/`](font/README.md) and the first checked runtime surface under
[`engine/`](engine/README.md). The font package defines all twelve logical font
roles recovered from the original PSP project, including their twenty physical
archive or embedded targets, storage formats, hashes, confidence levels, and
cell grids. The engine package now owns the readable Allegrex title-help VWF
patch, its versioned recipe, exact source guards, and focused tests.

This is not yet a PSP build. Text bindings, the remaining engine patches,
visual assets, UMD publication, and a top-level install profile still need to
be ported as PSP-owned components. The title-help builder is deliberately not
published until ROM extraction and executable composition have PSP-owned
workflows. The font catalogue intentionally does not infer a live reader from
a Saturn-equivalent filename or bitmap.
