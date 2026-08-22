# Translation editor

The root `tools` package contains local, repository-aware developer tools. Its
first application is the translation editor:

```powershell
python -B -m tools.editor
```

The editor binds only to `127.0.0.1`, opens the canonical text assets under
`assets/text`, traces their Saturn consumer bindings, and validates proposed
translations before saving them. Known hard validation failures block writes.
Unknown surface measurements remain visible without being treated as success.
The text workspace is organised by game surface: selecting a surface filters
the editable fields to that context, and fields shared by several surfaces can
switch between a separate live preview for each one. Preview geometry converts
cell-based contracts to the selected font's physical pixels and row height.
The title surfaces use their positional `TITLE.BIN` rasters over the actual
title artwork rather than a generic text box.

The **Fonts** workspace exposes the Saturn text fonts and all catalogued PSP
font resources, their runtime cell formats, source typefaces, confidence and
consumer state, and editable replacement slots. Saturn `ICON.FON` is
intentionally omitted; the unresolved PSP ICON resource remains visible as
part of the comprehensive physical audit. Original and generated atlases are shown
side by side so typeface style and bitmap placement can be reviewed visually.
Each font uses a descriptive interface name rather than relying on its disc
filename alone.

The Saturn list also includes the two visual-owned `TITLE.BIN` glyph runs used
by `PRESS START BUTTON`, `START`, and `OPTION`. They are presented as read-only
fonts because they are positional RGB555 image records, not `.FON` resources.
Their checked stock mappings and individual glyph images can be audited in the
same workspace; profile-specific generation remains locked until the title
renderer can publish translated positional runs safely.

The glyph inventory pages through every physical cell, including stock,
replaceable, and previously unmapped cells. Values from checked definitions
remain editable in case a mapping is wrong. For an unmapped cell, the editor
suggests a value when its bitmap exactly matches one known glyph, and identifies
empty cells automatically. Saving a correction or suggested value validates
and updates the corresponding checked definition under `saturn/font/config/`;
any existing replacement mapped to that cell is preserved.

English is the built-in language project. The editor can create additional
projects such as French, record the characters they need beyond English, and
import a `.ttf` or `.otf` file for an individual game font. On import, missing
language characters are assigned to the least-used editable slots and a
language-specific `.FON`, atlas, and metrics file are generated. The base
English font remains unchanged. Every automatic assignment can then be
reviewed and edited from the glyph inspector.

Fixed, unresolved, and source-preserved fonts remain visible but read-only; changing those
requires a proved runtime mapping rather than an unsafe bitmap substitution.
PSP source identities can still be reviewed and saved to their checked
definitions. PSP raster rebuild controls remain locked until the corresponding
archive publisher and feature-specific ownership guards exist in this repository.
Imported typefaces are copied under `assets/font/imported/<language>/`; the
user is responsible for ensuring the typeface license permits the intended use
and redistribution.

Generated Saturn font binaries and metrics under `saturn/font/generated/game`
enable exact-font previews. If those artifacts are absent, corpus editing still
works and the affected measurements are reported as unavailable.

Use `--no-browser` to start the server without opening a browser, or `--port`
to select another loopback port.
