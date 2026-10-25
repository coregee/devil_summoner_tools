# Applying the patch

The English patch is a BPS file for the Japanese Sega Saturn release of
*Shin Megami Tensei: Devil Summoner*, **Rev. B**. Download it from the
[releases page](https://github.com/coregee/devil_summoner_tools/releases).

## What you need

A BIN/CUE dump of the Rev. B disc, split into two tracks the way Redump dumps
are:

```text
Shin Megami Tensei - Devil Summoner (Japan) (Rev B).cue
Shin Megami Tensei - Devil Summoner (Japan) (Rev B) (Track 1).bin
Shin Megami Tensei - Devil Summoner (Japan) (Rev B) (Track 2).bin
```

The patch only touches **Track 1**. It must match exactly:

| | |
| --- | --- |
| Size | 430,467,744 bytes |
| CRC32 | `e70c6b92` |
| SHA-256 | `9fb801057082ff482343a45667120ac2af5374ecdf848b22ec3d082922662b6f` |

Earlier revisions of the game won't work, and neither will a dump that has been
merged into a single BIN or converted to CHD/ISO. The patcher checks the CRC
and refuses the wrong file, so you can't end up with a half-patched disc.

## Steps

1. Make a copy of the whole disc folder. 
2. Apply `devil_summoner_en_v0.2.2.bps` to the **Track 1** BIN using one of:
   - [Floating IPS (Flips)](https://github.com/Alcaro/Flips/releases): choose
     *Apply Patch*, pick the BPS, then the Track 1 BIN, then where to save.
   - [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), in the
     browser. Nothing is uploaded, but the file is large, so it can take a
     while.
   - The script in this repository, if you have Python 3.10+:

     ```bash
     python -B saturn/rom/patch.py apply devil_summoner_en_v0.2.2.bps "Track 1 original.bin" "Track 1 patched.bin"
     ```

3. Save the patched file with the **original Track 1 filename**, replacing the
   unpatched one in your copy.
4. Open the `.cue` file in your emulator, or burn the BIN/CUE to disc.

To check the result, the patched Track 1 for v0.2.2 should be:

| | |
| --- | --- |
| Size | 430,467,744 bytes |
| CRC32 | `59bd82df` |
| SHA-256 | `2b22ff1fb27d278dd31a9921b5c00ab7d7228d9fad47c1071d9d7455c952bc5d` |
