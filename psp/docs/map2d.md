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
