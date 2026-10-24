# Saturn text

This package extracts text records from the Saturn discs and repacks
translated text into them. It's organised around records:

- a **source** says where records live on the disc;
- a **container** says how they're framed (pointers, terminators, padding);
- each record names the **source encoding** that turns its code units into
  readable text. Encodings are never tied to a particular game file.

Repacking runs the same pieces in reverse. The general `event.dialogue`,
`battle.negotiation` and shared `battle.ui` text, plus the shop/facility part of
the mixed `SHOPSMP.EVE` bank, are compiled from the shared assets. Containers
handle pointers, terminators, capacity and round-trip checks.

The translation itself lives in `assets/text` at the repository root. The
extracted corpus here is reference data, not something to edit.

> **Hashes and sizes in this document** describe the build before the 2026
> translation review, which changed much of the wording. The test suites hold the
> current values; treat the figures here as illustrations of what is checked.

## Layout

- `config/encodings.json`: alphabets, control codes and source encodings.
- `config/surfaces.json`: measured Japanese and English display limits for each
  screen.
- `config/glyph_sets.json`: stock glyph sets kept for non-FONT8 systems, such
  as the KANJI name-entry grid. For FONT8, the alphabet is chosen per text
  field.
- `config/event_scenes.json`: scene groupings for the general event banks,
  where there's something in the data to justify them.
- `config/sources/<disc>/manifest.json`: physical files, the four container
  types, defaults, and per-record overrides.
- `corpus/<disc>/`: the extracted records (regenerated identically each time).
- `bindings/`: links Saturn records to fields in the shared assets.
- `../../assets/text/`: the translation, shared across platforms.
- `util/`: config loading, tokens, codecs and container helpers.
- `generated/` (ignored): compiled banks, build bindings, inventories and other
  data passed to the engine.
- `extract.py`: verifies the source disc and regenerates the corpus.
- `event_inventory.py`: writes an (ignored) scene-sorting report for the four
  general event banks.
- `repack.py`: builds general EVENT, shop/facility dialogue, battle
  negotiation, the file-based battle and ritual text, and the COMP help/name
  tables.

Extraction always reads from the verified original disc, never from the
writable build mirror. That way the mirror can hold translated text, engine
patches, fonts and graphics without changing the corpus or making extraction
tests go stale.

A corpus record looks like this, and should stay this small:

```json
{
  "id": "stable-record-id",
  "source_encoding": "game_font12_16_event_skip",
  "output_encoding": "",
  "reference": "Original text{n}",
  "translation": "",
  "note": ""
}
```

Records aren't deduplicated by content. Physical copies, and the three
intentional `NAME.BIN` translation forks, are listed in the source manifest.

### Event scenes

The general event banks hold 1,103 messages with 2,028 pages between them, but
the binary layout doesn't tell you where one scene ends and the next begins.
Running `python saturn/text/event_inventory.py` writes
`generated/event_scene_inventory.json`, which groups pages by the message they
belong to and records speaker cues, tokens, and where each page is already used
in the assets. Scene, location, story-state, choice and call-site fields stay
blank until an entry in `event_scenes.json` fills them in.

All four general event banks are done: the 1,103 messages and 2,028 pages are
assigned to 92 scenes and bound to the shared assets, with no unclassified
messages or unbound pages left. The report is a working aid, not an asset, and
one message isn't assumed to equal one story scene.

### How the assets are organised

Assets are grouped by game entity and by screen, not by the file a string
happens to sit in:

- Item and equipment names, descriptions and battle-console forms stay with the
  item. MAZE suffixes become full field-message templates with typed
  placeholders.
- Locations: 144 records plus 288 separately indexed ELV/KAI copies boil down
  to 24 places, plus three automap forms that can be edited separately and full
  floor/location templates.
- MAZE and AUTOMAP share the same Yes/No choices. `(No data)` and `Delete?`
  belong to AUTOMAP.
- Seven extra save-screen places, plus the shared Mount Kasagi entry, cover the
  eight special SAVE/LOAD labels without duplicating them. Each record checks
  that both executables hold the same bytes.
- The mixed SHOPSMP bank is split by use: facilities, demon joining, debug UI
  and the race catalogue each have their own lines.

Bindings keep the exact physical location of each record, but file offsets and
table indices never become part of an asset's ID.

