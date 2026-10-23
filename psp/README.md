# PSP port

The PSP port is very incomplete. Most of the game is still in Japanese. What's
here builds cleanly and produces a working ISO, but only the screens listed
below are translated.

It uses the same shared translation in `assets/text` and the same replacement
art in `assets/image` as the Saturn version, with PSP-specific code for the
file formats, fonts, and runtime patches.

## What's translated

- Title screen help text
- CONFIG menu and command-menu help
- Battle messages (BTL_MES)
- Event dialogue in the five standard EVENT banks, plus boss-battle dialogue
  (BOSSTALK)
- Name entry and the player profile
- Battle party panel and results names, and the COMP party cards
- The 2D city map
- Demon Compendium names and descriptions, with English alphabetical sorting
- The three PSP-only items
- Save data: the PSP save menu shows an English title, codename, level,
  difficulty, location and playtime
- Dungeon location and floor display
- Title screen, dungeon wall textures, and the save icon
- Subtitles for the opening START2 movie

## What isn't

Pretty much everything else: shops and facilities, status and equipment
screens, the remaining menus, many fonts, and any artwork whose PSP layout
differs from the Saturn version (menu sheets, automap, loading screens and so
on). Those images will need their own PSP-specific assets.

## Building

Put the original Japanese ISO in [`rom/original/`](rom/original/README.md),
then from the repository root:

```powershell
python -B psp/build.py default --plan
python -B psp/build.py default
python -B psp/build.py default --check
```

The output ISO is the same size as the original; only the files that changed
are rewritten.

## Package layout

- [`text/`](text/README.md): maps the shared translation onto PSP text files
- [`font/`](font/README.md): catalogue of the PSP fonts and generated
  replacements
- [`engine/`](engine/README.md): executable patches (Allegrex assembly)
- [`visual/`](visual/README.md): PSP encoding of the shared artwork
- [`fmv/`](fmv/README.md): movie subtitles
- [`rom/`](rom/README.md): ISO checks and rebuilding

## Technical notes

Notes on individual screens, mostly for whoever works on this next:

- [Battle messages](docs/btl_mes.md)
- [Battle party panel and results names](docs/battle_names.md)
- [Command-menu help](docs/command_menu_help.md)
- [COMP party cards](docs/comp_party_panel.md)
- [Demon Compendium](docs/compendium.md)
- [Event dialogue window](docs/event_window.md)
- [Movie subtitles](docs/fmv_subtitles.md)
- [PSP-only items](docs/item_runtime.md)
- [2D city map](docs/map2d.md)
- [Name entry](docs/name_entry.md)
- [Save data](docs/savedata.md)
- [Text encodings](docs/text_encodings.md)
