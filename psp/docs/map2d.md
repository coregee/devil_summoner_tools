# PSP two-dimensional map

The MAP2D port owns every proved city-map text path from the original PSP
project: the lower native talk prompt and choices, the mirrored top prompt and
choices, five fixed destination tags, and the four dynamic city/ward draw
states. The 16 guarded BOOT writes retain all stock delay slots and relocation
records; their 2,049-byte payload is pinned to the mature implementation.

Authored wording remains consolidated. The prompt and choices bind to
`assets/text/field/messages.json`; destination names bind to
`assets/text/locations.json`, with only the 64-pixel `Mt. Kasagi` variant owned
by this surface. Dynamic city and ward values come from the shared NAME profile.

MAP2D uses two physical font projections without introducing another text
codec. Its lower fixed-grid path fills the deliberately reserved FONT16 codes
`0x069d..0x06af` with three precomposed Ark Pixel 12 rows. Its EVE path uses
Ark Pixel 12 for fixed rows and Ark Pixel 16 for dynamic names, but maps the 95
printable characters through the same packed-storage permutation used by EVENT,
command help, and the COMP panel. The EVE allocation is isolated at
`0x1d60..0x1dfe`; two four-cell scratch strips are cleared and rebuilt only
when a live city or ward name must be horizontally scaled.

The generated font and engine manifests publish the complete row, glyph,
scratch, write, and cave-capacity inventories. Focused tests reproduce both
font archives and the original executable payload from the pinned retail ISO.

## Runtime safety

The movement routine at `0xa3240..0xa32dc` indexes nine 35-by-35 u16 collision
grids at `0x172e98..0x1784ba` (end exclusive). Zero values are blocked tiles.
Earlier dungeon, savedata, and Compendium allocations incorrectly treated
zero-filled portions of these grids as spare storage. Their instructions and
text introduced walkable cells and invalid destination IDs, including outside
the visible map. These payloads now occupy explicitly retired NAME Kanji pages
at `0x1c7202..0x1c7b64`. The build validates the source reserve, its relocations,
the one-page NAME grid, and all active label descriptors before using it.
Every collision byte must match retail in the final combined executable.

The lower prompt rows are also used by the **3D field** retained-text renderer:
`0x2a39c -> 0x15bcc -> 0x15edc`, then `0x156f0 -> 0xc998` each frame. They
are independent of MAP2D's EVE prompt hooks. MAP2D now rejects a build unless
the native FONT16 gate admits every translated prompt/choice code. Extending
only the atlas while retaining the earlier `0x069d` gate blanks these rows.

`psp/engine/tests/test_map_safety.py` checks the entire collision table and
movement instruction sequence, reclaimed-storage ownership, and rejection of
the old glyph gate. With `unicorn` installed it additionally executes the
relocated native queue and C998 drawer at two load bases: all 14 prompt cells
and five choice cells reach sprite submission under either highlight state.
It also executes the relocated item/Compendium bridge and all 144 dungeon
locations through the HUD and four staircase-transition indices.
These are executable-level checks; in-game appearance still requires a fresh
ISO boot and normal gameplay verification.
