# Saturn text

The text package is record-centric. A physical source describes where records
live, a container describes how those records are framed, and each record names
the source encoding used to turn its code units into readable text. Source
encodings never name a game file.

Repacking uses the same separation in the other direction. The complete
general `event.dialogue`, `battle.negotiation`, and shared `battle.ui` surfaces,
plus the supported shop/facility portion of the mixed `SHOPSMP.EVE` bank, are
compiled from shared authored assets. Physical containers own pointers,
terminators, capacity, and round-trip validation. Canonical translations live
under the repository-level `assets/text` tree; the physical corpus remains
binary evidence rather than an editing interface.

## Layout

- `config/encodings.json` defines reusable alphabets, control vocabularies, and
  source encodings.
- `config/surfaces.json` records measured Japanese and English consumer limits.
- `config/glyph_sets.json` selects preserved stock glyph sets for consumer
  surfaces that intentionally retain a retail typeface.
- `config/event_scenes.json` records only evidence-grounded semantic groupings
  for the general event banks.
- `config/sources/<disc>/manifest.json` defines physical files, the four
  container shapes, defaults, and exceptional record-level overrides.
- `corpus/<disc>/` contains deterministic extracted physical records.
- `bindings/` joins Saturn physical records to shared authored asset fields.
- `../../assets/text/` is the human-facing, cross-platform authoring layer.
- `util/` contains strict configuration, token, codec, and container helpers.
- `generated/` is ignored and contains compiled banks, build bindings,
  inventories, and other engine-facing payloads.
- `extract.py` verifies source identity and regenerates the complete corpus.
- `event_inventory.py` builds an ignored scene-curation report for the four
  general event banks.
- `repack.py` builds general EVENT, shop/facility dialogue, battle negotiation,
  the file-backed battle and ritual consumers, and the COMP help/name tables.

Extraction reads its evidence directly from the verified original disc, never
from the writable build mirror. The mirror may therefore contain translated
text, engine patches, fonts, and visuals without changing corpus references or
making the extraction suite stale.

The corpus record contract will stay small:

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

Records are not deduplicated by content. Physical copies and the three deliberate
`NAME.BIN` translation forks are declared explicitly in the source manifest.

The general-event banks prove 1,103 message units containing 2,028 pages, but
their binary framing does not itself establish semantic scene boundaries. Running
`python saturn/text/event_inventory.py` writes
`generated/event_scene_inventory.json`, grouping pages by the source message
that actually frames them and recording literal speaker cues, tokens, and any
existing asset uses. Scene, location, story-state, choice, and call-site fields
remain explicitly unresolved until a compact entry in `event_scenes.json`
grounds them. All four general-event banks are complete: their 1,103
text-bearing messages and 2,028 pages are assigned to 92 semantic scenes and
bound to shared authored assets. The report now proves zero unclassified
messages and zero unbound pages. It is not an authored asset and does not claim
that one physical message equals one story scene.

The generated corpus is binary evidence, not the translation editor. Assets
are organised around entities and player-facing surfaces. Item and equipment
names, descriptions, and console forms stay with their entities; MAZE suffixes
become complete typed field-message templates. The location slice similarly
reduces 144 canonical records plus 288 independently indexed ELV/KAI mirrors to
24 explicitly bound places, while retaining three separately editable automap
forms and complete floor/location templates. MAZE and AUTOMAP share the same
authored Yes/No choices; `(No data)` and `Delete?` remain AUTOMAP-owned fields.
Seven additional save-screen places and the shared Mount Kasagi identity cover
the eight special SAVE/LOAD labels without duplicating them as save prose; each
record validates the identical physical copy in both executables. The mixed
SHOPSMP bank is partitioned by consumer: facilities, demon joining, debug UI,
and the race catalogue own their lines independently of the parent file. Saturn
bindings retain exact physical grounding without putting file offsets or table
indices into semantic asset identities.

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

