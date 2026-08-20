# Saturn ROM workflow

This directory treats the two original Saturn releases as separate discs with the
same workflow:

```text
original/             untouched source BIN/CUE files
extracted/game/        editable game-disc files
extracted/compendium/  editable Akuma Zensho files
build/game/            rebuilt game BIN/CUE
build/compendium/      rebuilt Akuma Zensho BIN/CUE
```

The scripts resolve project data from their own location instead of the current
working directory. The examples below assume the project root. With no disc
argument, each command processes both `game` and `compendium`.

## Current integration

`saturn/rom` owns media validation, extraction, ISO injection, sector repair,
and structural verification. It does not decide which translations to build.
The normal entry point is `python -B saturn/build.py`, whose configured default
profile restores both mirrors, installs the current font/text/engine/visual
outputs in dependency order, and then asks this package to rebuild both discs.

Use the commands below for focused media work. Generated files under
`rom/extracted/` are mutable integration mirrors, not authored sources; the
default build restores them from verified original media before applying any
translation package.

## Extract

```powershell
python saturn/rom/extract.py
python saturn/rom/extract.py game
python saturn/rom/extract.py compendium
python saturn/rom/extract.py --check
```

Extraction validates every source track against `discs.json`. It will create
missing files, but it will not silently replace a differing local file. Use
`--overwrite` only when deliberately restoring the mirror from the original
disc. `--check` requires the mirror to contain every ISO file, with no extras.

## Edit and repack

Edit files under the appropriate `extracted/<disc>/` directory, then run:

```powershell
python saturn/rom/repack.py --list
python saturn/rom/repack.py
python saturn/rom/repack.py --check
```

The repacker copies the complete source disc, injects only files that differ,
updates ISO9660 file sizes when needed, and regenerates Mode 1 EDC/ECC for every
changed sector. A file may change size only within its existing sector
allocation; the tool does not relocate, add, or remove ISO files.

Repacking refuses to replace an existing populated build directory unless
`--overwrite` is supplied. Publication is transactional: a new disc is fully
verified before it replaces the previous build.

The verification pass checks all of the following:

- the CUE and every audio track still match the source;
- each changed file reads back from the rebuilt ISO;
- ISO9660 extents and directory-record locations are unchanged;
- raw changes occur only in the edited file allocations and required directory
  records; and
- every changed Mode 1 sector has valid EDC/ECC.

An unchanged extraction must rebuild to a byte-identical BIN/CUE set. Emulator
testing remains necessary after real game-data edits; structural verification is
not a playtest.
