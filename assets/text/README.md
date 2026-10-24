# Shared text assets

This directory is the translation. The JSON files here hold every piece of
player-visible text in Devil Summoner, and both the Saturn and PSP builds read
from them. Files are organised by what the text is about (demons, items, a menu,
a story scene), not by which game file it came from.

## Quick start for translators

- **Edit** the `translation` value of a field.
- **Leave alone** the `reference` value. It's the original Japanese, kept
  beside the translation so you can read it.
- **Keep placeholders** such as `{item}`, `{n}` or `{yen_symbol}` intact. The
  game fills them in at runtime. You can move them within the line, but the
  translation must use the same placeholders, the same number of times, as the
  reference.
- **Don't edit** `<platform>/text/corpus/` (raw extracted data) or anything
  under a `generated/` directory. Those are rebuilt from the files here.
- Optional keys are left out when they'd say nothing. `reviewed` defaults to
  `false`; notes, variants, placeholders and status only appear where needed.

Before changing wording, read the [style guide and glossary](STYLE.md).

The translation editor (`python -B -m tools.editor`) is the easiest way to work
on these files. It previews lines in the game font and flags anything that won't
fit.

## Ownership rule

All visible text lives here: strings, labels, fragments and whole templates.
That includes labels that were already in English, text left untranslated on
purpose, text stored inside executable code, and text drawn into images.

Game code is allowed to:

- pick an asset and one of its declared variants;
- fill in typed values such as an item, demon, location or number;
- apply a declared number format;
- measure, wrap, encode and draw the result.

Game code must not contain visible words, punctuation, word order, short labels
or translated phrase pieces. Anything derived for drawing, such as compound
glyphs or packed dictionaries, is generated from these files.

Typeface and glyph-set choices belong to the platform, not to the text. A plain
`GO` can be drawn with the old Saturn FONT8 capitals on a command menu and with
the normal English alphabet elsewhere, without storing it twice or marking it
up.

## Layers

The text system has four separate layers:

1. `assets/text` (here): reference text, translations, grouping, templates, and
   alternate forms written for specific screens, such as `console_text`.
2. `<platform>/text/bindings`: connects each field to the game data that uses
   it: records on disc, code locations, generated pools or images. Platform
   IDs, offsets, selectors and which platform a line applies to live here.
3. `<platform>/text/config/surfaces.json`: what each screen can display. Limits
   are per language and use stated units such as glyph cells or pixels.
4. `<platform>/text/corpus`: a generated, lossless dump of the original records.
   It's reference data, not something to edit.

How many bytes a record can hold on disc is a property of the file format. It's
a different thing from how much fits on screen.

## Organisation

Text about an entity stays with that entity. Dialogue, prompts, menu labels and
templates stay with the screen that shows them. The rough layout is:

```text
assets/text/
  demons.json
  equipment.json
  items.json
  magic.json
  skills.json
  characters.json
  locations.json
  terminology/
  negotiation/<speaking-style>.json
  battle/
  ritual/
  field/
  fusion/
  facilities/
  system/
  ui/
```

An entity can have more than one written form. An item can have `name`,
`description` and `console_text`; a race can have full, grid, battle and fusion
forms where those screens really need different wording. The game must not
quietly truncate one form to make another.

Some specific placements:

- System console fragments that don't belong to an entity stay with the
  console.
- Field messages such as `Obtained {item}.` stay with the field messages as
  whole sentences, even when the original file stores only the suffix. If one
  stored suffix is used in several places, the binding lists each use rather
  than forcing them into one string.
- The MAZE talk choices are next to their prompt in `field/messages.json`.
  AUTOMAP reuses those Yes/No fields; its own `(No data)` and `Delete?` wording
  is in `field/automap.json`.
- `system/debug.json` has the three diagnostics shown by the Saturn
  portrait-scene overlay. They're already English but stay editable. Their
  letters are drawn from a fixed-cell tile set inside the program, so the
  wording is here while the Saturn binding and engine handle padding and
  drawing.

### Negotiation

Negotiation text is split by the demon's speaking style. The current files are
`archaic`, `beast`, `boy`, `cynical`, `feral`, `girl`, `highborn_lady`,
`kansai`, `lady`, `little_girl`, `manic`, `nobleman`, `old_man`, `slime` and
`young_man`. The original bank names stay in the platform bindings.

Keys like `dialogue_NNNN` are just per-file IDs for shared lines. They aren't
Saturn or PSP message addresses; the binding records every place a line is
used. Style-specific reactions to status conditions use descriptive keys such as
`condition_charmed` in the same file. Branch labels are only added when the
game code shows what they are, never guessed from the wording.

