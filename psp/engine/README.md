# PSP engine patches

This package ports PSP runtime changes into the same responsibility-oriented
layout used by the Saturn engine package:

- `surfaces/` contains one implementation per player-facing surface;
- `core/` contains strict configuration, binary patching, and Allegrex assembly;
- `asm/` and `config/` are readable, versioned build inputs; and
- `tests/` locks source guards, generated data, machine-code parity, and bounds.

The first ported surface is `title_help.ui`. It replaces the two fixed-width
title-help draw paths with one variable-width wrapper and a generated 268-byte
advance table. The wrapper is authored in Allegrex assembly rather than as a
Python-emitted machine-code blob. The builder accepts the title FONT16 advances
explicitly until the PSP font repacker owns their generated metrics.

`build_title_help_ui(stock, widths)` accepts the pinned decrypted `BOOT.BIN` and
the proved 95-entry packed printable-ASCII width order. It verifies the complete
stock file identity, both ELF relocation records, every edited instruction, and
both zero-backed cave spans before returning a same-size patched image. This is
not yet wired into a PSP disc build; publication should be added only after the
PSP ROM package owns extraction and the executable composition order.

Run the public engine checks from the repository root:

```powershell
python -m unittest discover -s psp/engine/tests -v
```

