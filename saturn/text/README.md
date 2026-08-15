# Saturn text

The text package is record-centric. A physical source describes where records
live, a container describes how those records are framed, and each record names
the source encoding used to turn its code units into readable text. Source
encodings never name a game file.

Repacking will make the same separation in the other direction: each record
will name an output encoding, while containers remain responsible for pointers,
terminators, padding, capacities, and file layout. During migration, a blank
physical translation retains the original record; canonical authored
translations live under the repository-level `assets/text` tree.

## Layout

- `config/encodings.json` defines reusable alphabets, control vocabularies, and
  source encodings.
- `config/surfaces.json` records measured Japanese and English consumer limits.
- `config/sources/<disc>/manifest.json` defines physical files, the four
  container shapes, defaults, and exceptional record-level overrides.
- `corpus/<disc>/` contains deterministic extracted physical records.
- `bindings/` joins Saturn physical records to shared authored asset fields.
- `../../assets/text/` is the human-facing, cross-platform authoring layer.
- `util/` contains strict configuration, token, codec, and container helpers.
- `generated/` is ignored and will contain dictionaries, coverage reports,
  capacity reports, and engine-facing payloads.
- `extract.py` verifies source identity and regenerates the complete corpus.
  `repack.py` remains absent until output encodings are settled.

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

The generated corpus is binary evidence, not the translation editor. Assets
are organised around entities and player-facing surfaces: the initial slice
groups all 287 ITEMNAME rows into 208 equipment entities and 79 item slots. The
item slots become 73 authored entries because the proven unused-reserve forms
are explicitly shared. Each name and description stays with its entity, all 48
physical battle-console forms bind to their item fields, and the MAZE field
suffixes become complete typed templates. Saturn bindings retain exact physical
grounding without putting file offsets or table indices into semantic asset
identities.

## Extraction

```powershell
python saturn/text/extract.py game
python saturn/text/extract.py game --check
python saturn/text/extract.py compendium
python saturn/text/extract.py compendium --check
python -m unittest discover -s saturn/text/tests -v
```

The game manifest covers 47 physical files and 55 source groups. Its four
container types are EVE banks, pointer banks, fixed records with subfields, and
explicit addressed spans. The generated corpus contains 15,704 records: 12,711
text-bearing EVE pages and 2,993 other records. All 144 physical dungeon-location
rows remain distinct instead of collapsing to 24 repeated Japanese strings.

The consumer audit added four physically grounded source groups containing five
record families that the earlier registry omitted: all 66 independently
indexed Combat Analyze affinity slots, two padded combat-result labels, 16
EVENT drink names and six Talk-role labels from one EVENT bar group, and one
healing all-members label.
Equal compact-affinity values remain distinct physical records, just like
repeated dungeon-location rows; semantic assets may explicitly share them
later. The healing label is assembled from the seven FONT16 glyph-index bytes
consumed by its code-immediate renderer.

The MAZE suffix at `0x251dc` has three proved consumers: successful item
acquisition, yen acquisition, and magnetite acquisition. The two currency paths
prefix source glyph `0x00c0` (yen) or `0x00c1` (magnetite), then the formatted
amount, before appending the shared suffix. Its authored binding therefore fans
out to separate item, yen, and magnetite templates instead of assigning prose
or symbol choice to runtime code.

The compendium manifest covers the 292 physical `DVL_*.DAT` profile files as
one repeated fixed-record source. Each file contributes origin, summary, and
detail fields from its exact text tail. A second source covers the independently
rendered 319-name table proved at `A_DIC.BIN` offset `0x5d9b0`. Together they
produce 1,195 records in two generated catalogues. Tail-only identity checks
allow future profile-image changes in the DVL files while still failing on any
changed text byte.

Other `A_DIC.BIN` sections remain outside the manifest. Read-only discovery
proves 48 race labels, 255 magic names, 48 race-description layouts, and 11
fusion-help rows. The description layouts mix labels, prose, and an unexplained
marker, while adjacent regions are lookup or executable data. Those sections
will get focused inventories rather than being folded speculatively into the
profile source.

`corpus/<disc>/` is a generated physical catalogue. Its file grouping is not an
authoring interface. Mature translations are imported only into the shared
authored assets after a semantic binding is proved; stable physical IDs allow
that view to evolve without weakening binary grounding.

The extraction manifest records only data that extraction consumes. Runtime
reader selection and output-side packing rules will be introduced with repacking,
once those contracts have executable behavior.

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

## Consumer limits

`config/surfaces.json` is a platform display contract, not an authored-text or
binary-storage catalog. Each surface has separate `ja` and `en` layouts with an
explicit font, row count, and width measured in either glyph cells or pixels.
`null` means that a limit has not been established; the loader rejects omitted
fields and partially specified widths so an unknown value cannot silently
become a guessed constraint.

The English event window is the documented 300-pixel, three-row patch surface.
The battle console is fixed at 16 cells by three rows in both languages. Other
English limits remain unknown until their translated renderers are measured.

## Implementation plan

1. **Complete:** implement strict configuration loading, lossless token syntax,
   and reusable source decoders.
2. **Complete:** extract the complete game-disc text inventory with a new
   physical-ID contract and no content deduplication.
3. **Complete:** add all 292 compendium profiles and the proved 319-name
   `A_DIC.BIN` table, while keeping other mixed sections evidence-only.
4. **In progress:** establish the shared human authoring view and import only
   translations and useful notes from the mature corpus. Item, equipment,
   field-message, demon-name, and Compendium-profile slices are complete.
5. Produce complete encoding coverage and capacity reports for both discs.
6. Finalize output encodings and deterministic full-corpus dictionary groups.
7. Implement one atomic text repack; partial dictionary builds remain
   unsupported.
8. Design engine hooks against the finalized output encoding contracts.

Extraction verifies source files, decodes every record readably, preserves
unknown glyph and control identity after declared zero normalization, and
retains user-owned text by stable ID. Later repacking will restore original
inputs, verify references by reparsing current files, train selected dictionaries
deterministically over the complete corpus, enforce capacities, and reparse every
generated output.

The new package intentionally does not inherit the mature format-class tree,
global semantic registry, per-page hash manifests, automatic Japanese-text
deduplication, migration wrappers, capability graph, browser editor, or mature
test hierarchy. Focused local tests cover extraction, authored assets and
bindings, and surface contracts.
