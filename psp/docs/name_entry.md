# PSP NAME/profile entry

The NAME slice ports the mature five-field English profile controller while
keeping authored wording in `assets/text/ui/profile_entry.json`. First name,
last name, codename, city, and ward are independent eight-byte persisted rows;
the three UPPER/lower/SYMBOL grids and six occupations use the same canonical
asset.

The runtime installs 142 source-guarded writes. It expands the native screen
state, replaces the grid and label data, rebuilds profile caches on load and
commit, and redirects every proved EVENT/UI reader to the durable English
cache. The code and tables use 3,697 bytes of the checked 3,936-byte NAME
partition inside the larger EVENT allocation.

The live eight-cell input rows center each proportional glyph inside its cursor
cell. On confirmation, the same buffer drawer switches to accumulated VWF
placement for the five profile values and selected occupation. The native
character grid uses ink-bound offsets published by the font build, matching the
Saturn polish without assuming that the preserved PSP glyphs share its metrics.

NAME introduces no new alphabet. Persisted profile bytes and proportional
labels use the shared packed-English mapping from `text/util/event_packed.py`;
the visible input grid projects those same characters onto fixed native
KANJI.FON glyph IDs. This distinction keeps the binary layouts separate while
retaining one printable-ASCII authority.

The EVENT runtime is an explicit build dependency because translated name
tokens consume the rebuilt cache. Savedata is intentionally downstream: its
SFO detail formatter decodes the codename from this English profile layout.
