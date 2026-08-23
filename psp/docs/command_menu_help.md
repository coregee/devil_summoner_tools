# PSP command-menu help contracts

Command help is one composed text/font/runtime surface rather than a text-only
archive edit.

- `regdata.bin` member 14 contains 57 fixed records of 42 big-endian words.
  Command help owns slots 0–44 and 54–56; CONFIG retains slots 45–53.
- Printable ASCII maps bijectively to the checked source-blank EVE KANJI tiles
  `0x1E20..0x1E7E`. Ark Pixel 12 is rasterized into member 5 of
  `eve_files.bin`; member 6 supplies the unchanged grayscale palette.
- The 95-byte advance table is derived from the generated tiles. Space advances
  three pixels; visible glyphs use their ink width plus one, capped at fourteen.
- The draw hook at `0x0003D6E8` preserves the stock renderer for unowned codes
  and routes owned EVE codes through the retail retained-glyph allocator.
- The frame hook at `0x00000598` releases only tracked handles after the stock
  transient reset. Invalid handles are ignored and overflow is released
  immediately.

Both hooks retain their stock relocation records. Every call preimage, delay
slot, source archive/member identity, blank cave span, generated hash, and
same-size ISO extent is checked before publication.