### Horoscope and credits

The eight `HOSI.BIN` messages bind to `assets/text/ui/horoscope.json` and the
`horoscope.message` surface. The game's renderer gives three 20-cell FONT16
rows and a 64-word stream that's revealed progressively. The engine only adds
line breaks at word boundaries and moves the full messages into an unused
(zero-filled) area of the overlay.

The 40 `END_ROLL.BIN` records bind to `assets/text/credits/names.json`:

| Surface | Records | Cells | Destination width |
| --- | --- | --- | --- |
| `credits.main_name` | 28 | 6 | 96 px |
| `credits.test_name` | 12 | 7 | 112 px |

Both take names of up to 18 FONT16 glyphs. The engine draws the name as one
proportional row and only scales it down if it's wider than the 96- or 112-pixel
destination.

## Extraction

```powershell
python saturn/text/extract.py game
python saturn/text/extract.py game --check
python saturn/text/extract.py compendium
python saturn/text/extract.py compendium --check
python saturn/text/event_inventory.py
python saturn/text/repack.py event
python saturn/text/repack.py event --check
python saturn/text/repack.py shopsmp
python saturn/text/repack.py shopsmp --check
python saturn/text/repack.py negotiation
python saturn/text/repack.py negotiation --check
python saturn/text/repack.py battle
python saturn/text/repack.py battle --check
python saturn/text/repack.py comp
python saturn/text/repack.py comp --check
python -m unittest discover -s saturn/text/tests -v
```

## General EVENT repacking

The general EVENT compiler maps all 2,028 pages, through the Saturn bindings,
to 1,890 asset fields. It rebuilds `MESFILE.EVE` and `EVFILE_0.EVE` to
`EVFILE_2.EVE` together from the verified source disc. It keeps the two
messages that only contain control codes, wraps the FONT16 dialogue to the
`event.dialogue` limits, keeps the menu records that are read directly, and
re-parses every output.

`config/event_codec.json` holds the fixed dictionary used by the earlier
Saturn build. `generated/game/event_build.json` records that codec, the current
FONT16 metrics, and the digest of each rebuilt bank. All four outputs are
byte-identical to the earlier Saturn translation build. That's checked as a
regression test, not assumed from the strings matching.

## Portrait-scene EVENT consumption

`MSGR.COF` doesn't have its own dialogue bank. Its portrait-scene code loads
`MESFILE.EVE`, `EVFILE_0.EVE` to `EVFILE_2.EVE`, and `SHOPSMP.EVE`, so its
dialogue and choices come straight from the EVENT compiler output and use the
same `event.dialogue` and `event.choice_option` limits. There's no MSGR-only
text asset or repack output.

Inserted names come from the shared catalogues too: all 319 demon names, all
43 race names, and the character names Hajime, Rei and Kyouji can appear in
dialogue. The code still packs all six CHARNAME rows to keep the table layout,
but the character-insert handler only accepts indices 0–2. First name, last
name, codename, city and ward are EVENT placeholders filled from the shared
player data. MSGR's own race table is another physical copy of the same 43 race
fields. The earlier build's eight-byte UMA compatibility edit stays as the
existing `game.normcom_tables.races.r0022` record, not a duplicate asset.

Three English diagnostic messages are handled separately, because MSGR draws
them with a built-in fixed-cell ASCII tile set. They're in `system/debug.json`
and `bindings/portrait_scene_debug.json`:

| Message | Allocation | Max visible ASCII |
| --- | --- | --- |
| `NAME TO ID ERR` | 16 bytes | 15 |
| `LOAD ERR` | 10 bytes | 9 |
| `ERROR: MENU COUNT OVER` | 24 bytes | 23 |

Each needs a trailing NUL. The `portrait_scene.debug_message` surface is one
64-cell row; its font is `null` because the glyphs don't come from FONT8 or
FONT16.

## Shop and facility EVENT repacking

`SHOPSMP.EVE` is a mixed bank, not a separate shop renderer. Its dialogue and
its directly drawn FONT16 menu records use the same EVENT code installed for
`event.dialogue`.

