# Devil Summoner Translation Tools

Tools for translating and modifying *Shin Megami Tensei: Devil Summoner*. The
repository builds an English version of the Japanese Sega Saturn release
(Rev. B) from a clean copy of the disc, and contains the beginnings of a PSP
port of the same work.

This is not a release, and I'm not planning to keep working on it. It's here so
anyone who wants to pick it up can.

## Status

| Target | State |
| --- | --- |
| Saturn game disc (Rev. B) | Basically feature-complete. All of the game's text, fonts, menus, FMV subtitles and translated graphics are built. It still needs a proper editing pass and a full playthrough. |
| Saturn *Akuma Zensho* disc | **Broken.** The build produces an image, but the translated compendium does not work correctly in game. Don't rely on it. |
| PSP | **Very incomplete.** A number of individual screens are translated and build cleanly (see [`psp/README.md`](psp/README.md)), but most of the game is still in Japanese. |

The English script has not had a full editorial review. Expect typos,
inconsistent terminology, and the occasional line that doesn't fit.

## AI Disclosure

This repository was developed with the assistance of AI tools. While I believe that current AI products are inflicting tremendous social, economic, and environmental harms, I also believe that, when used and deployed responsibly, the underlying technology has genuine potential and value for humanity, particularly in the fields of open-source software development, preservation, and accessibility.

If you're dissatisfied with this, I encourage you to fork this repo, or otherwise create your own tools, translation, and/or documentation.

## Repository layout

| Directory | What's in it |
| --- | --- |
| `assets/text` | The translation itself: shared, platform-neutral JSON. This is what you edit. |
| `assets/image` | Replacement artwork (PNG). |
| `assets/font` | Open-source typefaces used to generate the game fonts. |
| `saturn/` | Saturn extraction, text/font/graphics repacking, engine patches, and the disc build. |
| `psp/` | The partial PSP port, with the same general structure. |
| `tools/` | A local, browser-based translation editor. |

Each package has its own README with more detail.

## Building the Saturn version

### Requirements

