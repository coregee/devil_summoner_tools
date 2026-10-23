# Translation editor

A local, browser-based editor for the translation. Start it from the
repository root:

```powershell
python -B -m tools.editor
```

It runs on `127.0.0.1` only. Use `--no-browser` to start the server without
opening a browser, or `--port` to pick a different port.

## Text

The editor opens the JSON files under `assets/text` and groups them by game
screen. Picking a screen shows just the lines used there, with a preview drawn
in that screen's font and dimensions. Lines used on several screens can be
previewed on each of them. The title screen previews are drawn over the real
title artwork.

Edits are checked before saving. Anything that definitely won't fit is
rejected; anything the editor can't measure is shown as unknown rather than
passed.

The previews need the generated Saturn fonts in `saturn/font/generated/game`.
If those haven't been built yet, you can still edit text, but the size checks
that depend on them will show as unavailable.

## Fonts

The **Fonts** tab lists the Saturn text fonts and the known PSP fonts, with
original and generated glyph sheets side by side. Saturn `ICON.FON` is left
out. The two `TITLE.BIN` glyph runs used for `PRESS START BUTTON`, `START` and
`OPTION` are shown read-only, since they're image data rather than real fonts.

You can page through every glyph cell, including unmapped ones. Mappings can be
corrected if they're wrong. For unmapped cells, the editor suggests a character
when the bitmap exactly matches a known glyph, and marks empty cells. Saving
writes the change back to the font definition under `saturn/font/config/`.

Some fonts are read-only (fixed, unresolved, or kept as-is from the original)
because changing them would need a code change, not just new bitmaps. PSP fonts
can be inspected and their mappings edited, but can't be rebuilt from the
editor yet.

## Other languages

English is the built-in language project. You can create another one (French,
say), list the extra characters it needs, and import a `.ttf` or `.otf` for a
given game font. The editor assigns the new characters to the least-used
editable slots and generates a separate font for that language, leaving the
English font alone. You can review and change each assignment afterwards.

Imported fonts are copied to `assets/font/imported/<language>/`. Check that the
font's license allows the use you have in mind.