The `shopsmp` target maps all 763 translatable pages, compiles the standard
dialogue and all 193 translatable direct-FONT12 Fusion pages, and re-parses the
whole 815-message bank. The one Fusion message that only holds control codes is
kept as-is. `generated/game/shopsmp_build.json` records zero deferred pages and
ties the output to both the FONT16 and FONT12 metrics. The Goofy shop line at
message 741 is pinned to the earlier Saturn build's output.

The matching `fusion.menu` engine target installs the FONT8/FONT12 renderers the
direct records need. The short chart labels have their own editable race
fields; they aren't treated as file-local text or cut down from the longer
table labels.

The `EVENT.BIN` status and facility screens use the same catalogues rather than
a separate text file. The manifest covers:

- all 43 race rows at `0x54828`;
- all 96 affinity rows at `0x5492a`;
- all 16 drink rows and all six patron rows;
- the healer's separate all-members text.

The earlier build edited exactly race 22 and affinities 1, 29, 51, 52, 60, 64,
and 66 to 95 directly in the table: 37 EVENT copies, each mapped to its existing
race or affinity field. Demon, character and ability names still come only from
`DVLNAME.DAT`, `CHARNAME.DAT` and `MAGNAME.DAT`.

Facility list widths:

| Field | Font | Width |
| --- | --- | --- |
| Drink and patron rows | FONT8 | 64 px |
| Shared character/demon list | | 104 px max |
| Healer's all-members line | | 144 px |
| Detailed name | FONT16, 8 cells | 126 px (same as the demon name) |

No wording is duplicated in renderer code.

## Battle-negotiation repacking

The negotiation compiler rebuilds `BOSSTALK.EVE` and all fifteen personality
banks from 9,920 bound pages. Six more messages only contain control codes and
are copied unchanged. Every rebuilt bank is byte-identical to the earlier
Saturn build.

The same target compiles 113 condition messages and four provisioning labels
into `COMBAT.BIN`, and builds the whole `ITEMNAME.DAT` catalogue so item names
and descriptions inserted at runtime always come from one place. The engine
stage takes this generated `COMBAT.BIN` as input; the normal build installs the
engine's final output, not this text-only intermediate.

## Shared battle UI repacking

The `battle` target rebuilds the six files used by the shared battle code:
`BTL_MES.MD8`, `BTL_SRF.MDT`, `BTL_HELP.DAT`, `ITEMNAME.DAT`, `MAGNAME.DAT`,
and the ritual console's `BUTU_SRF.MDT`. It fills in:

- 313 visible small-font console rows;
- 203 visible Demon Chat rows;
- all 19 help records;
- all 542 item and ability records, with separate names and descriptions;
- 64 visible ritual-console rows.

Remaining pointer slots are left alone. BTL_MES has 29 unbound blank rows and
one blank row that is bound on purpose; BTL_SRF has 160 blank rows.

The byte and word pointer banks are compacted into their translated body
locations and re-parsed with exact capacity checks. Item and ability names go
into unused description padding and are selected by the earlier build's
per-record pointer, without changing the 96-byte record size. All six outputs
are byte-identical to the earlier Saturn build. There's no hand-written
fallback text.

## COMP-core repacking

The `comp` target rebuilds `NORMHELP.DAT` and `DVLNAME.DAT` from the same assets
used by battle, Fusion and the Compendium. All 24 help records use the measured
300-pixel, two-row COMP layout and keep their fixed 42-word size. Of the 319
demon names, 210 fit the game's eight-byte/64-pixel slot and are written into
`DVLNAME.DAT`. The other 109 keep their original bytes there, and the COMP
party-panel code draws the full name from a separate overflow pool. Both
outputs are byte-identical to the earlier Saturn build.

That split is about storage, not editing. Every demon still has one full name
in `assets/text/demons.json`; the repacker and runtime decide where it can be
stored without being cut off.

### Game corpus

The game manifest covers 162 files in 62 source groups. Its four container
types are EVE banks, pointer banks, fixed records with subfields, and addressed
spans. The generated corpus has 16,141 records: 12,711 EVE pages with text and
3,430 other records.

**Dungeon locations.** All 144 location rows stay separate rather than
collapsing into 24 repeated Japanese strings. Each row checks that its name
bytes match across the MAZE, AUTOMAP, SAVE and LOAD tables; those four copies
still make one catalogue record.