The general EVENT compiler resolves all 2,028 physical pages through Saturn
bindings to 1,890 human-facing asset fields. It rebuilds `MESFILE.EVE` and
`EVFILE_0.EVE` through `EVFILE_2.EVE` atomically from the verified source disc,
preserves the two structural-only messages, wraps the translated FONT16
dialogue to the `event.dialogue` surface contract, retains direct menu readers,
and reparses every output.

`config/event_codec.json` records the stable dictionary used by the mature
Saturn output. `generated/game/event_build.json` binds that codec, the current
FONT16 metrics, and the exact digest of every rebuilt bank. All four outputs
are byte-identical to the mature Saturn translation build; this is enforced as
a regression oracle rather than assumed from matching strings.

## Shop and facility EVENT repacking

`SHOPSMP.EVE` is a mixed physical bank rather than a separate shop renderer.
The standard dialogue and direct FONT16 menu records use the same proved EVENT
runtime installed for `event.dialogue`. The `shopsmp` target resolves all 763
translator-facing pages, compiles both the standard dialogue and all 193
translator-facing direct-FONT12 Fusion pages, and reparses the complete
815-message bank. The one structural-only Fusion message remains intact.
`generated/game/shopsmp_build.json` records zero deferred pages and binds the
output to both FONT16 and FONT12 metrics. The displayed Goofy shop line at
message 741 remains pinned to the trusted mature Saturn output.

The corresponding `fusion.menu` engine target installs the FONT8/FONT12
consumer renderers required by the direct records. The compact chart labels
come from their own editable race fields rather than being treated as file-local
text or silently derived from the longer table labels.

## Battle-negotiation repacking

The negotiation compiler rebuilds `BOSSTALK.EVE` and all fifteen personality
banks from 9,920 bound physical pages. Six additional messages contain only
structural controls and are preserved directly. Every rebuilt bank is
byte-identical to the mature Saturn output.

The same target compiles 113 condition messages and four provisioning labels
into `COMBAT.BIN`. It also compiles the complete `ITEMNAME.DAT` catalogue so
runtime item substitutions and descriptions always come from one asset-backed
output. The engine stage consumes this generated `COMBAT.BIN`; the normal build
installs the final engine output rather than the intermediate text-only file.

## Shared battle UI repacking

The `battle` target rebuilds all six file-backed consumers used by the shared
battle runtime: `BTL_MES.MD8`, `BTL_SRF.MDT`, `BTL_HELP.DAT`, `ITEMNAME.DAT`,
`MAGNAME.DAT`, and the ritual console's `BUTU_SRF.MDT`. It resolves 313 visible
small-font console rows, 203 visible Demon Chat rows, all 19 help records, all
542 item and ability records with their separate names and descriptions, and
64 visible ritual-console rows. The remaining physical pointer slots stay
intact as binary evidence; BTL_MES has 29 unbound blank rows and one deliberately
bound blank row, while BTL_SRF has 160 blank rows.

The byte and word pointer banks are compacted into their proved translated body
locations and reparsed under exact capacity checks. Item and ability names are
allocated into verified description padding and selected by the mature runtime's
per-record pointer without changing the 96-byte record shape. All six outputs
are byte-identical to the trusted mature Saturn build. There is no fallback to
hand-maintained runtime prose.

## COMP-core repacking

The `comp` target rebuilds `NORMHELP.DAT` and `DVLNAME.DAT` from the same
human-facing assets used by battle, Fusion, and the Compendium. All 24 help
records use the measured 300-pixel, two-row COMP surface and retain their fixed
42-word records. Of the 319 demon names, 210 fit the retail eight-byte/64-pixel
direct slot and are written into `DVLNAME.DAT`; the other 109 retain their stock
record bytes and are supplied in full by the COMP party-panel runtime's compact
overflow pool. Both outputs are byte-identical to the mature Saturn build.

This split is physical, not editorial. Every demon still has one complete
editable name in `assets/text/demons.json`; the repacker and runtime decide
which storage path can display it without truncation.

