# Shared text assets

`assets/text` is the human-authored text layer for Devil Summoner. It is shared
by the Saturn and PSP projects. Files here are organised around entities and
player-visible consumer surfaces, never around the binary file that happens to
store a string.

## Ownership rule

Every player-visible string, label, fragment, and complete dynamic template is
an editable asset here. This includes stock-English labels, deliberately
untranslated text, text encoded in executable instructions, and text baked into
images.

Runtime code may:

- select an asset and a declared variant;
- substitute typed values such as an item, demon, location, or number;
- apply a declared numeric formatter;
- measure, wrap, encode, and render the result.

Typeface and glyph-set choices are platform consumer metadata, not special
characters embedded in translations. A plain authored `GO` can therefore use
the retained Saturn FONT8 capitals on a command surface and the normal English
alphabet on another surface without duplicating or decorating the text.

Runtime code must not own visible words, punctuation, word order, compact
labels, or translated phrase fragments. Render-only derivatives such as
compound glyphs and packed dictionaries are generated from these assets.

## Layers

The text system has four deliberately separate layers:

1. `assets/text` owns reference text, translations, semantic grouping, complete
   templates, and deliberately authored surface forms such as `console_text`.
2. `<platform>/text/bindings` maps an asset field to physical source records,
   code sites, generated pools, or visual targets. It owns platform identifiers,
   offsets, selectors, and applicability.
3. `<platform>/text/config/surfaces.json` describes what a player-visible consumer
   can display. Limits are locale-specific and use explicit units such as glyph
   cells or pixels.
4. `<platform>/text/corpus` is a generated, lossless catalogue of physical
   source records. It is binary evidence and is not the authoring interface.

Binary storage capacity belongs to the physical source/container contract. It
must not be confused with the visible surface limit.

## Organisation

Text describing an entity stays with that entity. Dialogue, prompts, UI labels,
and dynamic templates stay with their consumer surface. The expected broad
shape is:

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
  ui/