**SAVE/LOAD.** `Lv`, `YES`, `NO`, the date slash, the time colon and the
basement-floor template are all records. Identical EMPTY, special location,
`Lv`, punctuation and floor copies are checked in both SAVE and LOAD, not
assumed from one file. The three-cell LOAD capacity record at `0xB1AE` is
catalogued on its own.

**MAP2D.** All 14 records are covered, not just the five fixed destinations and
three talk fields. The default ward and city rows are split from their suffixes
and reuse the Profile Entry defaults; the duplicate `区` and `市` spans are each
checked as one record. The full-map `全図` suffix maps to a full world-city
template rather than being blanked. The standalone `雲` (cloud) record is
editable but still unidentified. MAP2D has its own bindings that reuse the five
shared location fields and the shared field prompt and choices. Only
`Mount Kasagi` gets a short form, `Mt. Kasagi`, for the 64-pixel destination
strip.

**ELV and KAI.** 56 landing records across 17 ELV files and 232 records across
all 98 KAI files are separate corpus entries. Exact offsets, file hashes,
text-region hashes and a digest of the KAI file list all have to match. Every
record maps back to an existing place rather than adding another translation.

**Records added by the consumer audit.** Four source groups, holding five kinds
of record that the earlier registry missed:

- all 66 separately indexed Combat Analyze affinity slots;
- two padded combat-result labels;
- 16 EVENT drink names and six Talk-role labels, from one EVENT bar group;
- one healing all-members label.

Equal short affinity values stay as separate records, like the repeated
dungeon locations; assets can share them later. The healing label is built from
the seven FONT16 glyph-index bytes its renderer reads from code.

**Status.** 24 separately addressed ASCII records from `NORMCOM.BIN`: nine
readout prefixes, the four control ranks plus the game's fallback, three party
alignment values and seven AUTO command values. Their bindings keep full
editable templates such as `HP {current_hp}/{maximum_hp}` and `CTRL {rank}`, so
punctuation and word order aren't left in renderer code.

**DA_3D Analyze.** 60 more records: all 43 short FONT8 race rows, seven grid
headings, four detail prefixes, two skill-cost units and the four stored
alignment-axis labels. The game's single `L` record binds to both the Law and
Light fields, which can be edited separately. The M and H records are suffixes
of full cost templates, and the grid and detail LV/HP/MP/CP records reuse the
shared status templates. Every visible Analyze label comes from an asset.

**MAZE acquisition suffix.** The suffix at `0x251dc` is used three ways:
getting an item, yen, or magnetite. The two currency paths add source glyph
`0x00c0` (yen) or `0x00c1` (magnetite) and the amount before the shared suffix.
The binding therefore splits into separate item, yen and magnetite templates,
so the wording and symbol choice aren't left to runtime code.

### Compendium corpus

> The *Akuma Zensho* build is currently broken in game. The extraction
> described here works; the translated disc doesn't.

The compendium manifest treats the 292 `DVL_*.DAT` profile files as one
repeated fixed-record source. Each file gives origin, summary and detail fields
from the text at its end. Focused `A_DIC.BIN` sources cover:

| Table | Address |
| --- | --- |
| 319 demon names | `0x5d9b0` |
| 255 ability names | `0x69be4` |
| 48 race labels | `0x5eda0` |
| 48 heading-and-description layouts | `0x6abd4` |
| 11 two-row fusion-help records | `0x6d828` |
| 6 single-cell base-stat labels | `0x69a70` |
| 6 four-cell derived-stat labels | `0x69b16` |

Together they give 1,617 records in eight generated catalogues. The DVL checks
only cover the text at the end of each file, so the profile images can change
later, but any change to a text byte still fails.

**Layout.** `A_DIC.BIN` loads the selected profile at `0x00210000`. Origin is
one 144-pixel row, summary is four 224-pixel rows, and detail is twelve
224-pixel rows. Summary starts at the last origin-layout word (`0x7801c`) and
detail at the last summary-layout word (`0x7808c`), so those two leading zero
words are layout, not authored whitespace. The 0x1dc-byte text block ends
right after the twelfth detail row.