Bosses that refuse to negotiate use the same window but are written separately
in `battle/boss_dialogue.json`. They aren't a speaking style and aren't mixed in
with story events.

### Story events

Story events are grouped under `events/` by place or storyline: DDS-NET mail,
Marie's jobs, the Central Library, the detective office, and so on. Bank,
message and page numbers stay in the Saturn binding. One line can cover several
places it appears in the game, but repeats that mean something different in
context stay as separate fields even when the Japanese is identical. The four
Saturn general-event banks use 1,890 fields for 2,028 pages; a PSP binding can
point its exact matches at the same fields instead of copying them.

### Magic and skills

The Saturn `MAGNAME` table is split, using its category data, into 79 magic
entries and 176 skill entries. Each has its own name and description, plus a
separate battle `console_text` only when there is an actual console record.
Magic used only in the field doesn't get a made-up console form. The bonus-disc
ability-name table uses the same fields, including 28 names whose Saturn FONT8
separator decodes to the same interpunct, plus one glyph treated as equivalent.

### 3D map Analyze

The 43 short katakana race names on the Analyze screen are reference-only
`analyze_grid` variants of the shared race names. Editing a race translation
updates both the grid and the FONT16 detail view. `ui/map_3d_analyze.json`
holds only Analyze's own headings and the typed `{cost}M` / `{cost}H` skill-cost
templates. Its LV, HP, MP and CP use the shared status templates. The retail
DA_3D data points both Law and Light at a single `L`; the alignment file keeps
them as separate fields, and the Saturn binding records Light as a second use
of the Law record.

### 2D map

`ui/map_2d.json` holds the city, world-city, ward and area templates, including
their suffixes and placeholder order. The default Hirasaki and Asahi come from
`ui/profile_entry.json`. The five fixed destinations come from
`locations.json`; only `Mt. Kasagi` has a MAP2D-specific short variant. The talk
prompt and Yes/No choices come from `field/messages.json`. A lone stock `雲` row
is editable but marked `unresolved` until a screen that shows it is found.

## Identity and sharing

A field is identified by its key within its file plus its field path. English
names and table indices aren't stable: names can repeat or change, and the PSP
version reuses some Saturn reserve slots for other things.

Row numbers and game IDs only appear in platform bindings. A binding can map:

- several places in the game to one field;
- one field to several screens or platforms;
- one game record to a declared platform variant.

Sharing is never assumed from matching Japanese. The same text can mean
different things in context, and differently stored Saturn and PSP records can
be the same line. Every share and every split is written into a binding.

Unused reserve slots have no known meaning yet. Until game code or another
release shows what they are, they get placeholder keys like
`reserved_magic_NNN` or `reserved_skill_NNN` with the game ID, and
`status: "reserve"`. This stops unrelated PSP replacements from being attached
to a made-up Saturn entry. Real entries never use table positions as their key.

Records that are just padding still appear in the corpus, but a binding can
mark a field that's only whitespace and line breaks as empty. That keeps padding
out of the editor without weakening the source checks.

A field has one translation unless there's a real difference in meaning or
presentation, in which case it gets a named variant. Different fonts, encodings,
storage or rendering between platforms don't by themselves justify a variant.
When a platform revised the Japanese, the field can use a reference-only
variant and keep the shared translation; if the revision changes the meaning,
it shows up as review work. Duplicate source glyphs that mean the same thing
are merged only by a binding rule, never inside the corpus.

## Templates and substitutions

Fields hold the whole sentence the player reads, with typed placeholders in
whatever order suits the language. The platform binding says how the game
provides the values. For example, a Saturn record may contain only `を手に入れた`,
while the field is the whole `{item}を手に入れた` / `Obtained {item}.` template.
Stored prefixes work the same way: the retail `CTRL` record backs the
`CTRL {rank}` template. Prefix and suffix composition is declared in the
binding; a fragment in the middle with nothing on disc to back it isn't
allowed.

Symbols and punctuation are written here too. The currency message has separate
yen and magnetite forms using `{yen_symbol}` and `{mag_symbol}` before
`{currency_amount}`. The game supplies only the formatted amount, not the
currency label.

Where the original data draws one of those symbols as a font glyph, the binding
maps that glyph code to the token. The corpus stays lossless, and the text you
edit says `{yen_symbol}` instead of a raw glyph number.

Placeholder names and counts must match between reference and translation, in
every variant. When a placeholder has a limited set of values, the platform code
should check every combination against the screen limits, not just the stored
pieces. Timing controls and unknown control codes also keep their counts. Line
breaks and source-only presentation glyphs may change with the language.

## Surface contracts