The game manifest covers 162 physical files and 61 source groups. Its four
container types are EVE banks, pointer banks, fixed records with subfields, and
explicit addressed spans. The generated corpus contains 16,129 records: 12,711
text-bearing EVE pages and 3,418 other records. All 144 dungeon-location rows
remain distinct instead of collapsing to 24 repeated Japanese strings. Each
row now verifies that its name bytes agree across the MAZE, AUTOMAP, SAVE, and
LOAD tables; these four physical copies still produce one catalogue record.
SAVE/LOAD's previously omitted `Lv`, `YES`, `NO`, date slash, time colon, and
basement-floor scaffold are now explicit records. Identical EMPTY, special
location, `Lv`, punctuation, and floor copies are validated across SAVE and
LOAD instead of being inferred from one file. The direct three-cell LOAD
capacity record at `0xB1AE` remains independently catalogued.
The additional 56 landing records across 17 ELV files and 232 records across
all 98 KAI files are separate physical corpus entries. Exact offsets, complete
source hashes, owned-region hashes, and the KAI file-catalogue digest fail
closed; every record binds back to an existing semantic place rather than
creating another translation.

The consumer audit added four physically grounded source groups containing five
record families that the earlier registry omitted: all 66 independently
indexed Combat Analyze affinity slots, two padded combat-result labels, 16
EVENT drink names and six Talk-role labels from one EVENT bar group, and one
healing all-members label.
Equal compact-affinity values remain distinct physical records, just like
repeated dungeon-location rows; semantic assets may explicitly share them
later. The healing label is assembled from the seven FONT16 glyph-index bytes
consumed by its code-immediate renderer.

The status audit adds 24 independently addressed stock-ASCII records from
`NORMCOM.BIN`: nine readout prefixes, all four control ranks plus the retail
fallback, three party-alignment values, and seven AUTO command values. Their
semantic bindings retain complete editable templates such as `HP
{current_hp}/{maximum_hp}` and `CTRL {rank}` rather than leaving punctuation or
word order in renderer code.

The DA_3D Analyze inventory adds 60 more physical records: all 43 compact
FONT8 race rows, seven grid headings, four detail prefixes, two skill-cost
units, and the four stored alignment-axis labels. The one retail `L` record is
explicitly bound to both the independently editable Law and Light fields. The
M and H records are suffixes of complete typed cost templates, while the grid
and detail LV/HP/MP/CP records reuse the shared status templates. This leaves
no player-visible Analyze label as an unowned renderer literal.

The MAZE suffix at `0x251dc` has three proved consumers: successful item
acquisition, yen acquisition, and magnetite acquisition. The two currency paths
prefix source glyph `0x00c0` (yen) or `0x00c1` (magnetite), then the formatted
amount, before appending the shared suffix. Its authored binding therefore fans
out to separate item, yen, and magnetite templates instead of assigning prose
or symbol choice to runtime code.

The compendium manifest covers the 292 physical `DVL_*.DAT` profile files as
one repeated fixed-record source. Each file contributes origin, summary, and
detail fields from its exact text tail. Three focused `A_DIC.BIN` sources cover
the independently rendered 319-demon-name table at `0x5d9b0`, the
255-ability-name table at `0x69be4`, and the 48 proved race-label records at
`0x5eda0`. Together they produce 1,498 records in four generated catalogues.
Tail-only identity checks allow future profile-image changes in the DVL files
while still failing on any changed text byte.

Other `A_DIC.BIN` sections remain outside the manifest. Read-only discovery
proves 48 race-description layouts and 11 fusion-help rows. The description
layouts mix labels, prose, and an unexplained marker, while adjacent regions are
lookup or executable data. Those sections will get focused inventories rather
than being folded speculatively into the profile source.

`corpus/<disc>/` is a generated physical catalogue. Its file grouping is not an
authoring interface. Mature translations are imported only into the shared
authored assets after a semantic binding is proved; stable physical IDs allow
that view to evolve without weakening binary grounding.

The extraction manifest records only data that extraction consumes. General
EVENT output-side packing lives in `config/event_codec.json` and
`util/event_repack.py`; the corresponding runtime renderer and fetch hook live
under `saturn/engine`. Those contracts now have executable behavior without
adding output concerns to source extraction.

