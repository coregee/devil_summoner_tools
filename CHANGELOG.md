# Changelog

## v0.2.3 (Saturn)

A bug-fix release. Apply it to the original **Rev. B** Track 1, not on top of an
earlier patch; see [PATCHING.md](PATCHING.md).

- **Ending credits:** the last two screens of the staff roll drew garbage in
  place of their empty rows, and the Test Player list repeated a Special
  Thanks name. Both screens now match the original layout.

## v0.2.2 (Saturn)

A bug-fix release. Apply it to the original **Rev. B** Track 1, not on top of an
earlier patch; see [PATCHING.md](PATCHING.md).

- **Escape lines:** when running from a fight, a demon's reply could wrap onto
  a third row below the chat window and stay on screen. Every escape line now
  fits on one row, and the build checks it. Four lines are reworded to fit.

## v0.2.1 (Saturn)

A bug-fix release. Apply it to the original **Rev. B** Track 1, not on top of an
earlier patch; see [PATCHING.md](PATCHING.md). It includes everything in v0.2.

- **Boss and special-character names:** in some fights, demons such as Yakou
  and Tenaga were named "Mysterious Man" in the TALK and Analyze windows. The
  patch kept the player's names in memory the game also uses for demon names,
  and overwrote the last part of that table. The names now live in unused space.

## v0.2 (Saturn)

A full revision of the English script against the Japanese. Apply it to the
original **Rev. B** Track 1, not on top of v0.1; see [PATCHING.md](PATCHING.md).

- **Story dialogue:** about 550 lines revised for accuracy and natural English,
  with consistent voices for Rei, Kyouji, Marie, Sid, Kumiko and the rest.
  Several lines that had the wrong speaker, target or tense are fixed.
- **Negotiation:** about 550 lines across the 15 demon personalities. Choices
  now match their questions, reactions match the choice, and lost puns are
  rebuilt in English.
- **Reply choices:** 27 choices that were too wide for their column (and were
  cut off mid-word in game) are reworded to fit.
- **Item and equipment names:** 24 corrected, e.g. Rime Moonlight, Halo Helm,
  Demonbane Ring, Sheragamo Boots.
- **Demon profiles:** about 140 fields corrected for accuracy and tense.
- **Facilities, battle and menus:** about 230 lines, including ritual console
  lines that used to run off the edge of their window.
- **Consistency:** a [style guide and glossary](assets/text/STYLE.md) now fixes
  names and terms across the script (Tendou-gumi, Chuo Ward, Otherworld, House
  of Fortune), and narration follows the tense of the Japanese.

Known issues:

- The script still hasn't had a full playthrough. Reports are welcome.
- The *Akuma Zensho* bonus disc is still **not** included.

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