Each platform records the Japanese and translated screen limits separately. A
limit gives the font or measuring method, maximum rows, width and its unit,
alignment or wrapping where relevant, and where the number came from. Unknown
limits are marked unknown, not guessed.

Bindings also record which screens use a field, separately from storage. A
field-wide entry covers a form used everywhere, such as item `console_text`; a
per-record entry covers something narrower, such as the Bead and Life Stone
result labels. If no entry exists, it's treated as unknown rather than guessed
from a shared table.

Examples: the Saturn event window is 20 FONT16 cells by three rows in Japanese,
and 300 pixels by three rows with the English renderer. The battle console is
three rows of 16 small-font cells in both languages. A field used on several
screens must fit all of them, or have a separate written form for the one where
it doesn't.

## Coverage requirements

The goal is for the build to fail when:

- visible text or a template exists only in game code;
- a screen listed in `consumers.md` has no asset here;
- a reference, variant or typed placeholder is invalid;
- sharing is assumed from content instead of declared in a binding;
- a filled-in value breaks a known screen limit;
- a text record on disc is neither bound nor marked as not player-facing.

Text in artwork follows the same rule. Its binding may be an image replacement
rather than a text encoder, but the wording still lives here.

### Current ownership boundaries

All visible wording is supposed to live here, but some screens are handled
outside the normal text pipeline for now. Known gaps:

- The main battle commands `FIGHT`, `TALK`, `ESCAPE`, `AUTO`, `PRESET` and
  `REPEAT` are drawn as graphics or font lettering. A full search of COMBAT data
  and code found no text records to bind. Their fields stay here for when an
  image/font path exists.
- The PSP save screen still needs to be wired to the titles, difficulty labels,
  prompts, fallback label and detail template already in `save_load.json`.
- The Saturn slot-name compiler would need extending if a translation wants to
  reverse the `{first_name}` then `{last_name}` order. The separator is already
  here, but the renderer reads those adjacent save fields in a fixed order.
- The PSP first-VWF welcome line, and switching the PSP profile entry over to
  the shared profile-entry assets (removing its old content-equality locks).
- Every word in title, menu and other artwork.

This list is a starting point, not a guarantee it's complete. Coverage still
has to be checked against every item in `consumers.md`.

`battle/party_panel.json` holds the COMBAT placeholder rows `EMPTY` and
`IN PARTY` that the game builds at runtime, as five- and eight-cell fields. The
engine draws them with the FONT8 `stock_latin` set; centering and padding are
layout, not spaces in the text.

The developer Sound Test and 3D Test overlays on Saturn are editable too.
`diagnostics/sound_test.json` and `diagnostics/test_3d.json` hold all eleven
fixed-cell ASCII fields, including the spaces that separate and align numbers.
Their bindings keep the original byte capacities, and the diagnostics build
requires ASCII followed by a terminating NUL.

## Current coverage

The Saturn corpus is the extraction source; this directory is the only place
translations are written. What's covered, by area:

### Items, demons, magic and skills

- Equipment and items have names, descriptions, console forms and field-message
  templates.
- The demon catalogue has game and Akuma Zensho names and every Compendium
  profile field.
- The bonus disc's 44 distinct race descriptions, three intentional NO DATA
  layouts, eleven fusion-help rules, and the Vengeful Spirit and Fiend
  supplement labels are here. Two raw placeholder race entries are still
  unidentified.
- PSP-only entities and PSP revisions of the Japanese are available for later
  PSP bindings.
- Magic and skills cover all 255 Saturn ability slots, 199 separately written
  battle-console forms, and the Akuma Zensho name table.
- Of the PSP name/description fields: 298 match exactly and need no variant,
  105 have revised Japanese but keep the shared English, and 102 have
  meaningful revisions that are still untranslated. Two unused PSP-only skills
  appear as unresolved entries. The PSP's repurposed reserve slots point to the
  existing Evil Gaze, Death Ring and Cauterizing Fist entries.

### Negotiation

All 15 speaking styles are covered by 8,523 shared fields, including condition
reactions. On Saturn these are bound to 10,009 places in the game. PSP reuses
the same fields rather than keeping its own copies.

### Locations

24 shared dungeon locations, seven locations only shown on the save screen,
three short automap names, and editable 3D-map, automap and save/load
templates. 144 dungeon rows, 288 separately indexed ELV/KAI mirror uses and
eight special SAVE rows all bind to those locations, and PSP can reuse the same
names without copies or variants.

### Races and affinities