IDs are derived from pointer slots, fixed-record positions, addressed offsets,
or EVE message/page positions. EVE page numbering includes the 166 structural
pages that do not themselves produce translation records. It never depends on
Japanese content or a relocatable body address.

Extraction validates full stock hashes for text-owned files. Shared executable
overlays also carry a digest over the exact text regions they own, allowing
unrelated visual or later engine changes to compose safely. The current
`SAVE.BIN` and `LOAD.BIN` visual changes pass for that reason; changing any owned
text byte still fails closed.

Only `translation` and `note` are retained by stable ID. Reference text,
encodings, ordering, and JSON formatting are regenerated. Orphaned IDs,
overlapping source ownership, changed framing, stale generated fields, and
unmanaged corpus files are errors. `--check` performs no writes.

## Encoding boundaries

An alphabet maps numeric glyph indices to their original readable values.
Font-backed alphabets are loaded from the independent per-disc font definitions,
so the game and compendium `FONT16.FON` files cannot be confused. Small custom
code tables are declared centrally beside them rather than inside a physical
source. A source encoding combines one or more alphabet ranges with a code-unit
codec and a control vocabulary. This is enough to represent the game's 8-bit
tables, 16-bit EVENT and combat text, the two-font 8-bit battle-message
alphabet, and indexed configuration labels without making any of them
file-specific.

Zero handling is also explicit per encoding. Mixed-font dialogue encodings skip
zero words, while FONT12 and direct fixed records may treat each zero as a
space. Fixed and mirrored tables use separate run-separator modes that ignore
leading and trailing zeroes and collapse each internal run to one space or
newline.

Only formats demonstrated by the discs are configured. The current inventory
uses big-endian 16-bit glyph words, 8-bit glyph codes (including FONT16 indices
stored as one-byte code operands), and printable ASCII; no Saturn source has
established a Shift-JIS encoding.

The compendium font remains independent from the game font. Its mapping now
covers all 1,703 nonzero glyph codes demonstrated by the 292 profile tails.
Three duplicated Unicode values occupy six physical codes, so their 29 profile
occurrences remain lossless `{GLYPH:xxxx}` tokens rather than collapsing numeric
identity. No replacement-font or renderer contract is implied by this source
mapping.

Containers remove record terminators and structural padding; codecs apply only
the selected encoding's declared zero meaning. This keeps the same encoding
reusable across fixed fields, pointer tables, and mixed record files.

## Text tokens

Decoded text remains readable while preserving values that are not safely
mapped:

- `{n}`, `{WAIT}`, and `{first_name}` are named controls or glyphs.
- `{GLYPH:0342}` is an unknown or ambiguous 16-bit glyph.
- `{OP:801e}` is an unknown 16-bit control operation.
- `{{` and `}}` represent literal braces.

Raw 8-bit values use two hexadecimal digits. Unknown controls are never dropped,
and duplicate atlas values remain raw so their numeric identity is not lost.

Bindings can ground a complete runtime template with
`composition.source_role: "scaffold"`: removing its declared value
placeholders must leave exactly the physical literal record. This proves the
SAVE/LOAD `Lv`, slash, colon, and `地下…階` records without introducing duplicate
fragment assets. `substitutions` handles a different case, where a stored full
record materializes another placeholder-free asset field. SAVE/LOAD uses it to
compile the single `capacity_number.text` value into every capacity message;
reference and translation substitution operate on parsed named tokens, so
escaped literal braces cannot be rewritten accidentally.

## Consumer limits

`config/surfaces.json` is a platform display contract, not an authored-text or
binary-storage catalog. Each surface has separate `ja` and `en` layouts with an
explicit font, row count, and width measured in either glyph cells or pixels.
Layouts may also declare an independent `glyphs` ceiling when a proportional
renderer has both a pixel boundary and a finite encoded-row buffer.
`null` means that a limit has not been established; the loader rejects omitted
fields and partially specified widths so an unknown value cannot silently
become a guessed constraint.

