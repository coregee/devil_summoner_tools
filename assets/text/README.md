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

Visible symbols and punctuation are authored too. The currency message, for
example, has explicit yen and magnetite forms using `{yen_symbol}` and
`{mag_symbol}` before `{currency_amount}`. Runtime supplies only the formatted
amount; it does not choose or insert an unrecorded currency label.

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
- character full/short name forms used directly by renderers;
- status headings and personality terms;
- wiring the mature Saturn fusion and Analyze renderers to the authored race
  labels and heading template stored here;
- wiring the mature Saturn location renderers to the authored floor/location
  templates now stored in `field/location_formats.json`;
- the mature Saturn MAZE hook, which currently collapses the distinct item
  `Found` and `Obtained` call paths despite the retail call sites using both;
- wiring the PSP save renderer to the titles, difficulty labels, prompts,
  fallback label, and complete detail template now stored in `save_load.json`;
- the PSP first-VWF welcome line and content-locked name-entry labels/grids;
- config compound glyphs, which must be generated from editable labels rather
  than maintained as independent phrase fragments;
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

After bindings cover the authored corpus, translations in the generated
physical catalogue will be removed or generated from these assets. There must
never be two independently editable translation locations.