```

An entity may expose more than one deliberately authored form. For example, an
item can have `name`, `description`, and `console_text`; a race can have full,
grid, battle, and fusion forms where the visible surfaces genuinely require
different wording. Consumers must not silently truncate or derive these forms.

System console fragments that do not belong to an entity remain with the
console surface. Complete field messages such as `Obtained {item}.` remain with
the field-message surface even when the original binary stores only a suffix.
If one physical suffix is consumed by several runtime paths, the binding lists
every semantic use; it does not force those messages into one authored string.

Each text field keeps the readable `reference` beside its editable
`translation`. Optional state is omitted when it carries no information:
`reviewed` defaults to `false`, while notes, variants, placeholders, and status
appear only where they are needed.

Negotiation is divided by speaking personality. File-local `dialogue_NNNN`
keys identify shared authored lines, not a Saturn or PSP message/page address;
the platform binding owns every occurrence. Personality-specific condition
reactions use descriptive keys such as `condition_charmed` in the same file.
Branch labels are added only when call-site evidence proves them, rather than
being guessed from the wording.

Bosses that reject battle negotiation use the same event-style window but are
authored separately in `battle/boss_dialogue.json`; they are not a speaking
personality and are not mixed into the general story-event catalogue.

Story events are grouped under `events/` by player-facing place or narrative
thread, such as DDS-NET correspondence, Marie's jobs, the Central Library, and
the detective office. Event-bank names, message numbers, and page numbers stay
in the Saturn binding. One authored line may therefore serve several proved
physical occurrences, while contextually distinct repetitions remain separate
fields even when their Japanese happens to match. The four Saturn general-event
banks use 1,890 authored fields for 2,028 physical pages; a later PSP binding can
point its exact matches at those same fields rather than copying them.

The current speaking-style files are `archaic`, `beast`, `boy`, `cynical`,
`feral`, `girl`, `highborn_lady`, `kansai`, `lady`, `little_girl`, `manic`,
`nobleman`, `old_man`, `slime`, and `young_man`. Original bank names remain in
platform bindings rather than leaking into the authoring layout.

The Saturn `MAGNAME` catalogue is split by its proved category metadata into
79 magic entries and 176 skill entries. Each entity owns its editable name and
description, plus a separate battle `console_text` only when a physical console
record exists. Field-only magic therefore does not acquire an invented console
form. The bonus-disc ability-name table binds to the same fields, including its
28 explicit punctuation variants and one proved glyph equivalence.

## Identity and sharing

An asset is identified by its file-local semantic key and field path. English
names and platform table indices are not stable identities: names can duplicate
or change, and the PSP version repurposes some Saturn reserve slots.

Physical row numbers and game IDs therefore live only in platform bindings.
Bindings may explicitly map:

- several physical occurrences to one authored field;
- one authored field to several consumers or platforms;
- one physical source record to a declared platform variant.

Sharing is never inferred from matching Japanese text. Repeated text can have
different context, while physically different Saturn and PSP records can be one
semantic line. All sharing and forks are explicit.

An unused reserve has no known semantic identity to name. Until a call site or
another release establishes one, its provisional `reserved_magic_NNN` or
`reserved_skill_NNN` key retains the catalog game ID and carries
`status: "reserve"`. This narrow evidence-key exception prevents unrelated PSP
replacements from being attached to a made-up Saturn entity; active entities
still never use table coordinates as their identity.

Binary-only blank layout remains visible in the generated physical catalogue,
but a binding may explicitly normalize a field made entirely of whitespace and
layout breaks to an empty authored value. This keeps storage padding out of the
editor without weakening source verification.

A field uses one shared translation unless a real semantic or presentation
difference requires a named variant. Platform differences in fonts, encodings,
storage, and rendering do not by themselves create translation variants.
Platform revisions of the reference text may select a reference-only variant
while retaining the shared translation. Those variants remain visible review
work when the revision changes meaning. Equivalent duplicate source glyphs are
normalized only by an explicit binding rule, never inside the physical corpus.

## Templates and substitutions

Assets contain the complete text the player understands, with typed
placeholders in language-appropriate order. A platform binding explains how
the game supplies those values. For example, a Saturn source may contain only
`を手に入れた`, while the authored field is the complete
`{item}を手に入れた` / `Obtained {item}.` template.
The same rule applies to stored prefixes: retail `CTRL` grounds the complete
`CTRL {rank}` template. Prefix and suffix composition are declared explicitly;
an ungrounded middle fragment is not accepted.

Visible symbols and punctuation are authored too. The currency message, for
example, has explicit yen and magnetite forms using `{yen_symbol}` and
`{mag_symbol}` before `{currency_amount}`. Runtime supplies only the formatted
amount; it does not choose or insert an unrecorded currency label.

When a physical source represents one of those visible symbols as a font glyph,
the platform binding must explicitly map that glyph code to the authored token.
This keeps the physical corpus lossless while ensuring the editable text says
`{yen_symbol}` rather than exposing a raw glyph number or relying on runtime
prose.

Reference and translation placeholder names and multiplicities must agree,
including in every declared variant. When a placeholder has a bounded domain,
the platform adapter should additionally validate every composed value against
the relevant surface rather than checking only the stored fragments.
Timing controls and unknown operations also preserve their multiplicity;
layout breaks and source-only presentation glyphs may change with the language.

## Surface contracts

Each platform records Japanese and translated geometry independently. A
contract declares the font/measurement model, maximum rows, width and unit,
alignment or wrapping policy where relevant, and the evidence for that limit.
Unknown measurements remain explicitly unknown rather than receiving guessed
values.

Platform bindings declare the proven consumer edges separately from physical
storage. A field-wide edge covers a genuinely common form such as item
`console_text`; a record edge handles a narrower occurrence such as the Bead and
Life Stone result labels. Missing edges remain unproved rather than being
guessed from a shared source table.

For example, the Saturn event window is 20 fixed FONT16 cells by three rows in
Japanese and 300 pixels by three rows under the English renderer. The battle
console is three rows of 16 fixed small-font cells in both languages. A single
asset used by multiple surfaces must satisfy every binding, or provide an
explicit authored surface form.

## Coverage requirements

The build will ultimately fail when:

- a player-visible literal or template exists only in runtime code;
- a consumer described by `consumers.md` has no asset ownership;
- an asset reference, variant, or typed placeholder is invalid;
- sharing is inferred by content instead of declared by a binding;
- a composed value violates a known surface contract;
- a physical text record is neither bound nor explicitly classified as
  non-player-facing evidence.

Text in artwork follows the same ownership rule. Its platform binding may be a
visual replacement rather than a text encoder, but the editable wording still
lives here.

### Known migration debt

The mature implementations still contain visible wording that must move here;
none of it is a runtime exemption. The current audit tracks:

- the battle-result empty label;
- locating the retail render selectors for the authored primary battle labels
  `FIGHT`, `TALK`, `ESCAPE`, `AUTO`, `PRESET`, and `REPEAT`; the other battle,
  COMP, shop, bar, and healer commands now have proved Saturn records and all
  command surfaces select the preserved `stock_latin` face;
- wiring character full/short name forms from `characters.json` into the
  remaining mature renderers;
- wiring the mature Saturn status renderer to the complete readout templates,
  headings, command/alignment domains, and personality terms now owned by the
  shared assets;
- wiring the mature Saturn fusion and Analyze renderers to the authored race
  labels and heading template stored here;
- wiring the mature Saturn location renderers to the authored floor/location
  templates now stored in `field/location_formats.json`;
- the mature Saturn MAZE hook, which currently collapses the distinct item
  `Found` and `Obtained` call paths despite the retail call sites using both;
- wiring the PSP save renderer to the titles, difficulty labels, prompts,
  fallback label, and complete detail template now stored in `save_load.json`;
- the PSP first-VWF welcome line, and wiring the shared profile-entry assets
  while removing its old content-equality locks;
- every visible word in title, menu, or other artwork.

This checklist is an audit seed, not proof of completeness. Consumer coverage
must eventually prove that every item in `consumers.md` has asset ownership.

## Migration

The physical Saturn corpus remains the extraction oracle while this authored
layer is introduced. The first vertical slice joins equipment and items to
their names, descriptions, console forms, and complete field-message templates.
The demon catalogue now joins game and Akuma Zensho names with all Compendium
profile fields, while retaining PSP-only entities and PSP reference revisions
for later platform bindings. The magic and skill catalogues add all 255 Saturn
ability slots, 199 separately authored battle-console forms, and the complete
Akuma Zensho name table. Of the PSP name/description fields, 298 exact fields
need no variant, 105 source revisions retain the shared English, and 102
meaningful revisions remain explicitly untranslated. Two dormant PSP-only
skills are visible unresolved entries, while its repurposed reserve slots point
to the established Evil Gaze, Death Ring, and Cauterizing Fist entities. All 15
negotiation styles are represented by 8,523 shared authored fields, including
their condition reactions; Saturn fans them across 10,009 explicitly bound
physical occurrences. PSP reuses the same authored fields rather than carrying
duplicate translations. The location catalogue adds 24 shared dungeon places,
seven save-screen-only places, three proven compact automap names, and editable
3D-map, automap, and save/load composition templates. Its 144 dungeon rows and
eight special SAVE rows bind explicitly to those places, while PSP can reuse
the same names without copies or platform variants.
The race and affinity catalogues add all 43 game races, the bonus disc's 48
physical race labels, all 96 detailed affinities, and all 66 compact Analyze
slots. Fusion abbreviations and Analyze punctuation are authored data rather
than renderer literals. Exact PSP text reuses these fields; two PSP layout
revisions are reference-only variants, while its 29 replacements for Saturn
reserve affinities remain visible untranslated work. The fusion-only Time
identity and all 90 direct SHOPSMP race-table uses also bind here instead of
duplicating race names in Gouma-den text.

The facility slice partitions all 763 physical SHOPSMP pages into the
Gouma-den, shops, healer, bar, MAG exchange, gym, demon-join, shared, debug,
and race consumers while retaining the mature corpus's 595 authored lines and
explicit fan-out. Sixteen drinks join their separately stored names and
descriptions in one entity record, and six bar patrons own their display names.
Fusion confirmation, the healer's all-members label, and the stock `Inv.` label
are editable assets rather than renderer prose. `save_load.json` owns all
non-location Saturn SAVE/LOAD text, stock-English and raster labels, and the
previously code-owned PSP savedata wording and full detail template. The seven
genuinely PSP-only Gouma-den tutorial lines are additions; inherited PSP text
continues to reuse the Saturn-authored fields.

The character and profile-entry slice gives all six `CHARNAME` identities one
shared home in `characters.json`; the PSP table has the same six semantic rows
and therefore needs no copied text. Kyouji's short, full, given, and family
forms are independently editable, replacing the mature battle renderer's
embedded `Kyouji`/`Kuzunoha` wording. `ui/profile_entry.json` owns all 19
physical `NAME.BIN` strings, the 18 opening DDS-NET renewal pages, the six
English input-grid rows, the Hirasaki and Asahi defaults, and the visible END
command glyph. The event pages keep the mature Saturn translation in this
shared asset so a later PSP binding can reuse it rather than copy it. The
physically shared first/last, city/ward, and occupation prompt/summary sources
deliberately bind to separate fields, so a translator can change their English roles
independently. Runtime code may lay out these fields but does not own their
content or require two independently authored fields to remain equal.

The complete general-event corpus has 1,103 text-bearing message groups and
2,028 physical pages organized into 92 semantic scenes across 40 `events/`
catalogues plus the opening profile workflow. They resolve to 1,890 independently
editable fields: repeated uses are shared only where the mature Saturn binding
or reviewed cross-scene semantics establish that relationship, and the original
Saturn translations and useful notes are retained exactly. Visible yen glyphs
normalize explicitly to the authored `{yen_symbol}` token, and even retail
placement-error messages remain editable. No event-bank coordinate appears in
an asset key or filename.

The status slice gives the six base-stat abbreviations, eight derived-stat
headings, generic Attack and Accuracy labels, all ten personality values, and
the complete Loyalty, TYPE, LV, HP, MP, EXP, NEXT, CP, AUTO, P.A., and CTRL
templates one editable home in `ui/status.json`. Typed placeholders cover every
runtime-supplied number or selected value. The seven AUTO commands live in
`battle/commands.json`; party and alignment-axis terminology lives in
`terminology/alignments.json`; all four CTRL ranks and the retail fallback are
editable too. Twenty-four stock ASCII records bind these assets to exact
`NORMCOM.BIN` offsets, while bitmap-only Japanese labels remain grounded in
pinned retail regions. The English stays faithful to the mature Saturn output.

The command slice owns all battle, COMP, shop, bar, and healer menu wording as
ordinary editable fields. Thirty-seven newly catalogued Saturn records bind
the proved tables, including three byte-identical physical copies of the
16-entry battle action table. Retail `OFFENCE` and `DEFENCE` remain explicit
battle-table variants of the shared `OFFENSE` and `DEFENSE` terminology, and
the bonus compound cells used to draw `REVIVE` and `STATUS` are normalized only
at their physical bindings. Typeface selection remains platform metadata: each
of these consumers requests FONT8's preserved `stock_latin` reference set.
Bitmap generation and phrase compression remain derived rendering work; they
are not second translation sources.

The Options slice groups the two-page Saturn menu into settings, reusable value
domains, ordering-popup categories, controller actions, and state-dependent
footer prompts in `ui/options.json`. All 38 `CFG_SET.BIN` records have one
explicit binding and retain the mature Saturn English. Renderer-only pieces
such as `AR`, `ign`, and the old ordering-popup compound syllables are not
authored fields; a future repacker must derive any packed glyphs from the
complete editable words. The identical PSP Auto Map and speed values can reuse
these fields, while its revised battle-message source is an explicit reference
variant rather than a copied translation.

The battle slice gives the remaining 82 visible small-font console records,
all 203 visible Demon Chat records, 19 battle-help lines, 24 general command
help lines, four provisioning choices, and 12 diagnostic strings consumer-owned
homes. The 105 personality-specific condition reactions remain with their
negotiation styles; the eight generic fallbacks live in
`battle/condition_fallbacks.json`. Kyouji and Rei's distinct battle-test forms
remain on their character entities. Physical blank records stay classified as
binary evidence and do not become empty editor rows. Retail control operations
remain lossless tokens until their behavior is proved, while `{NUM}` and
`{demon_name}` are editable templates with typed runtime values. The mature
Saturn output is the translation oracle; identical PSP text can bind these same
fields without being copied.

The ritual console is a separate authored consumer under `ritual/console.json`.
Its 64 visible fields bind to 64 of the 144 physical `BUTU_SRF` slots; blank
slots remain physical evidence rather than empty editor rows. Sharing with
Demon Chat is never inferred from equal wording or similar presentation.

After bindings cover the authored corpus, translations in the generated
physical catalogue will be removed or generated from these assets. There must
never be two independently editable translation locations.