The English event and battle-negotiation windows are separate consumers with
the documented 300-pixel, three-row patch geometry. The battle console is fixed
at 16 cells by three rows in both languages. Demon Chat is 11 Japanese cells or
176 translated pixels by two rows, and battle help is 20 Japanese cells or 300
translated pixels by two rows. Battle item, skill, and party names use measured
80-pixel rows; Analyze names and compact affinities use 112 pixels, while its
race heading remains an eight-cell fixed FONT8 field. The result-name field is
88 pixels. The ritual console has a proved 176-pixel English width, but its row
count remains explicit `null` until measured. The negotiation choice field is
10 Japanese cells or 150 translated pixels on one row. Location
contracts now distinguish
the two-row 64-pixel 3D name, its 64-pixel floor row, the 112-pixel automap text
after the runtime-owned marker icon, the 112-pixel special SAVE/LOAD location,
and the 144-pixel generated dungeon label. SAVE/LOAD additionally records the
128-pixel joined-name strip, four-cell/64-pixel level field, five-cell/80-pixel
date and time fields, five-cell/80-pixel empty state, 11-cell/176-pixel prompt,
and three-cell/48-pixel confirmation choice. Its small messages are three rows
of 11 cells or 176 pixels, capacity messages two rows of 17 cells or 272
pixels, and its four- and six-row warnings use the proved 20-cell/320-pixel
geometry. Heading and storage-selector surfaces remain explicitly image-owned.
SAVE/LOAD English layouts record both limits: special/dungeon location rows
allow 16/24 encoded glyphs, the joined name 17, level 4, date/time and EMPTY 5,
prompts 11, choices 3, small-message rows 24, capacity-message rows 25, warning
rows 63, and the capacity value 3. Passing the pixel check alone is therefore
not sufficient for unusually narrow text.
MAZE
talk choices retain one 48-pixel row, and the three-row AUTOMAP marker popup is
limited to 64 pixels per row in English. Other English limits remain unknown
until their translated renderers are measured.
Facility contracts additionally distinguish the eight-cell bar and healer
lists, two-row drink help, and the shop's 16-pixel `Inv.` label. Unmeasured
facility widths remain explicit `null`s.
Profile-entry contracts retain the stock three/three/eight/three/three input
limits and the English patch's eight-character first, last, codename, city,
and ward fields. They also record the 13-cell English grid rows, 96-pixel tab
bands, 128-pixel occupation columns, and 208-pixel confirmation value area.
Character names have separate consumer contracts: the shared party-panel pool
is limited to 80 pixels and the shop information field to 72 pixels, while
the level-up character texture retains eight Japanese cells and the mature
96-pixel English safe limit. The main LEVEL_UP title, remaining-point display,
accept action, and confirmation choices use their proved fixed FONT8 slots.
Status vocabulary has separate contracts for the 12-pixel compressed parameter
nodes, 46-pixel derived and combat-stat rows, and 38-pixel Loyalty/personality
rows. The stock Japanese labels retain their distinct one-to-four-cell limits;
the fixed TYPE label remains a four-cell FONT8 consumer. CTRL ranks are three
FONT8 cells, AUTO command values and party alignments are seven cells, and the
two alignment axes use editable one-cell labels. The complete AUTO and P.A.
rows occupy twelve fixed FONT8 cells, with their seven-cell values beginning at
x=40. CTRL occupies ten cells, with its three-cell rank beginning at x=56.
These are composed slots: the cells between a prefix and its value are layout,
not extra translator capacity. Numeric draw starts are now recorded as x=40
for LV/CP, x=80 for EXP/NEXT, and x=40/x=48/x=80 for the HP/MP current value,
separator, and maximum value. Their final numeric right edges are still
unproved, so `status.numeric_readout` remains explicitly width-unknown. The
Loyalty number likewise begins at x=72 after its independently rendered
38-pixel label, but its final edge remains unknown; TYPE and its 38-pixel
personality value are also retained as separate, non-fungible components.
The 3D-map Analyze grid is a separate FONT8 consumer on a 352-pixel raster.
Its seven header columns begin at x=28, 80, 156, 202, 236, 264, and 300 and
have respective 52-, 76-, 46-, 34-, 28-, 36-, and 52-pixel contracts. Sixteen
rows begin at y=32 in 12-pixel steps; race and name translations have 52 and
84 pixels before the dynamic values at x=164, 208, 244, 280, and 316. The
selected-demon detail view retains 126 pixels for its FONT16 name, 46 pixels
for its FONT16 race, a 96-pixel numeric row, six 80-pixel FONT8 skill names,
16-pixel typed cost forms, and the existing 128-pixel two-row affinity surface.
The separate Learned Magic texture is 144x32 with two FONT16 rows. Its heading
uses five Japanese cells and a conservative 128-pixel English contract; the
ability row uses eight Japanese cells or 128 English pixels.
The Level Up name texture likewise distinguishes the five fixed character
assets (96px) from the live player codename (the full 128px row).
Options-menu contracts retain the nine-cell setting-label and four-cell value
limits while leaving their translated widths unknown. The ordering popup has
four 80-pixel translated rows, controller actions have one 128-pixel row, and
the two footer states have one 144-pixel row. These are consumer limits; local
compound glyphs and action-atlas chunks are derived output artifacts.

