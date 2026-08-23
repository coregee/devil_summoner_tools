# Devil Summoner: PSP Text Consumer Specs

This document describes any new or significantly-modified text surfaces present in the PSP version of the game.

## Title-menu help

The PSP title screen adds six contextual help records for Load, New Game,
Options, the special trailer, Normal difficulty, and Hard difficulty. Their
canonical wording lives in `assets/text/ui/title.json` under the `help_*`
entries. PSP-local bindings compile them into `regdata.bin` member 30 and render
their Latin glyphs from `datapack.bin` FONT16 page 0 through the title-help VWF
runtime.

## Configuration menu

The PSP CONFIG screen has 38 authored records in
`assets/text/ui/config_psp.json`. Twenty-seven main rows render through a
proportional Ark16 runtime, and Normal/Hard mode labels use right-aligned Ark12.
The remaining nine records are contextual help compiled into `regdata.bin`
member 14 slots 45–53 using the retained EVE character codes. The font stage
owns the coordinated Ark12/Ark16 allocations and exports their checked mapping
to the engine stage.

## Command-menu help

The PSP command menu stores 57 fixed 42-word rows in `regdata.bin` member 14.
Slots 45–53 are the CONFIG help records described above; command help owns
slots 0–44 and 54–56. Shared wording resolves from the general and battle help
assets. `assets/text/ui/command_help_psp.json` owns only the 34 PSP-exclusive or
capacity-specific states, avoiding a second authored copy of shared fields.
Printable ASCII uses the checked EVE bank at `0x1E20..0x1E7E`; `{n}` and the
two proved operation words remain structural controls.

## Battle console

The PSP battle console reads 358 indexed byte strings from `regdata.bin`
member 18. PSP-local bindings map 313 active rows to the canonical item, magic,
skill, and `assets/text/battle/console.json` fields and preserve 45 source-empty
rows. The native FNT8X12 codec permits at most 16 encoded cells and retains the
proved `n`-before-`m` lowercase order plus the `{NUM}`, `{OP:xx}`, and
`{GLYPH:xx}` controls. The text publisher compacts the body to member offset
`0x400`; two guarded BOOT instructions direct both native readers to that
composed body.

## Event window

The stock-safe EVENT VWF runtime and all five standard translated EVENT banks
are published. Compact PSP bindings join physical pages onto canonical semantic
fields through Saturn's checked EVE page identities; the 30 PSP-exclusive or
display-constrained lines live in `assets/text/events/event_psp.json`.
Markerless printable bytes use the same EVE glyph and advance contract as
command help. Raw-reader messages, eight explicitly native pages, big-endian
controls, and inline insertions remain lossless, while every bank receives the
same canonical 319-record DVLNAME runtime table.

## Boss combat dialogue

`eve_files.bin` member 22 contains 16 BOSSTALK messages displayed through the
common EVENT packed-byte renderer. They resolve one-to-one from
`assets/text/battle/boss_dialogue.json`, wrap to the same 300-pixel three-row
geometry, and preserve the combat VM's separate structural and color controls.
All 16 physical messages are reached by proved ordinary opcode-0 scripts; the
bank contains no combat-menu owner and needs no DVLNAME tail. It is composed
after the five standard EVENT members so only one final archive reaches the
ISO publisher.

## START2 news subtitles

`assets/text/fmv/subtitles.json` owns the nine presentation-relative cues for
the opening START2 news report. The PSP compiler converts centiseconds to
half-open `30000/1001` frame intervals, measures and centers each authored line
with the checked Ark Pixel 16 advances, and binds its 31 visible characters to
FONT16 codes `0x0672..0x0690`. The source PMF remains byte-for-byte unchanged;
the engine overlays one shadow and one face sprite per visible glyph only when
the selected movie basename is START2.

