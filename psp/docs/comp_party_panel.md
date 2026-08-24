# PSP COMP party-panel names

The call at module address `0x0002b204` is the common six-card party-name path.
Its six checked callers serve the COMP command screens; the similar
`0x0002ad48` call belongs to an unrelated 18-slot grid and remains stock.

The replacement reads the unit ID retained in the caller's frame and selects
one packed-English owner:

- `0x8000` reads the canonical live Codename directly from the NAME profile;
- `0x8001..0x8005` select Rei Reiho, Kyouji, Taro Tanigawa, Jiro Tanigawa,
  and Saburo Tanigawa;
- `0x0100..0x0104` use the resolved live Codename pointer;
- `0x0105` reuses the battle-name owner's `Mysterious Man`; and
- ordinary valid IDs read the Compendium-owned 319-row name table.

Invalid IDs delegate to the original fixed FONT8 renderer. Neither CHARNAME
nor DVLNAME is rewritten, and the unrelated grid remains on its stock path.

This screen needs a smaller raster than the Ark12 battle panels. Ark Pixel 10
is projected into the checked blank EVE member-5 range `0x1155..0x11b3`. The
95 glyphs retain the repository's existing packed printable-ASCII storage
order, so this is a distinct raster face rather than a new text encoding. Its
private 95-byte advance table is stored beside the wrapper.

Each successful EVE draw handle is appended to the bounded shared UI-frame
pool already installed by command help. The frame hook releases the previous
visible frame before the six cards are rebuilt, including the final frame when
COMP closes.

Names begin six pixels inside each 128-pixel card and have a checked 112-pixel
field. The Ark10 baseline keeps descenders above the HP sprite. Normal and
selected cards preserve their original tint behavior.

The wrapper and tables occupy the checked source-zero `.data` partition
`0x001c23f4..0x001c2740`. The one replaced JAL retains its relocation. Tests
pin the complete caller inventory, excluded grid, source cave, four-write
payload, full reachable name widths, shared owners, and Ark10 output.
