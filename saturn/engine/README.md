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
Direct FONT12 fusion records share that physical bank but remain stock until
the fusion-menu consumer patch is ported.

Run:

```powershell
python saturn/text/repack.py event
python saturn/engine/build.py event.dialogue
python saturn/engine/build.py event.dialogue --check
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
