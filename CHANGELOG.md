# Changelog

## v0.1 (Saturn)

First public release of the English patch for *Shin Megami Tensei: Devil
Summoner* on the Sega Saturn. It applies to the Japanese **Rev. B** disc; see
[PATCHING.md](PATCHING.md).

The whole game is translated:

- Story and event dialogue, battle negotiation and all demon conversation
- Menus, status, equipment, COMP, shops and facilities, save/load and options
- Battle messages, the city map, dungeon locations and automap
- FMV subtitles, drawn by the game at runtime
- Translated title screen, dungeon textures and other graphics

The text uses proportional (variable-width) fonts throughout. Names are drawn
in full rather than cut to a fixed number of letters, and name entry has
separate upper-case, lower-case and symbol grids.

Known issues:

- The script hasn't had a full editorial pass. Expect some typos and
  inconsistent terms.
- The *Akuma Zensho* bonus disc is **not** included. Its translation is in the
  repository but doesn't work correctly in game yet.

Everything used to make the patch is in this repository: SH-2 assembly sources
for every code change, documentation of the game's text formats, the
extract/repack pipeline, and a browser-based translation editor. Fixes, forks
and translations into other languages are welcome.