All 43 game races, the bonus disc's 48 race labels, all 96 detailed affinities
and all 66 short Analyze slots. Fusion abbreviations and Analyze punctuation
are text data, not hard-coded. PSP reuses these where the text matches; two PSP
layout revisions are reference-only variants, and its 29 replacements for
Saturn reserve affinities are still untranslated. The fusion-only Time entry
and all 90 race-table uses in SHOPSMP also point here instead of repeating race
names in Gouma-den text.

### Facilities and save/load

- All 763 SHOPSMP pages are split between Gouma-den, shops, healer, bar, MAG
  exchange, gym, demon join, shared, debug and race screens, keeping the 595
  lines and their reuse from the earlier Saturn translation.
- Sixteen drinks keep their separately stored names and descriptions in one
  record each, and six bar patrons have their display names here.
- Fusion confirmation, the healer's all-members label and the stock `Inv.`
  label are editable.
- `save_load.json` has all Saturn SAVE/LOAD text other than locations: the
  filled-slot name, level, date and time templates, the English confirmation
  choices, system messages, image labels, and the PSP savedata wording and
  detail template that used to be in code.
- `player_profile.json`'s `full_name_storage.text` is the one place that sets
  the `NAME_FW_FULL` order and separator. Profile Entry and LOAD both use it, so
  changing the slot layout can't make them disagree.
- `capacity_number.text` is the only place the required block count lives.
  Bindings substitute it into the three Saturn sentences that mention it,
  instead of keeping four copies of `129`.
- The Saturn date/time punctuation and `Lv` prefix are bound as the fixed parts
  of their templates; the basement prefix is bound to the template in
  `field/location_formats.json`.
- Lettering in the SAVE/LOAD images is handled by the visual package, not
  treated as font text.
- The seven Gouma-den tutorial lines that only exist on PSP are new fields;
  everything else on PSP reuses the Saturn fields.

The facility screens have different measured limits: drink and patron names use
64-pixel FONT8 rows, shared character/demon names on facility screens use 104
pixels, and the healer's separately drawn all-members row uses 144 pixels. The
status screen character name uses the same eight-cell, 126-pixel FONT16 space as
the detailed demon name. These are screen limits, not separate name fields.

### Characters and profile entry

- All six `CHARNAME` characters live in `characters.json`. The PSP table has
  the same six rows, so nothing is copied.
- Kyouji's short, full, given and family names are separately editable,
  replacing the `Kyouji`/`Kuzunoha` that the old battle renderer had built in.
- `ui/profile_entry.json` has all 22 `NAME.BIN` strings, the 18 opening
  DDS-NET renewal pages, the six English input-grid rows, and the Hirasaki and
  Asahi defaults. The runtime name format lives in `player_profile.json`.
- The three stock tab labels each have one field covering both their
  combined-row and selected-tab copies (which are byte-identical). Katakana is
  still listed even though the English version drops it. The city and ward
  suffixes are kept as separately editable fields.
- Grid rows use the generated `KANJI.FON` `ark_latin` reference set rather than
  hard-coded code formulas. NAME.BIN centers its 16px Ark glyphs at runtime
  based on the generated ink bounds.
- END and the left/right actions have editable labels, but their existing
  compound images are still handled as font/image data.
- The event pages keep the earlier Saturn translation here so a PSP binding can
  reuse it.
- The first/last name, city/ward, and occupation prompt/summary text share
  source records in the game, but bind to separate fields here so their English
  can differ. Game code can lay them out but doesn't decide their content or
  require two fields to stay equal.

### Story events

The general-event data has 1,103 message groups with text and 2,028 pages,
organised into 92 scenes across 40 `events/` files plus the opening profile
sequence. They come to 1,890 separately editable fields. Repeated uses are only
shared where the earlier Saturn binding or a review of the scenes supports it,
and the original Saturn translations and useful notes are kept exactly. Yen
glyphs are converted to `{yen_symbol}`, and even the retail placement-error
messages are editable. No bank coordinate appears in any key or filename.

### Status, level up and equipment

- `ui/status.json` has the six base-stat abbreviations, eight derived-stat
  headings, generic Attack and Accuracy labels, all ten personality values, and
  the Loyalty, TYPE, LV, HP, MP, EXP, NEXT, CP, AUTO, P.A. and CTRL templates.
  Typed placeholders cover every number or value the game fills in.
- The seven AUTO commands are in `battle/commands.json`. Party and alignment
  terms are in `terminology/alignments.json`. All four CTRL ranks and the retail
  fallback are editable.
- Twenty-four stock ASCII records bind these to exact `NORMCOM.BIN` offsets.
  Japanese labels that exist only as bitmaps are tied to fixed regions of the
  retail file. The English matches the earlier Saturn translation.