- Python 3.10 or newer
- [Pillow](https://pypi.org/project/pillow/) (`python -m pip install Pillow`)
- Your own copies of both Saturn discs as BIN/CUE:
  - *Shin Megami Tensei: Devil Summoner* (Japan, Rev. B)
  - *Shin Megami Tensei: Devil Summoner - Akuma Zensho* (Japan)

The build currently expects both discs, even though the *Akuma Zensho* output
isn't usable.

### 1. Add the original discs

Put the untouched BIN/CUE files in
[`saturn/rom/original/`](saturn/rom/original/README.md). The expected filenames,
sizes and SHA-256 hashes are listed in
[`saturn/rom/discs.json`](saturn/rom/discs.json), and the build will refuse
anything that doesn't match.

Disc images (original or built) are ignored by Git. Don't commit or share them.

To extract and check the discs on their own:

```powershell
python -B saturn/rom/extract.py
python -B saturn/rom/extract.py --check
```

This writes the disc contents to `saturn/rom/extracted/`. The full build
re-extracts over that directory, so don't make edits there.

### 2. Build

```powershell
python -B saturn/build.py --plan    # show what will run
python -B saturn/build.py           # build
python -B saturn/build.py --check   # verify the outputs are up to date
```

The build regenerates fonts, text, engine patches and graphics, then rebuilds
both discs into:

```text
saturn/rom/build/game/
saturn/rom/build/compendium/
```

Use the image in `build/game/` with an emulator or real hardware. The build
makes full disc images for your own testing; it does not make a distributable
patch.

## Editing the translation

### Text

The translation lives in the `translation` fields of the JSON files under
[`assets/text/`](assets/text/README.md). Leave the `reference` (Japanese) text
and any tokens such as `{n}` alone; tokens stand in for things like button
icons or names that the game fills in. The files under `saturn/text/corpus/` are
raw extracted data, not something to edit.

Many screens have tight width or line limits. The build checks these and will
fail if a line doesn't fit. [`assets/consumers.md`](assets/consumers.md) and
[`saturn/text/README.md`](saturn/text/README.md) describe the limits for each
screen.

The translation editor is easier to work with than the raw JSON. It lets you
search the text, previews lines in the actual game font, and flags anything
that won't fit:

```powershell
python -B -m tools.editor
```

It's also available as **Open Translation Editor** in the VS Code launch
configurations. See [`tools/README.md`](tools/README.md).

### Images

Replacement art is in `assets/image/`. To replace a new image, extract the
originals, copy the one you want from `saturn/visual/extracted/<disc>/` into
`assets/image/`, and add an entry for it in the catalog and the Saturn
bindings:

```powershell
python -B saturn/visual/extract.py all
python -B saturn/visual/repack.py all
python -B saturn/visual/repack.py all --check
```

Don't hand-edit the files in `extracted/` or the hashes in the manifests.
[`saturn/visual/README.md`](saturn/visual/README.md) covers the supported image
formats and the awkward cases (stitched textures, palette-limited title art).

### Fonts and other languages

The source typefaces and their licenses are in
[`assets/font/`](assets/font/README.md). The per-disc font definitions in
`saturn/font/config/` decide which typeface goes where and how glyphs are
packed.

```powershell
python -B saturn/font/extract.py all
python -B saturn/font/repack.py all
python -B saturn/font/repack.py all --check
```

Translating into another language is possible, but swapping the typeface is
usually not enough on its own: you may also need to change character maps,
text encodings, and the patched text renderers. The editor can set up a new
language project and import a font for it; see
[`saturn/font/README.md`](saturn/font/README.md) and
[`assets/languages/README.md`](assets/languages/README.md).

## Tests

```powershell
python -m unittest discover -s saturn/font/tests -v
python -m unittest discover -s saturn/text/tests -v
python -m unittest discover -s saturn/engine/tests -v
python -m unittest discover -s saturn/visual/tests -v
python -m unittest discover -s psp/visual/tests -v
```

Some tests need the original discs in place. Without them you can still inspect
the build with `--plan`, `--list-steps` and `--list-profiles`.

## Documentation

- [Shared text assets](assets/text/README.md)
- [Shared image assets](assets/image/README.md)
- [Language projects](assets/languages/README.md)
- [Per-screen text limits](assets/consumers.md)
- [Saturn disc extraction and rebuilding](saturn/rom/README.md)
- [Saturn text](saturn/text/README.md)
- [Saturn engine patches](saturn/engine/README.md)
- [Saturn fonts](saturn/font/README.md)
- [Saturn graphics](saturn/visual/README.md)
- [PSP status](psp/README.md)
- [PSP graphics](psp/visual/README.md)

## License

Code and documentation written for this project are under the BSD Zero Clause
License. Text and images taken from the game, and the screenshots below, are
not covered by it, and the bundled fonts keep their own licenses. See
[LICENSE](LICENSE) for details.

## Screenshots

From an earlier Saturn build that this tooling reproduces. FMV subtitles are
now drawn by the game at runtime rather than burned into the video.

| **Title** | **Fusion Table** |
| :---: | :---: |
| ![Translated title screen](saturn/docs/preview_screens/title.png) | ![Translated fusion table](saturn/docs/preview_screens/fusion.png) |
| **Equipment Screen** | **Event Choice** |
| ![Translated equipment screen](saturn/docs/preview_screens/equip.png) | ![Translated event choice](saturn/docs/preview_screens/event.png) |
| **3D Field Event** | **Inventory** |
| ![Translated 3D field event](saturn/docs/preview_screens/field.png) | ![Translated inventory](saturn/docs/preview_screens/item.png) |
| **Negotiation Choice** | **Shop** |
| ![Translated negotiation choice](saturn/docs/preview_screens/negotiate.png) | ![Translated shop](saturn/docs/preview_screens/shop.png) |
| **Settings** | **Status** |
| ![Translated settings](saturn/docs/preview_screens/settings.png) | ![Translated status screen](saturn/docs/preview_screens/status.png) |
| **FMV Subtitles** | **Name Input** |
| ![Translated FMV subtitles](saturn/docs/preview_screens/fmv.png) | ![Translated name input](saturn/docs/preview_screens/name.png) |
