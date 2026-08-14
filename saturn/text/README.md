# Saturn text

The text package is record-centric. A physical source describes where records
live, a container describes how those records are framed, and each record names
the source encoding used to turn its code units into readable text. Source
encodings never name a game file.

Repacking will make the same separation in the other direction: each record
will name an output encoding, while containers remain responsible for pointers,
terminators, padding, capacities, and file layout. A blank translation retains
the original record.

## Layout

- `config/encodings.json` defines reusable alphabets, control vocabularies, and
  source encodings.
- `config/sources/<disc>/` will define physical files, containers, defaults, and
  exceptional record-level encoding overrides.
- `corpus/<disc>/` will contain the extracted translation records.
- `util/` contains configuration, token, codec, and later container primitives.
- `generated/` is ignored and will contain dictionaries, coverage reports,
  capacity reports, and engine-facing payloads.
- `extract.py` and `repack.py` will be added when the source inventory and output
  contracts exist; phase 1 deliberately does not add placeholder entry points.

The corpus record contract will stay small:

```json
{
  "id": "stable-record-id",
  "source_encoding": "game_font12_16_event_skip",
  "output_encoding": "packed_latin_u16be",
  "reference": "Original text{n}",
  "translation": "",
  "note": ""
}
```

Records are not deduplicated by content. Shared output is represented only by an
explicit alias.

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

Zero handling is also explicit per encoding. Mixed-font dialogue-bank readers
skip zero words, while FONT12 and direct fixed records may treat each zero as a
space. Fixed and mirrored tables use separate run-separator modes that ignore
leading and trailing zeroes and collapse each internal run to one space or
newline.

Only formats demonstrated by the discs are configured. The current inventory
uses big-endian 16-bit glyph words, 8-bit glyph codes, and printable ASCII; no
Saturn source has established a Shift-JIS encoding.

The compendium font has its own source encoding, but its atlas is intentionally
unmapped in phase 1. It therefore decodes to lossless `{GLYPH:xxxx}` tokens
instead of silently borrowing the game font. Its verified profile mapping is
added with the profile sources in phase 3.

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

## Implementation plan

1. **Complete:** implement strict configuration loading, lossless token syntax,
   and reusable source decoders.
2. Extract the complete game-disc text inventory without importing the mature
   repository's physical bindings.
3. Add all 292 compendium profiles and begin discovery of the mixed
   `A_DIC.BIN` sections.
4. Import only reference text, translations, and useful notes from the mature
   corpus.
5. Produce complete encoding coverage and capacity reports for both discs.
6. Finalize output encodings and deterministic full-corpus dictionary groups.
7. Implement one atomic text repack; partial dictionary builds remain
   unsupported.
8. Design engine hooks against the finalized output encoding contracts.

Later extraction will verify source files, decode every record readably, preserve
unknown glyph and control identity after its declared zero normalization,
retain existing translations by stable ID, and report unmapped coverage.
Later repacking will restore original inputs, verify references by reparsing the
current files, retrain selected dictionaries deterministically over the complete
corpus, enforce capacities, and reparse every generated output.

The new package intentionally does not inherit the mature format-class tree,
global semantic registry, per-page hash manifests, automatic Japanese-text
deduplication, migration wrappers, capability graph, browser editor, or tests
package.
