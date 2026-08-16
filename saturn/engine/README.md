# Saturn engine patches

This package applies only the runtime changes required by translated consumer
surfaces. `build.py` reads stock binaries directly from the verified source
disc, applies every selected patch in memory, and writes ignored outputs under
`generated/<disc>/`. The normal Saturn build installs those outputs into the
editable disc mirror.

## Event dialogue

`config/event_dialogue.json` binds the `event.dialogue` surface to two proved
`EVENT.BIN` patch groups:

- `event_vwf` supplies the FONT16 variable-width renderer, menu paths, and the
  two-glyph typewriter pacing used by the mature Saturn translation.
- `event_packed_fetch` decodes the compact EVENT words emitted by
  `text/repack.py` using the exact configured dictionary table.

The patch image is data rather than another engine framework. Every site names
its purpose and records either its exact stock bytes or an exact zero-filled
cave size. The builder rejects changed input bytes, overlapping sites, wrong
font metrics, the wrong dictionary table, stale text outputs, and a final
binary that differs from the isolated mature patch digest. This retains the
proved SH-2 output without importing the mature repository's assembler,
capability graph, global build context, or unrelated consumers.

The same EVENT runtime renders the standard dialogue and direct FONT16 menu
records in `SHOPSMP.EVE`; shop dialogue does not have a separate text hook.

## Fusion menu

`fusion.menu` composes the general EVENT runtime with all Gouma-den consumers
that read the direct FONT12 records in `SHOPSMP.EVE`. It rebuilds the mature
5,786-byte Fusion runtime exactly from current shared assets and font metrics:
demon, character, full race, preview-race, and compact chart labels are all
editable data. It also ports the English name sort, list, preview, result table,
chart, Guide, Help, and confirmation paths.

The generated runtime is byte-identical to the trusted mature Saturn runtime.
The surrounding patches name each consumer and verify their stock bytes. The
six confirmation fields are rebuilt from the Gouma-den asset rather than stored
as prose inside the engine patch.

Run:

```powershell
python saturn/text/repack.py event
python saturn/engine/build.py event.dialogue
python saturn/engine/build.py event.dialogue --check
python saturn/text/repack.py shopsmp
python saturn/engine/build.py fusion.menu
python saturn/engine/build.py fusion.menu --check
python -m unittest discover -s saturn/engine/tests -v
```

Runtime code owns rendering, decoding, and substitution mechanics only. All
visible words, punctuation, symbols, and complete templates continue to come
from `assets/text` through explicit Saturn bindings.

## Battle negotiation

`config/battle_negotiation.json` binds the player-facing negotiation window and
choice fields to the proved COMBAT renderer and packed-text reader. The window
uses the same FONT16, 300-pixel, three-row display geometry as general EVENT;
choices use the renderer's measured 150-pixel column geometry.

The executable patch image remains fixed data. Demon names, race labels, item
names, and Kyouji's full name are rebuilt separately from shared authored
assets, so no visible runtime string is hand-maintained in engine code. The
dynamic pool matches the mature Saturn output while leaving growth space before
the fixed insertion routine. Condition messages and provisioning choices arrive
through the text build's generated `COMBAT.BIN`.

Run:

```powershell
python saturn/text/repack.py negotiation
python saturn/engine/build.py battle.negotiation
python saturn/engine/build.py battle.negotiation --check
python saturn/build.py default
```

## Shared battle UI

`battle.ui` composes the negotiation runtime with the remaining shared COMBAT
renderers and the NORMCOM ritual-console reader. It installs the mature FONT8
VWF paths for party panels, Analyze, lists, and results; the FONT16 Demon Chat
and help paths; and compact readers for `BTL_SRF.MDT` and `BUTU_SRF.MDT`.

The checked runtime images contain code and fixed layout only. FONT8 widths,
all 43 Analyze race-heading slots, 319 demon names, 66 compact affinities, both
result labels, and all six character names are regenerated from the current
font metrics and human-facing assets before the patches are applied. Item,
ability, console, help, Demon Chat, and ritual text arrive through the six files
produced by `text/repack.py battle`. No visible wording is maintained inside
engine code.

Every patch site verifies its expected input, the two packed readers reject a
decoded row larger than their 127-word scratch buffers, and all outputs match
the isolated mature Saturn patches byte-for-byte. The two result labels retain
the mature runtime's checked storage slots in addition to their measured
display limit; an oversized edit therefore fails during the build instead of
overwriting adjacent code.

Run:

```powershell
python saturn/text/repack.py battle
python saturn/engine/build.py battle.ui
python saturn/engine/build.py battle.ui --check
python saturn/build.py default
```

## COMP core

`comp.menu` composes the NORMCOM ritual decoder from `battle.ui` with the shared
FONT8 party-panel and item/magic-grid renderers, the complete item-name pointer
reader, and the full-width FONT16 help renderer. This boundary deliberately
stops before the separately proved equipment and detailed-status surfaces.

The runtime rebuilds its FONT8 width tables and all character/demon overflow
name data from the current font metrics, `characters.json`, `demons.json`, and
the generated `DVLNAME.DAT`. Names that fit the retail record stay direct;
longer names enter checked low/high compact pools without exposing that packing
to editors. The preassembled drawer is retained only as checked code: its data
addresses and the three caller pointers are rebound whenever the pools move.

`NORMHELP.DAT`, `DVLNAME.DAT`, `ITEMNAME.DAT`, and `MAGNAME.DAT` remain ordinary
file-backed text outputs. The composed NORMCOM result is byte-identical to the
same isolated mature capabilities and fails on changed source bytes, stale text
or metrics, overlong names, unsupported compact characters, or cave overflow.

Run:

```powershell
python saturn/text/repack.py comp
python saturn/engine/build.py comp.menu
python saturn/engine/build.py comp.menu --check
python saturn/build.py default
```
