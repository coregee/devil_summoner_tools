# PSP EVENT text and VWF runtime

The EVENT slice combines a stock-compatible runtime layer with a transactional
rebuild of `SHOPSMP`, `EVFILE_0`, `EVFILE_1`, `MESFILE`, and `EVFILE_2` inside
`eve_files.bin`.

The readable emitter reproduces the original 25-write runtime fingerprint. In
the new repository, command help installs the shared 95-byte EVE advance table
first, so EVENT verifies and reuses that table and publishes 24 disjoint writes.
Those writes provide:

- markerless packed-byte decoding with preserved big-endian word fallback;
- proportional pen placement for one active textbox;
- three visible rows of 120 retained glyph handles;
- guarded clear and wrap helpers for inline insertions;
- proportional two-column or stacked option geometry; and
- the expanded 319-record DVLNAME resolver.

Every generated helper is bounded by the neutral cave partitions in
`engine/core/layout.py`. The complete stock BOOT identity, hook preimages,
argument-producing delay slots, and eight retained relocation records are
validated before composition. Native EVENT pages retain their original reader
and handle geometry.

The text compiler starts from the font stage's generated archive, preserving
member 5 byte-for-byte while replacing members 0 through 4 together. Its five
compact physical bindings contain one canonical `path#entry.field` identity
per payload page. Most identities are joined through the Saturn EVE bindings;
the PSP-only tutorial, teleport, optional-battle, and constrained option text
lives in `assets/text/events/event_psp.json`. Eight pages with no translatable
payload identity remain explicit null bindings.

Packed prose wraps to 300 pixels and three visible rows. Opcode-3 choices stay
raw u16 words for their direct readers and are checked against the real 150- or
300-pixel menu geometry and shared 84-handle pool. The same 3,205-byte DVLNAME
table, resolved from 319 semantic `assets/text/demons.json` slots, is reserved
at the end of every bank. The resulting archive is the sole ISO publication
owner for `eve_files.bin`; the font-stage archive is its checked input.
