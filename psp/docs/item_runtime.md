# PSP active-item runtime

The active-item slice publishes the three PSP-authored ITEMNAME additions:
game IDs `255` (Back-Upper R), `280` (Death Tally), and `281` (Demon
Compendium Extra Volume). Semantic text lives in
`assets/text/items_psp.json`; `text/config/item_runtime.json` binds those
entries to their exact native rows in `regdata.bin` member 4.

The native 29,848-byte ITEMNAME member remains unchanged. Its member hash,
record hashes, metadata, and complete 16-byte source names are validation
inputs. ID 255 receives an additional live source-name check because the stock
executable uses that row as a scratch destination.

The engine installs 13 checked BOOT writes covering both shared item-name
helpers, the description helper, category-two detail routing, and EVENT control
`0x8018`. Non-owned IDs return to the stock readers. The runtime stores 238
bytes of packed text in a checked cave and reuses the EVE width table, glyph
atlas, and Compendium packed renderer; it owns no font data itself.

Direct ITEMNAME readers excluded by equipment kind, item ID, or scratch-copy
ownership remain stock. Source function hashes, hook preimages, relocations,
and blank cave ranges make that reader inventory fail closed when applied to a
different executable.