**Font.** The stock compendium font has no free glyphs: code zero is the only
blank cell, and the other 2,047 cells are all in use. Instead of overwriting
Japanese UI glyphs, the engine uses a reversible compact-row codec: a fixed
64-entry dictionary plus a tagged five-bit stream. Every profile paragraph,
fixed A_DIC name, race-description row and fusion-help row has been tested and
fits its pixel layout and existing storage. The description layouts keep their
leading graphic marker outside the text; three NO DATA layouts keep their prose
rows empty on purpose. Vengeful Spirit and Fiend are translated. Two separately
addressed race placeholders are left byte-identical to the original until it's
clear what they are.

### Corpus rules

`corpus/<disc>/` is a generated catalogue; its file grouping isn't meant for
editing. Earlier translations are only imported into the shared assets once a
binding is confirmed. Stable record IDs mean the asset layout can change
without losing track of the physical data.

The extraction manifest only holds what extraction needs. Output-side packing
for general EVENT is in `config/event_codec.json` and `util/event_repack.py`;
the matching renderer and fetch hook are in `saturn/engine`.

IDs come from pointer slots, fixed-record positions, addressed offsets, or EVE
message/page positions. EVE page numbers include the 166 pages that only hold
control codes and don't produce records. IDs never depend on the Japanese text
or on a relocatable address.

Extraction checks full stock hashes for files that only hold text. Shared
executable overlays also carry a digest over just their text regions, so
unrelated graphics or engine changes don't break it. The current `SAVE.BIN` and
`LOAD.BIN` graphics changes pass for that reason; changing any text byte still
fails.

Only `translation` and `note` are kept between runs, by record ID. Reference
text, encodings, ordering and JSON formatting are regenerated. Orphaned IDs,
overlapping sources, changed framing, stale generated fields and unmanaged
corpus files are errors. `--check` doesn't write anything.

## Encoding boundaries

An alphabet maps glyph indices to readable characters. Font-based alphabets
are loaded from the per-disc font definitions, so the game's and the
compendium's `FONT16.FON` can't get mixed up. Small custom code tables are
defined in the same central place, not inside a source. A source encoding
combines one or more alphabet ranges with a code-unit codec and a set of
control codes. That covers the game's 8-bit tables, 16-bit EVENT and combat
text, the two-font 8-bit battle-message alphabet, and indexed config labels,
without tying any of them to a file.

Each encoding says how it treats zero. Mixed-font dialogue skips zero words;
FONT12 and directly drawn fixed records may treat each zero as a space. Fixed
and mirrored tables use separator modes that ignore leading and trailing zeros
and collapse each run inside the text to one space or newline.

Only formats actually found on the discs are configured: big-endian 16-bit
glyph words, 8-bit glyph codes (including FONT16 indices stored as one-byte
operands), and printable ASCII. No Saturn source uses Shift-JIS.

The compendium font is separate from the game font. Its mapping covers all
1,703 nonzero glyph codes used in the 292 profile tails. Three Unicode values
each appear at two physical codes (six codes total), so their 29 occurrences
are kept as `{GLYPH:xxxx}` tokens rather than losing which code was used. This
mapping doesn't imply a replacement font: the compact renderer only embeds the
narrow Latin glyphs it needs and leaves `FONT16.FON` untouched.

Containers strip terminators and padding; codecs only apply the encoding's
zero rule. That lets one encoding work across fixed fields, pointer tables and
mixed record files.

## Text tokens

Decoded text stays readable while keeping anything that can't be safely mapped:

- `{n}`, `{WAIT}` and `{first_name}` are named controls or glyphs.
- `{GLYPH:0342}` is an unknown or ambiguous 16-bit glyph.
- `{OP:801e}` is an unknown 16-bit control code.
- `{{` and `}}` are literal braces.

Raw 8-bit values use two hex digits. Unknown controls are never dropped, and
duplicate atlas values stay raw so the original code isn't lost.

A binding can tie a full runtime template to a stored record with
`composition.source_role: "scaffold"`: removing the template's placeholders
must leave exactly the stored bytes. That's how the SAVE/LOAD `Lv`, slash,
colon and `地下…階` records are matched without separate fragment assets.

`substitutions` covers a different case, where one stored record fills in
another asset field that has no placeholders. SAVE/LOAD uses it to put the
single `capacity_number.text` value into every capacity message. Substitution
works on parsed tokens, so escaped braces can't be rewritten by accident.

## Consumer limits

