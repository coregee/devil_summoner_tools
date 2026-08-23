# PSP BTL_MES battle console

BTL_MES is the PSP-native indexed byte-string table used by the battle
console. Canonical wording remains in the repository-level item, magic, skill,
and battle-console assets. `psp/text/config/btl_mes.json` owns the PSP member,
record indices, glyph codes, controls, capacities, and source hashes.

## Checked composition

`PSP_GAME/USRDIR/regdata.bin` member 18 is 5,082 bytes and contains 358
big-endian `uint16` offsets followed by a `0xffff` sentinel at member offset
`0x2cc`. Stock text begins at `0x800`; every message ends with byte `0x80`.
The publisher encodes 313 active rows, verifies 45 source-empty rows, and
compacts the body to `0x400` without changing the member or archive size.

- Encoded body: 3,136 of 4,058 bytes
- Zero-filled free tail: 922 bytes
- Output member SHA-256:
  `6d9cf516bbf0971b96bbf4b9ed54562f6108e27edcac1deffdb09fbee499630e`
- Composed members 14, 18, and 30 `regdata.bin` SHA-256:
  `960653dca478aec246be825dac99e3fb41e35d3792168ce421e173ad58795764`

The stock member-15 FNT8X12 resource is read-only codec evidence. Its physical
order includes lowercase `n` before `m`. Rows may contain at most 16 encoded
cells and may use the proved `{NUM}`, `{OP:xx}`, and `{GLYPH:xx}` controls.
The port deliberately resolves wording from the new canonical assets; this
keeps the corrected `7_Shooting_Stars` row rather than restoring the old
project's `8_Shooting_Stars` spelling.

Both executable readers originally add `0x800` to the member base. The engine
surface validates and replaces only these instructions:

| Module address | Stock bytes | Replacement bytes |
| --- | --- | --- |
| `0x0006b874` | `00 08 92 24` | `00 04 92 24` |
| `0x0006bb40` | `00 08 64 24` | `00 04 64 24` |

They are ordinary immediate edits, not relocations, and compose after the
existing title-help and CONFIG surfaces.

## Verification

Run from the repository root:

```powershell
python -m unittest psp.text.tests.test_btl_mes -v
python -m unittest psp.engine.tests.test_battle_console -v
python -B psp/build.py default
python -B psp/build.py default --check
```

Static checks do not replace runtime acceptance. In PPSSPP, exercise ordinary
item and ability rows, a 16-cell row such as `Cauterizing_Fist`, status labels,
and control-bearing results such as `Damage_{NUM}` through both battle-console
paths. Confirm rows redraw cleanly and preserved empty slots do not expose
compacted-body data.
