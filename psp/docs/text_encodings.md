# PSP text encoding ownership

The PSP build has three authored text-codec families. Surface-specific files
own physical layouts, capacities, and control vocabularies; they do not define
new glyph alphabets merely because they store the same alphabet differently.

## Shared EVE printable ASCII

`text/util/event_packed.py` is the sole authority for the 95 printable ASCII
assignments, prose normalization, packed-byte storage order, runtime glyph-code
bias, and the common `0x8000` message terminator.

The same assignment has two physical projections:

- packed one-byte glyphs for EVENT, BOSSTALK, Demon Compendium prose and names,
  and the three PSP-only active items;
- direct big-endian u16 runtime glyph codes for CONFIG help, command help, and
  direct-reader EVENT options.

The EVE font package consumes this codec to populate its atlas and produces the
advance table. It no longer defines a parallel character-to-code map.

EVENT and BOSSTALK remain separate control dialects. Their opcode vocabularies
belong to different VMs, but their literal glyphs share the EVE codec.

## Native FONT16 u16 text

`text/config/title_help.json` is the authority for the native FONT16 mapping
used by the title-help member. The title font builder derives its owned raster
subset from that mapping instead of repeating character/code rows in font
configuration. CONFIG extends that same title allocation for its Ark12 mode
labels.

## BTL_MES bytes

`text/config/btl_mes.json` remains independent. BTL_MES has a distinct u8
alphabet, terminator, named controls, verified operations, and 16-cell record
limit; folding it into EVE or FONT16 would erase real source semantics.

The FMV/CONFIG Ark16 allocation is a runtime glyph allocation rather than
another source text codec. Its character/code/advance table is compiled once by
the font stage and passed to the engine and subtitle placement builders.