`config/surfaces.json` describes how much text each screen can show. It isn't
a list of text or of storage. Each surface has separate `ja` and `en` layouts
with a font, a row count, and a width in either glyph cells or pixels. A layout
can also set a `glyphs` limit when a proportional renderer has both a pixel
width and a fixed-size row buffer. `null` means the limit hasn't been measured.
The loader rejects missing fields and half-specified widths, so an unknown
value can't turn into a guess.

### Event and battle

| Surface | Japanese | English |
| --- | --- | --- |
| Event and negotiation windows | | 300 px × 3 rows (separate surfaces) |
| Battle console | 16 cells × 3 rows | 16 cells × 3 rows |
| Demon Chat | 11 cells × 2 rows | 176 px × 2 rows |
| Battle help | 20 cells × 2 rows | 300 px × 2 rows |
| Battle item, skill and party names | | 80 px |
| Analyze names and short affinities | | 112 px |
| Analyze race heading | 8 cells, FONT8 | 8 cells, FONT8 |
| Result name | | 88 px |
| MSGR diagnostic writer | 64 cells × 1 row | 64 cells × 1 row |
| Ritual console | | 176 px wide; rows `null` |
| Negotiation choice | 10 cells × 1 row | 150 px × 1 row |
| Negotiation two-way choice | 15 cells × 1 row | 240 px × 1 row |

The MSGR diagnostic tiles aren't FONT8 or FONT16, and its three strings have
their own 15-, 9- and 23-byte limits.

Negotiation choices are read from each personality bank's script (see
`negotiation_choice_messages` in `util/battle_negotiation.py`) and tagged in
the bindings' `record_surfaces`. Three- and four-way choices sit in a
two-by-two grid of 150px columns; the game clips anything wider, and the
build fails on it. The editor also warns past 142px. Two-way choices have
Japanese options up to 15 cells, so they get a 240px limit: the widest the
original is known to use, not a measured maximum.

### Locations and SAVE/LOAD

Location widths:

- 3D map name: 64 px × 2 rows, with a 64-pixel floor row;
- automap: 112 px after the marker icon drawn by the game;
- special SAVE/LOAD location: 112 px;
- generated dungeon label: 144 px.

SAVE/LOAD limits (English):

| Field | Pixels / cells | Max glyphs |
| --- | --- | --- |
| Special / dungeon location | | 16 / 24 |
| Joined name strip | 128 px | 17 |
| Level | 4 cells / 64 px | 4 |
| Date and time | 5 cells / 80 px | 5 |
| EMPTY | 5 cells / 80 px | 5 |
| Prompt | 11 cells / 176 px | 11 |
| Confirmation choice | 3 cells / 48 px | 3 |
| Small messages | 3 rows × 11 cells / 176 px | 24 per row |
| Capacity messages | 2 rows × 17 cells / 272 px | 25 per row |
| Warnings (4 and 6 rows) | 20 cells / 320 px | 63 per row |
| Capacity value | | 3 |

Because of the glyph limits, fitting the pixel width isn't enough for unusually
narrow text. The heading and storage-selector text is part of the artwork.

### MAP2D, MAZE and AUTOMAP

MAP2D (all FONT16):

- world-city box: 6 cells / 96 px;
- destination strip: 4 cells / 64 px;
- combined area box: 8 cells / 128 px;
- field prompt: 14 cells / 224 px;
- choices: 3 cells / 48 px, max 3 glyphs.

The earlier renderer's 64-pixel dynamic part, and hiding the city name on the
area screen, are engine behaviour, not smaller surface limits. The cloud row
next to these has no surface until it's clear what uses it.

MAZE talk choices are one 48-pixel row. The three-row AUTOMAP marker popup is
64 pixels per row in English. Other English limits are unknown until their
renderers are measured.

### Facilities

Facility surfaces cover the eight-cell bar and healer lists, the two-row drink
help, and the shop's 16-pixel `Inv.` label. Unmeasured facility widths are
`null`.

### Profile entry

- Stock input limits are three/three/eight/three/three. The English patch
  allows eight characters for first name, last name, codename, city and ward.
- `player_profile.json#full_name_storage.text` gives Profile Entry and
  SAVE/LOAD one shared 17-cell `NAME_FW_FULL` format. The visible save-slot
  name is a separate template. The stored format allows either name order,
  each placeholder exactly once, around one supported separator glyph.
