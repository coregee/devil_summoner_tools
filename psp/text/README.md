# PSP text

The PSP text package follows the Saturn package's authored-asset and physical-
binding split. Repository-level `assets/text` files own player-facing wording;
PSP-local configuration owns archive members, offsets, capacities, character
codes, source hashes, and expected binary results.

The first complete surface is `title_help`. Its six English records come from
`assets/text/ui/title.json` and compile into the six fixed 42-word slots in
`regdata.bin` member 30. The publisher verifies the complete source file and
member identities, enforces the proved raw FONT16 code map, round-trips every
record, and reproduces the original project's exact same-size output.

```powershell
python -B psp/text/repack.py title_help
python -B psp/text/repack.py title_help --check
```

Generated `regdata.bin` and its provenance manifest live under
`generated/game/` and remain ignored.
