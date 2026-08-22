# PSP text

The PSP text package follows the Saturn package's authored-asset and physical-
binding split. Repository-level `assets/text` files own player-facing wording;
PSP-local configuration owns archive members, offsets, capacities, character
codes, source hashes, and expected binary results.

The first complete surfaces are `title_help` and `config_menu`. The title's six English records come from
`assets/text/ui/title.json` and compile into the six fixed 42-word slots in
`regdata.bin` member 30. The publisher verifies the complete source file and
member identities, enforces the proved raw FONT16 code map, round-trips every
record. CONFIG has 38 authored records in `assets/text/ui/config_psp.json`: 29
runtime rows feed the engine renderer, while nine contextual-help records
compile into fixed slots 45–53 of `regdata.bin` member 14. The composed
publisher reproduces the original project's exact same-size output.

```powershell
python -B psp/text/repack.py all
python -B psp/text/repack.py all --check
```

Generated `regdata.bin` and its provenance manifest live under
`generated/game/` and remain ignored.
