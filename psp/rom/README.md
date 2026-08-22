# PSP ROM workflow

The PSP ROM package owns source-image identity, ISO9660 extent resolution, and
same-size publication. Place the supported Japanese ISO under `original/` with
the filename and SHA-256 recorded in `discs.json`. Original and generated media
remain ignored.

The current build changes only four checked extents: `BOOT.BIN`, `EBOOT.BIN`,
`datapack.bin`, and `regdata.bin`. Every other byte is streamed directly from
the verified source ISO. Each replacement must match its engine, font, or text
manifest before the output and aggregate provenance manifest are written under
`build/game/`.

Run the complete configured workflow from the repository root:

```powershell
python -B psp/build.py default --plan
python -B psp/build.py default
python -B psp/build.py default --check
```

`--check` reproduces the candidate digest, verifies all four replacement
extents, and rejects any difference outside them.