- The two confirmation fields have their own positions.
- The prompt is 168 px / 11 glyphs; the confirmation question is 176 px / 11
  glyphs.
- YES and NO are each 48 px, max three glyphs.
- English input rows use up to 13 cells inside the 19-column `KANJI.FON` grid
  and use its `ark_latin` glyph set. The Saturn renderer uses the generated ink
  bounds to centre the 16px Ark glyphs in their cells at runtime.
- The two-cell END key is a FONT16 action, not grid text.
- Other widths: 96-pixel tab bands, 128-pixel occupation columns, eight-cell
  defaults, and a 208-pixel confirmation value area.
- The unused English address suffixes have no known width until a renderer uses
  them again.

The storage template has no source binding, since the game stores no separate
template record. Both runtime builders load the asset directly and include it
in their input list.

### Character names, Level Up and status

- Party-panel name pool: 80 px. Shop information field: 72 px.
- Level-up character texture: eight Japanese cells, 96 px safe limit in
  English (from the earlier build). The Level Up name texture gives the five
  fixed character names 96 px and the live player codename the full 128-pixel
  row.
- The LEVEL_UP title, remaining-point display, accept action and confirmation
  choices use fixed FONT8 slots.

Status screen:

| Element | Limit |
| --- | --- |
| Compressed parameter nodes | 12 px |
| Derived and combat-stat rows | 46 px |
| Loyalty / personality rows | 38 px |
| Stock Japanese labels | 1–4 cells each |
| TYPE label | 4 cells, FONT8 |
| CTRL ranks | 3 cells, FONT8 |
| AUTO values, party alignments | 7 cells |
| Alignment axes | 1 cell each |
| AUTO and P.A. rows | 12 FONT8 cells, value starts at x=40 |
| CTRL row | 10 cells, rank starts at x=56 |

These rows are composed: the cells between a prefix and its value are spacing,
not extra room for text. Numbers start at x=40 for LV/CP, x=80 for EXP/NEXT,
and x=40/48/80 for the HP/MP current value, separator and maximum. Their right
edges aren't known yet, so `status.numeric_readout` has no width. The Loyalty
number starts at x=72 after its 38-pixel label, and its right edge is also
unknown. TYPE and its 38-pixel personality value are separate pieces and can't
borrow space from each other.

### 3D-map Analyze

The Analyze grid is a FONT8 screen on a 352-pixel raster.

| Header column | x | Width |
| --- | --- | --- |
| 1 | 28 | 52 px |
| 2 | 80 | 76 px |
| 3 | 156 | 46 px |
| 4 | 202 | 34 px |
| 5 | 236 | 28 px |
| 6 | 264 | 36 px |
| 7 | 300 | 52 px |

Sixteen rows start at y=32, 12 pixels apart. Race and name get 52 and 84 pixels,
before the values at x=164, 208, 244, 280 and 316.

The selected-demon detail view has 126 px for the FONT16 name, 46 px for the
FONT16 race, a 96-pixel number row, six 80-pixel FONT8 skill names, 16-pixel
cost forms, and the existing 128-pixel two-row affinity area.

The Learned Magic texture is 144x32 with two FONT16 rows. The heading is five
Japanese cells, or a cautious 128 px in English; the ability row is eight
Japanese cells or 128 px in English.

### Options

The options menu keeps its nine-cell label and four-cell value limits; English
widths are unknown. The ordering popup has four 80-pixel rows, controller
actions one 128-pixel row, and the two footer states one 144-pixel row. Compound
glyphs and action-atlas chunks are generated from the text, not separate
limits.

### Choosing the FONT8 alphabet

Each FONT8 translation picks its typeface:

- `"font8_alphabet": "original"` uses FONT8's stock `stock_latin` set and
  uppercases letters when drawing. Menu labels such as `GO`, `COMP`, `BUY`,
  `EQUIP`, `REPEAT`, `OFFENSE` and `LEVEL UP` use this.
- `"replaced"`, or leaving it out, uses the language project's replacement
  font. Names and ordinary text use this, including the shop's `Inv.` label.

