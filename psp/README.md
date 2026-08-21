# PSP package status

PSP implementation has begun with the original UMD font catalogue under
[`font/`](font/README.md). It defines all twelve logical font roles recovered
from the original PSP project, including their twenty physical archive or
embedded targets, storage formats, hashes, confidence levels, and cell grids.

This is not yet a PSP build. Text bindings, engine patches, visual assets, UMD
publication, and a top-level install profile still need to be ported as
PSP-owned components. The font catalogue intentionally does not infer a live
reader from a Saturn-equivalent filename or bitmap.
