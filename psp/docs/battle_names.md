# PSP battle names

The battle name patch covers two executable-owned consumers that do not use
the EVENT text renderer: the battle party cards and the private battle-result
routine.

Five party-panel loops at module addresses `0x0002ce40`, `0x0002d3c4`,
`0x000868b0`, `0x00086c38`, and `0x0008a47c` originally draw eight fixed-width
FONT16 cells. Their shared wrapper now handles three namespaces:

- IDs `0x0100..0x0104` decode the current eight-byte packed Codename from the
  durable NAME profile;
- ID `0x0105` draws the canonical `Mysterious Man` translation; and
- other valid one-based IDs read complete packed names from the
  Compendium-owned 319-row table.

The special namespace deliberately continues to shadow physical demon rows
256 through 261. Resolver callers outside the five proved loops remain stock.
The party entry preserves its caller-provided position and tint; the other
four entries retain their fixed geometry.

The battle-result routine has two possible Codename draw sites and six fixed
label sites. Only row zero of its mixed native/packed name table is decoded as
the live Codename. Native rows continue through the original FONT16 drawer.
The fixed calls publish `(None)`, `Life Stone`, and `Bead`; the continuation
calls become no-ops so no Japanese second cell remains. Item counts and their
stock alignment are untouched.

Both consumers use the consolidated low-code Ark Pixel 12 mapping in DATAPACK
FONT16 member 9. That mapping is the union of title help, CONFIG modes, the
complete NAME input alphabet, all 319 Compendium names, and the result labels;
the battle patch adds no private encoding or raster bank.

The runtime owns checked source-zero partitions at
`0x0016f500..0x0016f700`, `0x00171700..0x00171800`, and
`0x00171e00..0x00172260`. All thirteen replaced JALs retain their relocation
records, while only the five local fixed-cell loops are skipped with
relocation-free branches.

Runtime acceptance in PPSSPP should exercise custom Codenames from every NAME
tab, ordinary and special demon IDs in each panel mode, both result-name rows,
all three fixed labels, panel transitions, target switching, tint, clipping,
and preservation of unrelated status and roster screens.
