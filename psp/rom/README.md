# PSP ROM workflow

The PSP ROM package owns source-image identity, ISO9660 extent resolution, and
same-size publication. Place the supported Japanese ISO under `original/` with
the filename and SHA-256 recorded in `discs.json`. Original and generated media
remain ignored.

The current build changes 91 checked extents: five executable/text/font archive
files plus one title pack, 83 maze packs, the savedata pack, and `ICON0.PNG`.
Every other byte is streamed
directly from the verified source ISO. The visual manifest supplies four title
members and fifteen unique maze-family members; the ROM composer fans them out
to their packs without storing duplicate rebuilt archives. Every replacement
must match its component manifest before the output and aggregate provenance
manifest are written under `build/game/`.

Run the complete configured workflow from the repository root:

```powershell
python -B psp/build.py default --plan
python -B psp/build.py default
python -B psp/build.py default --check
```

`--check` reproduces the candidate digest, verifies all 91 replacement
extents, and rejects any difference outside them.