Typeface selection is also a consumer contract, not authored punctuation.
`config/glyph_sets.json` assigns the `font8_stock_latin` handler to the battle,
COMP, shop, bar, healer, and status command surfaces, the status AUTO, P.A., and
alignment-axis compositions, every fixed FONT8 Level Up label/readout, and the
DA_3D Analyze headers, numeric prefixes, and cost units. That handler selects
FONT8's named `stock_latin` reference set, preserving the retail appearance of
labels such as `GO`, `COMP`, `BUY`, `EQUIP`, and `LEVEL UP`. Other FONT8
consumers continue to use the normal narrow-English mapping. No inline token or
capitalization heuristic chooses between the two faces. The named stock set also
publishes the source-preserved hyphen, full stop, and slash cells used by fixed
numeric fallbacks and punctuation.

LEVEL_UP extraction now covers all eleven proved visible records: the fixed
FONT8 `LV`, `HP`, `MP`, `EXP`, `NEXT`, `LEVEL UP`, `LEFT`, `YES`, `NO`, and
`OK` fields plus the FONT16 `魔法を習得` heading. The physical spans begin
`LEFT` and `NO` at their first visible letters, so the preceding four ornament
cells and one centering cell remain layout rather than authored spaces. The five
numeric prefixes bind to the existing typed status templates; the other fields
bind to `assets/text/ui/level_up.json`, including the complete typed
remaining-point form and the mature `Learned Magic` translation. That asset also
owns the runtime-constructed maximum-level `-------` and no-MP `---/---`
fallbacks; the latter's post-slash alignment cell remains renderer layout. Their
lack of corpus IDs is explicit because they have no stored text record.

The physical catalogue includes the 16-entry battle action table at all three
proved COMBAT, MAZE, and NORMCOM locations, the four item/skill actions, the
five COMP commands, and twelve shared facility commands. Compound stock cells
for `REVIVE` and `STATUS` are normalized by explicit binding maps rather than
being taught to the general source decoder. The primary battle selectors for
`FIGHT`, `TALK`, `ESCAPE`, `AUTO`, `PRESET`, and `REPEAT` are still unlocated;
their wording is editable, but they remain recorded consumer-binding debt.

## Implementation plan

1. **Complete:** implement strict configuration loading, lossless token syntax,
   and reusable source decoders.
2. **Complete:** extract the complete game-disc text inventory with a new
   physical-ID contract and no content deduplication.
3. **Complete:** add all 292 compendium profiles and the proved demon-name,
   ability-name, and race-label `A_DIC.BIN` tables, while keeping other mixed
   sections evidence-only.