- `ui/level_up.json` has the title, the typed remaining-points line, OK,
  Yes/No, and the Learned Magic heading. `LV`, `HP`, `MP`, `EXP` and `NEXT`
  reuse the templates in `ui/status.json`, and names come from the usual
  catalogues. The four-cell ornament before `LEFT` and the centering cell before
  `NO` are layout, not spaces. The max-level `-------` and no-MP `---/---`
  fallbacks are here too, even though the retail game builds them in code and
  has no text record for them.
- Equipment uses the shared stat words in `ui/status.json` and adds only its
  two actions in `ui/equipment.json`. COMP and shops both use those. Shop
  `Inv.`, character names and item names come from their normal files; the
  engine derives what it needs for drawing instead of keeping its own strings.

### Commands

All battle, COMP, shop, bar and healer menu text is here as ordinary fields.
Thirty-seven Saturn records bind the menu tables, including three
byte-identical copies of the 16-entry battle action table. The retail
`OFFENCE` and `DEFENCE` are battle-table variants of the shared `OFFENSE` and
`DEFENSE` terms. The bonus compound cells used to draw `REVIVE` and `STATUS`
are only normalized in their bindings. Each menu field sets
`font8_alphabet: original`; fields without it use the replacement typeface.
Bitmap generation and phrase compression are build steps, not extra places to
translate.

### Options

`ui/options.json` groups the two-page Saturn options menu into settings, shared
value lists, ordering-popup categories, controller actions and footer prompts
that change with state. All 38 live `CFG_SET.BIN` records have one binding each
and keep the earlier Saturn English. The serif `CONFIG` heading is a graphic; an
empty unused table row with those codes is kept for byte-for-byte parity but
isn't shown as editable. Drawing fragments like `AR`, `ign` and the old
ordering-popup compound syllables aren't fields; `options.ui` builds every
packed glyph from the full words. The PSP's identical Auto Map and speed values
can reuse these fields; its revised battle-message text is a reference variant,
not a copy.

### Horoscope

`ui/horoscope.json` has all eight story messages as whole sentences. The
Saturn build works out line breaks at word boundaries and moves the pointers to
suit the three-row reveal window. Line breaks and pool addresses aren't a second
copy of the text.

### FMV subtitles

The START2 news report is in `fmv/subtitles.json`. Its nine entries hold the
Japanese, the English line breaks, and start/end times in hundredths of a second
relative to the movie, with no ASS/libass styling and no second subtitle script
per platform. Saturn derives 12 fps frame ranges, FONT16 codes, centering and
storage from it. PSP derives `30000/1001` frame ranges and its own FONT16
overlay from the same cues. The movie files are only used to verify against;
they aren't edited or regenerated.

### Credits

`credits/names.json` has the 40 people in the credits. Their 28 uses in the
main roll and 12 in the staff test are separate records in the game but point to
one field per person. The Saturn renderer builds fixed 96- and 112-pixel bitmap
rows from the full names; the squeezed rows are generated, not separately
written abbreviations.

### Battle

- 82 remaining small-font console records, all 203 visible Demon Chat records,
  19 battle-help lines, 24 general command-help lines, four provisioning
  choices and 12 diagnostic strings.
- The 105 style-specific condition reactions stay with their negotiation
  styles; the eight generic fallbacks are in `battle/condition_fallbacks.json`.
- Kyouji and Rei's battle-test name forms are on their character entries.
- Blank records stay in the corpus and don't become empty editor rows.
- Control codes in the retail data stay as lossless tokens until their effect
  is known; `{NUM}` and `{demon_name}` are editable templates with typed values.
- The earlier Saturn translation is the reference for the English; matching PSP
  text can bind to the same fields.

### Ritual console

The ritual console is its own set of fields in `ritual/console.json`. Its 64
visible fields bind to 64 of the 144 `BUTU_SRF` slots; empty slots stay in the
corpus and aren't shown in the editor. It's never treated as shared with Demon
Chat just because the wording or look is similar.

### COMP and command help

COMP uses the existing demon, character, item, magic, skill and command-help
files directly. Its 210 direct demon records and 109 compact overflow records
are just how the names are stored, not alternate name fields. All 24 COMP help
lines are in `ui/command_help.json`; neither the code nor `NORMHELP.DAT` is a
second place to translate.

PSP command help reuses those fields and the battle-help fields wherever the
line is the same. Its 34 PSP-only states and shorter variants that fit its
capacity are in `ui/command_help_psp.json`. The PSP binding places them in
fixed member-14 slots; it isn't another place to edit.

Generated catalogues are output only: their translated values are filled in
from these files and the bindings. There should only ever be one editable place
for any translation.
