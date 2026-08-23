# PSP savedata metadata

The savedata slice switches the PSP utility language to English and publishes
canonical game, slot, cancellation, and SFO-detail text from
`assets/text/save_load.json`. Its 24 dungeon names and the Home/Detective
Agency special cases come directly from `assets/text/locations.json`.

The runtime maps 144 physical save-location records to the 24 canonical names,
then formats the live codename, level, difficulty, location, and accumulated
playtime into the SFO detail buffer. The complete formatter template remains
an authored asset; the binding pins its placeholder order and punctuation so
the machine-code formatter cannot silently diverge from it.

Thirteen writes are guarded against the stock BOOT, including every hook,
relocation, physical location table, and three zero-backed cave partitions.
The generated data uses 1,500 of 1,505 reserved bytes; the location-name blob
alone uses 321 of its 324-byte partition.

Savedata requires `name_entry.runtime` because its codename decoder consumes
the packed-English profile bytes established by NAME. Output metadata itself
is ordinary ASCII, which is also valid UTF-8 for the PSP utility/SFO buffers.
It shares printable-ASCII validation with the packed codec but does not share
the packed binary representation or require a game-font allocation.
