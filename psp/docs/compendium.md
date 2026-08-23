# PSP Demon Compendium

The PSP Compendium port is one atomic engine surface with two readers. Prose
retains the stock 319-row pointer/flag table and the original lore arena, while
full demon names use the 3,205-byte packed DVLNAME table already shared with
EVENT. Keeping them together prevents the name table from colliding with the
tail of the translated prose allocation.

`text/config/compendium.json` records every physical row. It binds 288
Saturn-inherited profiles and the four PSP-only profiles David, Enoch,
Leviathan, and Skoll to semantic entries in `assets/text/demons.json`.
Twenty-three empty rows and four orphan source profiles preserve their stock
pointer ownership and flags explicitly.

The compiler wraps origins to 195 pixels, summaries and details to 315 pixels,
and enforces the stock 1/3/11-row geometry. It deduplicates identical fields
inside the fixed `0x1d028`-byte prose arena. The canonical build owns 292 live
profiles, 876 translated fields, and 635 unique strings, using 116,577 bytes.

The runtime redirects only the three proved lore calls and two proved
Compendium name calls. A local packed-ASCII renderer uses the EVE member-5
glyph atlas and shared 95-byte advance table. A separate comparator sorts the
complete packed English names instead of the stock eight-cell Japanese source
rows, while IDs `0x100..0x105` retain the stock player-name fallback.

All hook preimages, JAL relocation records, source data hashes, row flags,
pointer relocations, atlas ownership, and three source-zero code caves are
validated before the surface is composed into BOOT/EBOOT.