Named tokens are never uppercased. The stock set also provides the hyphen, full
stop and slash used by fixed number fallbacks. The `name_entry.grid_row`
surface uses the KANJI `ark_latin` set instead.

### LEVEL_UP records

Extraction covers all eleven visible records: the FONT8 `LV`, `HP`, `MP`,
`EXP`, `NEXT`, `LEVEL UP`, `LEFT`, `YES`, `NO` and `OK` fields, plus the FONT16
`魔法を習得` heading. The stored `LEFT` and `NO` start at their first letter,
so the four ornament cells and one centring cell before them are layout, not
spaces in the text.

The five number prefixes use the shared status templates. The rest bind to
`assets/text/ui/level_up.json`, including the remaining-points template and the
earlier translation `Learned Magic`. That file also holds the `-------`
(max level) and `---/---` (no MP) fallbacks the game builds at runtime; the
spacing cell after the slash is renderer layout. These have no corpus IDs
because the game doesn't store them as text.

### Command words

The catalogue includes the 16-entry battle action table at all three locations
(COMBAT, MAZE and NORMCOM), the four item/skill actions, the five COMP
commands, and twelve shared facility commands. The combined stock glyphs used
for `REVIVE` and `STATUS` are handled by binding maps rather than the general
decoder.

The main battle commands `FIGHT`, `TALK`, `ESCAPE`, `AUTO`, `PRESET` and
`REPEAT` have no text records in COMBAT after searching all storage and call
sites. Their English lettering is treated as graphics/font data, not given a
guessed text binding. The command fields in the assets are there for when that
artwork gets migrated.

COMBAT builds its party-state rows in code. Their text comes from
`assets/text/battle/party_panel.json`: `EMPTY` and `IN PARTY`, with five- and
eight-cell limits and FONT8's stock `stock_latin` set.

### Diagnostics

SNDTEST and TEST3D have eleven on-screen fixed-cell diagnostic fields. They're
in `assets/text/diagnostics/sound_test.json` and
`assets/text/diagnostics/test_3d.json`, bound to their addressed records, and
compiled as ASCII plus a NUL into the 7-, 8-, 11-, 17- or 19-cell fields.
Trailing spaces that matter are kept.

## Current implementation

Extraction checks the source disc files, decodes every record, keeps unknown
glyphs and controls intact after applying the zero rules, and keeps
translations by record ID. The catalogues hold 16,141 records from 62 game
source groups and 1,617 records from eight compendium source groups.

The file-based repacker has five selections that can each be checked on their
own:

| Selection | Generated text outputs |
| --- | --- |
| `event` | The four general EVENT banks |
| `shopsmp` | The shop, facility, and Fusion EVENT bank |
| `negotiation` | All sixteen battle-negotiation banks |
| `battle` | Battle help, console, Demon Chat, ritual, item-name, and ability-name files |
| `comp` | COMP help and direct demon-name tables |

`all` builds all five. Each one reads the verified source disc, follows the
bindings, enforces storage and display limits, and re-parses every record
before writing.

Text stored in executables is compiled by `saturn/engine`. That covers
Profile, MAP2D, Horoscope, Credits, the diagnostic overlays, portrait scenes,
Options, Level Up, detailed status, facilities, Save/Load, MAZE and battle
text. The *Akuma Zensho* text (all 292 profile tails plus the A_DIC demon,
ability, race-label, race-description, fusion-help and status-label tables) is
built by `compendium.text`, though that build is currently broken in game.
These engine builds use the same assets, bindings, corpora, encodings and
surface limits; they aren't separate translation systems.

## Remaining boundaries

- The main battle command words are graphics/font data, since no text record or
  code-built string was found. Their assets are ready for when the artwork is
  redone.
- The MAP2D cloud record and two compendium race rows are still unidentified
  and aren't bound to guesses.
- Words baked into title, menu, selector and environment artwork still need to
  be tied to text assets where there's no generated version.
- `null` surface limits are measurements still to be taken; they don't mean the
  screen hasn't been translated.
- PSP text is handled in `psp/text`, and Saturn FMV subtitles are built by
  `saturn/engine`, not this package.

This package doesn't bring back the old format-class tree, global registry,
content-based Japanese deduplication, or migration wrappers. Its tests cover
extraction, assets, bindings, surface limits, packing round trips, and
cross-package freshness manifests.
