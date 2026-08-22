# Devil Summoner: PSP Text Consumer Specs

This document describes any new or significantly-modified text surfaces present in the PSP version of the game.

## Title-menu help

The PSP title screen adds six contextual help records for Load, New Game,
Options, the special trailer, Normal difficulty, and Hard difficulty. Their
canonical wording lives in `assets/text/ui/title.json` under the `help_*`
entries. PSP-local bindings compile them into `regdata.bin` member 30 and render
their Latin glyphs from `datapack.bin` FONT16 page 0 through the title-help VWF
runtime.

