# PSP text

The PSP text package follows the Saturn package's authored-asset and physical-
binding split. Repository-level `assets/text` files own player-facing wording;
PSP-local configuration owns archive members, offsets, capacities, character
codes, source hashes, and expected binary results.

The complete surfaces are `title_help`, `config_menu`, `command_menu_help`,
`battle_console`, the five standard `event_dialogue` banks, the BOSSTALK
boss-combat bank, and the BOOT-resident Demon Compendium. The title's six
English records come from
`assets/text/ui/title.json` and compile into the six fixed 42-word slots in
`regdata.bin` member 30. The publisher verifies the complete source file and
member identities, enforces the proved raw FONT16 code map, and round-trips
every record. CONFIG has 38 authored records in
`assets/text/ui/config_psp.json`: 29 runtime rows feed the engine renderer,
while nine contextual-help records compile into fixed slots 45–53 of
`regdata.bin` member 14. Command help owns the complementary slots 0–44 and
54–56. Shared states resolve from `assets/text/ui/command_help.json` and
`assets/text/battle/help.json`; only PSP-exclusive states live in
`assets/text/ui/command_help_psp.json`. The fixed 42-word capacity and EVE
printable-ASCII/control encoding are enforced for every row.

BTL_MES resolves 313 active rows from the canonical item, magic, skill, and
battle-console assets through `config/btl_mes.json`, while explicitly
preserving all 45 native empty slots. Its PSP-local codec validates the stock
72-cell FNT8X12 ordering, control bytes, and 16-cell row limit, then compacts
member 18 from body offset `0x800` to `0x400`. All three members are composed
from stock in one transaction, so no surface can erase another surface's
changes.

EVENT is a second transaction over the font stage's generated
`eve_files.bin`. Compact bindings under `config/event/` join 2,830 payload
pages to canonical `path#entry.field` identities and preserve eight native
pages explicitly. The compiler packs proportional prose, keeps direct-reader
options as guarded raw u16 words, and installs the same 319-record DVLNAME
table in members 0 through 4. The 30 PSP-exclusive or constrained fields live
in `assets/text/events/event_psp.json`; shared dialogue continues to resolve
from the general event and facility assets. The composed text-stage archive is
the ISO publisher's final `eve_files.bin` input, so its member-5 EVE font data
cannot be lost.

BOSSTALK is composed immediately afterward into member 22. Its 16 ordinary
opcode-0 messages resolve directly from `assets/text/battle/boss_dialogue.json`
and use the common packed EVENT cursor, but retain their distinct combat
control vocabulary: structural `0x8000..0x8004`, insert `0x8010..0x8017`, and
color `0x8020..0x8026`. The compiler proves that every message has exactly one
ordinary script owner and that no combat-menu reader is present before
publishing the member.

The Compendium binding in `config/compendium.json` preserves all 319 physical
pointer-table rows and resolves 292 live profiles through
`assets/text/demons.json`. Its compiler pools and wraps 876 canonical prose
fields into the fixed BOOT lore arena; the engine surface combines that output
with the shared 319-name DVLNAME table.

```powershell
python -B psp/text/repack.py all
python -B psp/text/repack.py all --check
python -B psp/text/event_repack.py all
python -B psp/text/event_repack.py all --check
```

Generated `regdata.bin`, the composed `eve_files.bin`, and their provenance
manifests live under `generated/game/` and remain ignored.