4. **In progress:** establish the shared human authoring view and import only
   translations and useful notes from the mature corpus. Item, equipment,
   field-message, location, demon, race, affinity, magic, skill, all 15
   negotiation-style, facility, SAVE/LOAD, character, profile-entry, status,
   battle-consumer, and Options-menu slices are complete. The battle slice binds
   every visible BTL_MES and BTL_SRF row while retaining their 29 and 160 blank
   rows as physical evidence, and its 16 BOSSTALK refusal messages now live in a
   separate reviewed boss-dialogue asset. SHOPSMP's 763 physical pages bind to
   595 shared authored lines without copying exact PSP text; its seven PSP-only
   tutorial lines remain explicit additions. The six shared character rows
   likewise need no PSP copies. All 19 physical profile-entry records retain
   exact semantic bindings, including the three deliberate same-source forks;
   the opening event workflow adds 18 mature Saturn pages to the same shared
   profile-entry asset without creating a platform-specific copy. All four
   general-event banks are also complete: 1,103 text-bearing message
   groups and 2,028 physical pages bind to 1,890 human-facing fields arranged by
   location, scene, or consumer rather than by event-bank coordinates. Their 138
   repeat and cross-bank uses are explicit binding fan-out instead of duplicated
   editable translations. The two structurally empty `EVFILE_1` messages remain
   binary framing rather than editor rows. Retail placement-error messages remain
   editable assets because visible debug text is not a runtime exemption.
5. **Complete for `event.dialogue`:** prove output glyph coverage, capacity,
   and the stable packed dictionary for all four general EVENT banks.
6. **Complete for `event.dialogue`:** implement atomic, round-tripped bank
   repacking with exact mature-output parity.
7. **Complete for `event.dialogue`:** port the surface-bound VWF renderer and
   packed fetch hook, then integrate both text and engine outputs into the
   normal disc build.
8. **Complete for `battle.negotiation`:** rebuild all sixteen EVE banks, fixed
   prompts and conditions, dynamic names/items, and port the surface renderer
   and packed fetch hook into the normal disc build.
9. **Complete for `battle.ui`:** rebuild the console, Demon Chat, help, ritual,
   item, and ability text banks; port the shared battle renderers, Analyze and
   result fields, dynamic names, and both packed readers into the normal build.
10. **Complete for `comp.menu` core:** rebuild the COMP help and direct demon
    name tables, then compose the party panels, item/magic grids, full-name
    pointer reader, and ritual decoder into the normal build.
11. **Complete for `equipment.ui`:** compose the shared COMP and shop equipment
    labels, item-name readers, stat headings, inventory label, and fixed
    character-name pool from editable assets on top of the checked EVENT and
    NORMCOM stages. Its SH-2 implementation is readable source under
    `engine/asm/`, with surface code isolated under `engine/surfaces/`.
12. **Complete for `status.ui`:** compose the human and demon detailed-status
    renderers, labels, names, race/affinity text, command fields, axes, and full
    templates from editable assets on top of the checked equipment NORMCOM
    intermediate. All executable changes are readable assembly, and the final
    binary matches the mature Saturn output exactly.
13. **Complete for `options.ui`:** derive the expanded labels, popup compounds,
    controller-action atlas, and footer packing from all 38 live editable
    fields. The zero-length `CONFIG` table row is retained as dormant data; the
    visible serif heading is graphical. The readable engine stage matches the
    mature `CFG_SET.BIN` output exactly.
14. Continue with the bounded MAZE field-message and dungeon-location consumer
    family; do not introduce one global repack or engine capability graph
    before another consumer needs shared machinery.

Extraction verifies source files, decodes every record readably, preserves
unknown glyph and control identity after declared zero normalization, and
retains user-owned text by stable ID. EVENT repacking independently reads the
verified source disc, resolves the authored bindings, enforces capacity, and
reparses every generated bank.

The new package intentionally does not inherit the mature format-class tree,
global semantic registry, per-page hash manifests, automatic Japanese-text
deduplication, migration wrappers, capability graph, browser editor, or mature
test hierarchy. Focused local tests cover extraction, authored assets and
bindings, and surface contracts.
