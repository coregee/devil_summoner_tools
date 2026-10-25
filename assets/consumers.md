# Devil Summoner: Saturn Text Consumer Specs

This document describes how each on-screen text area in the Saturn game behaves,
and the size limits that the text, font, engine and graphics packages all have
to agree on. It's the readable companion to the Saturn surface catalogue
(`saturn/text/config/surfaces.json`).

Where a screen has been translated, there's a note on how the current patch
handles it. Things that haven't been measured or worked out yet are marked as
such. An unmeasured limit doesn't mean the screen isn't translated.

These are described from the player's point of view. The game may draw
similar-looking screens through different code for its own reasons.

Every bit of text the player can see, including labels, fragments and
templates with values filled in, should have an editable entry under
`assets/text`. That includes text that's already in English and text drawn from
code or images. Code may pick an entry, fill in values, format numbers, measure
and draw it, but it shouldn't contain visible wording or punctuation itself.
Where this document says something doesn't need a hook, it only means no
special renderer change is needed right now.

### Title Screen

The game has the logos for "真・女神転生" and "デビルサマナー" scale down onto the title screen.

There is also the logo "悪魔召喚師" (literally Devil Summoner, in Japanese). The current English version may leave this logo untranslated, but its text and image should still be editable.

The title screen itself is another image, displayed after a white flash transition. These three logos are pre-baked into it.

The `PRESS START BUTTON` prompt and the `START` / `OPTION` menu labels are
separate from that baked screen. `TITLE.BIN` stores them as two runs of
positioned RGB555 glyph images: sixteen 16x12 images for the prompt, and eleven
16/8x9 images for the two menu labels. The wording is in
`assets/text/ui/title.json`, and the editor's Fonts tab shows both glyph styles
as read-only Saturn fonts. The originals only contain the letters needed for
those three strings, so changing the wording would need a glyph generator and a
way to write the new images back, which doesn't exist yet.

### Options Menu

The options menu consists of two pages.

#### Page 01

This page consists of seven adjustable settings rows laid out vertically. The user moves between the settings rows with up/down inputs, and selects between the options for the highlighted row with left/right.

All text is displayed in fixed-width white FONT16.

Each row consists of left and right column groups.
The left column is the option text (バトルメッセージ, オートマッピング, パーティーパネル). This uses FONT16 and displays at most 9 glyphs with fixed width and advance (At most 8 on the first page).

The game reserves the equivalent of 9 glyphs for the left column, followed by one equivalent space, and then the right column.

The right column contains 2 or 3 separate option strings, each separated by one or more equivalent space characters.
Including space characters, options can display comfortably on screen up to at most 10 glyphs in equivalent width. However, no row exceeds 9 glyphs in used width, and no individual option uses more than 4 glyphs.

The cursor for the active row is indicated by blitting the row at full brightness. The cursors for each of the active options are indicated by blitting the option's text in yellow. The inactive rows appear 'grey' as their brightness is approximately halved.

The bottom two options rows have an additional text consumer.
When either of these rows are highlighted, a window appears in the bottom-right of the screen. This window renders four more rows of (at most) 5 glyphs each. These represent spell/item window orderings. Some of the lines displayed across these two windows include 回復, 宝石, 攻撃.

#### Page 02

This page consists of one more option row:
"コントロールパッド", "ノーマル　カスタム"

Also on-screen (but not immediately selectable) are a list of controller buttons, and their associated action.

At the bottom of the screen is help text, "スタート：設定変更".

Pressing START while the "カスタム" option is highlighted selects the first of the button binding texts (the カスタム text turns grey, and the binding text turns yellow; the コントロールパッド text remains white).

The user can then navigate up/down the list of texts, swap them with the A/B buttons, and press START again to leave the rebinding menu -- the help text changes to "スタート：設定終了"

These binding texts appear to use FONT12. Examples include ラージキャンセル, 決定, ヘルプ表示.

All 38 text records used on these two pages are in `assets/text/ui/options.json`
and map to `CFG_SET.BIN`. The serif `CONFIG` heading is an image. There's also
a table row in the file containing those letters, but its length is zero and
nothing draws it, so it's left alone as unused data rather than listed as
editable text.

The menu is split into five groups, with these Japanese limits:

| Group | Japanese limit | English limit |
| --- | --- | --- |
| Main labels | 9 cells | not measured |
| Setting values | 4 cells | not measured |
| Ordering popup rows | 5 cells | 80px |
| Controller actions | 8 cells | 128px |
| Footer (two states) | 9 cells | 144px |

The English limits come from the older finished English build. Any packed or
combined glyphs used to make words fit are generated from the full words in the
asset files, not maintained separately.

### Horoscope Vision

The fortune-telling sequence in `HOSI.BIN` shows eight FONT16 story messages
using the game's normal reveal-as-you-go text drawing. Each message can be up to
three rows of 20 fixed cells. Lines only wrap at spaces in the text, and each
message is limited to 64 words including line breaks and the terminator. The
messages describe the five locations and the magic circle, and live in
`assets/text/ui/horoscope.json`. The English build moves them into a 1,024-byte
pool and repoints the eight original pointers at the new rows. Line breaks,
addresses and reveal speed come out of the renderer; they aren't written by
hand.

### FMV Subtitles

The 33.4-second `START2` news report shows nine timed English subtitles over a
320x224 Cinepak movie. `assets/text/fmv/subtitles.json` holds the Japanese
reference, the English line breaks, and start/end times in hundredths of a
second from the start of the movie. The Saturn engine converts those times to
the movie's 12 fps frame count and centres one or two proportional FONT16 rows
at y=196 (one row) or y=180/196 (two rows). Font codes, pixel widths, x
positions, packed rows, movie index, framebuffer address and the drop shadow
are all worked out by the build, not written by hand. The CPK file itself is
not modified.

### End Credits

`END_ROLL.BIN` shows staff names in two places. The main scrolling credits have
28 FONT16 names in six-cell (96px) rows, and two staff test grids have another
12 names in seven-cell (112px) rows. All 40 people have their own entry in
`assets/text/credits/names.json`. The English renderer draws each full name in
proportional type and squeezes it horizontally only if it's too wide, rather
than cutting the name off or keeping a short version. Names can be at most 18
generated FONT16 glyphs.

### Save/Load Screens

SAVE and LOAD list three slots using FONT16. Their headings and top selectors
are images, not font text: LOAD, NEW GAME and SAVE are the original image
lettering, and the 104x24 INTERNAL/CARTRIDGE selector images come from the
graphics package. `assets/text/save_load.json` still has entries for those
labels so another platform or a future regenerated image has something to work
from, but the Saturn text package doesn't treat their pixels as text records.

An empty slot shows `未使用` / `EMPTY`. The original stores five visible cells
and the English version has an 80px limit. SAVE and LOAD each have an identical
copy, and both are checked against the one entry. The blank cells used for
centring, and the unused one-glyph left margin, are layout rather than text.

A filled slot has two rows. The first row is the player's name followed by a
location. In the original, the name is three given-name cells, one separator
cell and three family-name cells. The English renderer has an eight-cell
(128px) strip. The editable template is `{first_name} {last_name}`. The
renderer fills in the saved values and may drop the separator if either name is
empty. The Saturn compiler currently needs `{first_name}` before `{last_name}`,
because it reads the two save fields in that order. Supporting the reverse
order would need a second renderer path and hasn't been done.

That `save_load.json` entry only controls how the slot looks. The stored name
row `NAME_FW_FULL` is built separately from
`player_profile.json#full_name_storage.text`. Profile Entry and LOAD both use
that one order and separator, so changing the slot display can't change how the
player's name is stored.

A fixed special location has seven Japanese cells or 112 English pixels. A
generated dungeon label uses the same seven-cell field in the original, but
has a 144px English limit because it can have a floor added.

The second row has separate fields, each with its own limit:

- `Lv{level}`: four Japanese cells or 64 English pixels;
- `{day}／{month}` / `{day}/{month}`: five cells or 80 pixels;
- `{hour}：{minute}` / `{hour}:{minute}`: five cells or 80 pixels.

Day, month, hour, minute, level, location, floor number and player names are
filled in at runtime and aren't translatable. Alignment blanks and the
unpadded number layout are also just layout. The visible `Lv`, date slash, time
colon and `地下…階` floor wording are text: the identical FONT16 copies in SAVE
and LOAD are extracted and tied to the slot templates in `save_load.json` and
the floor template in `field/location_formats.json`. The same floor record
supplies the final `階` for above-ground floors. The above-ground form is a
separate editable template, even though the original has no separate record
for it.

On SAVE, choosing an occupied slot shows a one-row prompt (`記録の更新をしますか？`
or `ゲームを終了しますか？`) followed by the FONT16 choices `YES` and `NO`.
Prompts are 11 Japanese cells or 176 English pixels; choices are three cells or
48 pixels. `YES` and `NO` are already English but are still editable.

The SAVE/LOAD system messages each have their own limits rather than sharing
one message box:

| Message | Rows | Japanese | English |
| --- | --- | --- | --- |
| Small failures | 3 | 11 cells | 176px |
| Capacity messages | 2 | 17 cells | 272px |
| Start warning | 4 | 20 cells | 320px |
| Storage-management warning | 6 | 20 cells | 320px |
| Capacity number on its own | 1 | 3 cells | — |

The number `129` is only written once, in `capacity_number.text`. The
`{capacity_blocks}` placeholder copies that value into each message, and into
the LOAD record at `LOAD.BIN` `0xB1AE`.

English rows have to fit both a pixel width and a maximum number of encoded
glyphs:

| Field | Max glyphs |
| --- | --- |
| Special location | 16 |
| Dungeon location | 24 |
| Joined player name | 17 |
| Level | 4 |
| Date, time, empty slot | 5 |
| Prompts | 11 |
| Choices | 3 |
| Small-message row | 24 |
| Capacity-message row | 25 |
| Warning row | 63 |
| Capacity value | 3 |

PSP reuses the same location entries and general save wording, without copying
translations. Its game title, slot title, difficulty labels, cancel prompts,
fallback location and `psp_detail` template are PSP-only entries, because the
PSP save screen is laid out differently from the Saturn two-row slot.


### Event Window

Most of the game's dialogue displays through this window.
There is space for 20 FONT16 characters per row, and 3 rows.
The game rendered resolution can change. It's always the internal 352x224, but depending on the scene, black bars are used to reduce the effective resolution down to a width of 320px. At its minimum width, it renders with no margins, across this full 320px span.

The English renderer wraps within 300px on purpose, leaving a 10px margin on
each side of that 320px area. This matches the PSP version so translations and
previews behave the same on both. It doesn't try to copy the original
edge-to-edge wrapping.

The font blits smoothly in event dialogues, at ~1 frame per glyph. Pressing A mid-typewriter accelerates this to ~1 frame per row instead.

#### Event YES/NO

Sometimes, the event window displays a choice dialog above it and to the right of the screen. This appears in a green window, with options "YES", "NO" rendered in FONT8 fixed-width.
One line that triggers this prompt after blitting is "＞下におりますか？"

#### Event Options

Sometimes the event window displays options inside for the user to select. These are invariably rendered below a prompt line. The game can display between two and four options. For two-option splits, the game displays the options vertically, on lines 2/3. For 3/4 option splits, the game displays the options in a 2x2 grid.

The options section has an 8px left margin. It's not clear what the maximum length is from looking, but space wouldn't permit more than 9 glyphs.

One example of an options prompt is:
Prompt/Line 1: ＞何をしますか？
Line 2: [8px]NETアクセス[gap]行動を記録する
Line 3: [8px]部屋を出る

The active option is highlighted yellow.

#### Portrait-scene overlay (`MSGR.COF`)

Portrait scenes aren't a separate set of dialogue. The overlay loads
`MESFILE.EVE`, `EVFILE_0.EVE` through `EVFILE_2.EVE`, and `SHOPSMP.EVE`, so its
dialogue and choices use the same `event.dialogue` and `event.choice_option`
entries and wrapping as the Event Window above: three rows of 20 fixed cells in
Japanese, or a 300px row in English. The text build doesn't produce a separate
MSGR dialogue bank.

Portrait dialogue can insert all 319 demon names, all 43 race names, and the
three selectable character names Hajime, Rei and Kyouji, all from the shared
entries. All six CHARNAME rows are built so the table keeps its layout, but the
character-insert code doesn't accept indices 3–5. First name, last name,
codename, city and ward are runtime values in the existing EVENT templates. The
name inserts can put at most 20 glyphs into the dialogue stream. That's a limit
on the insert itself, not the visible width of a dialogue row; measuring and
wrapping still use the 300px, three-row event window. MSGR's own eight-byte
race table mirrors the same 43 race entries; in the older finished English
build only the UMA row differs.

Three error paths draw fixed ASCII tile glyphs directly into a one-row, 64-cell
VDP2 pattern-name buffer. `NAME TO ID ERR` and `LOAD ERR` start at cell 10;
`ERROR: MENU COUNT OVER` starts at cell 0. Their padded records in the
executable hold 15, 9 and 23 visible ASCII bytes respectively, plus a NUL. The
wording is editable in `assets/text/system/debug.json`, mapped to
`portrait_scene.debug_message`. The glyph images are built into MSGR rather
than coming from FONT8 or FONT16, so changing the wording is a text job, but
changing the letter shapes is a font/image job.

The rest of the readable ASCII in MSGR is resource names, file names, lookup
tables and internal stuff. Tracing the code didn't turn up any other on-screen
text.

### Profile Entry

The player fills out their profile by progressing through several inputs. For each input, they need to provide a valid input value, and confirm with END to advance.

The game renders each input screen with a top prompt section, consisting of a FONT16 question (i.e., "コードネームは？") and an input area (a series of underline characters to indicate available length/spacing, with a white bounding box to indicate the active input character target).

`ui/profile_entry.json` has every prompt, choice, occupation, tab label,
English grid row and default value. The stored full-name template is
`player_profile.json#full_name_storage.text`; Profile Entry and SAVE/LOAD both
build `NAME_FW_FULL` from its placeholder order and its one separator. Either
order works, as long as each field appears exactly once. The visible SAVE/LOAD
slot template is separate. The confirmation screen draws first and last names
at their own x positions, so the much wider gap there is layout and doesn't
affect the stored format. Underline slots, cursor boxes, highlight colours and
centring blanks are layout, not text.

The sequence is as follows:
1. Full Name: ___ ___ - 3 glyphs for last/first names. This is not ideal in English. The patch currently splits this into two separate screens.
2. Codename: ________ - 8 glyphs.
3. Place of residence: ___市___区 - 3 glyphs for city/ward. This is also not ideal in English. The patch currently splits this into two separate screens as well. These fields are pre-filled with 平崎 and 朝日.
4. Occupation: N/A

#### Full Name + Place of Residence Input

The player can switch between three pages for the text input. 漢字, ひらがな, and カタカナ. The actively-highlighted page has yellow text instead of white. The position of the grid cursor is indicated by a yellow bounding box. This bounding box borders either the current glyph's cell, or the page's rectangle, depending on where it's positioned.

Each page consists of a navigable input grid. Ordinary grid cells are drawn
from `KANJI.FON`; the action cells are special combined images in the font.
Cells have different colourations:

- Blue characters: Used to indicate the start of a section on the kanji page (i.e., あ, い, う, え, お, か, き, etc.). If selected, is treated the same as a hiragana glyph input.

- White characters: Used to indicate ordinary glyphs.

- Green characters: Used to indicate actions. I.e., the left and right arrows move the active input cursor left/right. The "END" symbol confirms the current input and advances to the next screen if accepted.

- Empty cells: These are treated as space characters if selected.

The kanji page consists of a full-window grid, 8 rows tall, 19 rows wide, with the ability to scroll down. To assist in navigation, pressing the L/R buttons moves the cursor between the blue section characters, and scrolls the window to place the highlighted blue section at the top, if there are enough rows below it to allow this.

The hiragana and katakana pages consist of three small grids distributed evenly and centered inside the window.
Each grid is 6 rows, 5 columns. The first and second grids are the standard kana and small vowels/ya/yu/yo/tsu/katakana-vu. The third grid consists of dakuten/handakuten variants, and the dash and interpunct. It also has the left/right arrows and END command button.

The English version replaces those pages with three tabs: `UPPER`, `lower` and
`SYMBOL`. It still draws eight navigable rows of 19 cells, with up to 13
characters per row starting at column three. The six row strings are editable.
Every emptied cell can still be selected as a blank. The trailing space in the
second SYMBOL row is the only blank that's actually part of the row text. The
grid uses the `ark_latin` glyph set in `KANJI.FON`, which replaces the needed
cells with 16px Ark glyphs. NAME.BIN uses the generated ink bounds to centre
each glyph in its cell at runtime. The typed eight-cell input row is centred the
same way, using the existing FONT16 metrics.

The original stores `漢字`, `ひらがな` and `カタカナ` twice: once in the row of
tabs, and once in each selected-tab template. Each identical pair has one entry
with two source locations. Katakana is still listed even though the English
version doesn't use it. The city `市` and ward `区` suffix glyphs are also
editable records, although the split English screens don't use that address
layout.

The left/right arrows and `終了` are text in meaning, but in the original
they're combined font images, not ordinary grid strings. `grid_end.text`
records the editable `END` meaning and the two original `FONT16` cells. The
older finished English code draws the original action through display code
`0x01F7`, so showing a different label needs engine and font changes, not just
an asset edit. The English version doesn't currently draw the left/right
arrows.

#### Codename Input

The codename input is almost identical to the above, however the first page has been replaced. Instead of Kanji, the player can enter "英字数字" -- a 4 row, 14 column input consisting of English capital letters (no lowercase), numbers, the interpunct, forward slash, full stop, exclamation and question marks.

#### Occupation Input

The occupation input has the same page buttons as its previous screen (location input), but they're greyed out. Instead, the game provides a 3 row, 2 column loose grid of occupations to choose.
Each occupation is 3 glyphs wide, with a matching sized yellow bounding box. They are spaced apart with 1 empty non-selectable row, and ~5 empty non-selectable columns.

Our patch currently replaces the yellow box with the yellow highlight cursor to avoid awkwardly resizing to different text widths.

#### Confirmation

After entering this information, the game renders four blocks summarising the user input, and one more down the bottom, prompting for confirmation.
Answering NO restarts the process.

The blocks are:
あなたの氏名は？　　＿＿＿　＿＿＿
コードネームは？　　＿＿＿＿＿＿＿＿
あなたの住所は？　　＿＿＿市＿＿＿区
あなたの職業は？　　＿＿＿

これで　いいですか？　　YES　NO

The older finished English build had one bug here: it left out the `0x8000`
terminator after its 19-cell template, so the game's drawing code ran on into
the `漢字` data that follows. The current `profile_entry.ui` build adds the
terminator. This is a fix to the output, not text kept in an asset.

### 2D Map

All the known on-screen text in `MAP2D.BIN` is ordinary FONT16 data; none of it
is baked into images. The inventory keeps all the runtime pieces listed, even
the ones the older English renderer doesn't draw, rather than treating them as
deleted:

| Text | Offset(s) | Notes |
| --- | --- | --- |
| `朝日` | `0x1E684` | Default value, shared with Profile Entry |
| `平崎` | `0x1E6C0` | Default value, shared with Profile Entry |
| `区` | `0x1E688`, `0x1E6DE` | |
| `市` | `0x1E6C4`, `0x1E6E2` | |
| `全図` | `0x1E6CA` | |
| `雲` | `0x1E6D4` | Separately terminated; unresolved |

Extraction checks that each pair of suffix copies is byte-for-byte identical.
`雲` is still an editable but unresolved entry: nothing has been found that
points to it or selects it.

#### World Map

The world map has two text consumers. All use FONT16.

In the bottom-left is a grey rectangle with the original template
`{city}市全図`. The city name is centred in a four-cell space, and the whole
rectangle is six Japanese cells or 96 English pixels.
`ui/map_2d.json#world_city_label.text` holds the template, translated as
`{city}`. The older English code builds the city name in a narrower 64px space
and leaves out both suffixes. That doesn't shrink the 96px limit, and `市全図`
isn't left as hard-coded renderer text.

In the top-right are destination boxes that appear depending on context. Each
is four Japanese cells or 64 English pixels, centred horizontally. The dynamic
template `{ward}区` is translated as `{ward}`. Five fixed names reuse the
shared location list: Rinkai Park, Mt. Kasagi, Yarai Ward, Chuo Ward and
Hibarigaoka. Only Mount Kasagi needs a short map-only version: `Mount Kasagi`
is 69px, while `Mt. Kasagi` is 55px and fits. Names that are the same aren't
copied into a second map list.

#### Area Map

Inside each area, the bottom-left rectangle is eight Japanese cells or 128
English pixels. The original draws two separately centred four-cell pieces:
the `{city}市` city label, then the current `{area}` label. These are separate
templates. The older English code hides the city on this screen and shows only
the area. The asset still has the city placeholder, and the area is still the
full eight-cell rectangle.

While exploring the map, the player may traverse over a conversation point. This displays on the screen in a large pair of green boxes:
"＞誰かいる。話しかけますか？"
and vertically stacked, "YES", "NO".

The prompt and choices reuse the shared field-message entries. The prompt is a
14-cell (224px) FONT16 area; the older English text is 32 proportional glyphs,
171px wide, pre-drawn into those cells. Each choice is three cells (48px), with
at most three encoded glyphs. Their records are at `0x1E756`, `0x1E774` and
`0x1E77C` respectively.

### 3D Map

#### Location Window

In the top-right of the 3D map is the compass and location text.
The location text is displayed as a row of 4 FONT16 glyphs. Examples include 氷川神社, カーサ乾, 図書館. These are left-justified.
Below the location text is another 4 glyph strip for floor information. The format is an optional 地下 prefix, followed by an up-to 2 digit number, followed by 階. These are right-justified. The game never combines 'underground' with a floor that requires more than 1 digit.

#### Elevator floors

Elevator destinations use the same four-cell FONT16 floor strip, but have their
own entries. The English renderer draws them proportionally in the same 64px
buffer. `field/elevator.json` has the optional basement symbol, the floor
symbol and the full template; the current English template is
`{lower_symbol}{floor_number}{floor_symbol}`, giving `4F` or `B1F`.

In the top-left of the 3D map is the moon phase and currency information. The game uses FONT8 to render two rows of 4 letters for the moon phase. These can include English texts, "NEW", "FULL" and "MOON". The first two being on the top row, the latter being on the bottom.

#### Analyze Grid

All of the grid text is rendered in FONT8.

Pressing R (default) in the 3D Map view opens the Demon Analyze table. The table includes columns for "RACE", "NAME', "LV", "HP", "MP', "ATK", "DEF". Highlighting a column header sorts the table by that metric. The player can scroll down the table to view the demons they've encountered thus far.

On the 352px-wide screen, the headers start at x=28, 80, 156, 202, 236, 264 and
300, with one-row limits of 52, 76, 46, 34, 28, 36 and 52 pixels. The headers
sit on y=20. These English headings use the original Japanese FONT8 English
letters rather than the new mixed-case font. Each heading entry sets
`font8_alphabet: original` for this; leaving it out means the new font.

The table shows 16 rows from y=32 to y=212, 12 pixels apart. Race starts at
x=28, name at x=80, and the five numbers at x=164, 208, 244, 280 and 316. In
Japanese each row is a five-kana race and an eight-glyph name. In English the
race gets 52px and the name gets 84px before the first number. The older
English renderer doesn't clip long names, so names that are too long are
flagged by validation rather than cut off. With the current FONT8 metrics,
`Yamata-no-Orochi` is 93px and `Yomotsu-Shikome` 88px, so both are wider than
the 84px gap. `Take-Mikazuchi` and `Jack-o'-Lantern` are wider than the 76px
header column but still fit before the first number.

The 43 race spellings in the grid are katakana versions of the same race
entries used by the FONT16 detail view. They don't need a second translation
list.

Selecting a demon from the list opens its status screen.

#### Auto Map

Pressing L (default) in the 3D Map view opens the Auto Map.
Pressing A on the Auto Map opens a list of map marker entries.
The game shows 9 entries on the page, but scrolling reveals a total of up to 16 that can be saved.
Each list item consists of an 8 glyph FONT16 string, with a leading space for " NO DATA" by default.
Selecting a list item, then selecting a tile on the map assigns a marker to that tile. The list then shows that marker, followed by a 7 character location string. This is identical to the existing location string implementation in the Location Window, but to guarantee 7 characters at most, 地下 is represented as "B" instead.
I.e., "{icon}図書館　B1F"

Selecting a marker on the map displays a small window in the top-left. 3 rows, 6 FONT16 characters each. Right-aligned.
"マーカー削除"
"   YES"
"    NO"

The English popup keeps those three rows, with a 64px limit per row.
`(No data)`, `Delete?`, `Yes` and `No` are separate editable entries, not
hard-coded in the renderer. The MAZE interaction choices keep their original
three-cell size, measured as 48px in English.

#### Auto Recovery

Pressing Y (default) on the 3D Map displays "オートリカバーON" in the green toast window briefly.

#### Field Messages

Along with having the existing "Someone is here, will you talk?" message prompts that appear on the 2D Map, there are other field messages that can appear, i.e., when discovering a treasure chest.

{item}を手に入れた
{item}を見つけた
{yen_symbol}{currency_amount}を手に入れた
{mag_symbol}{currency_amount}を手に入れた
etc.

The yen and magnetite messages each start with their own symbol glyph before
the amount. Both money messages and the "obtained item" message share the same
stored `を手に入れた` suffix, but they're separate templates for editing. The
code picks the message and fills in the item or amount; the symbol and
surrounding words come from the asset.

Some may also appear briefly before an encounter transition, warning of an ambush or advantage.


### Combat

#### Party Panels

The party panels are a set of six rectangular panels located near the bottom of the screen.
Each panel consists of two rows. The top is a FONT8 consumer, 8 glyphs (though space for ~12); it's the demon/player/unit's name (left-justified) or "EMPTY" (centered) when no unit is present.
The bottom row uses FONT6 and consists of the HP/MP labels and dynamic values. It may not require a special renderer hook, but its visible labels/templates should still have editable entries.

COMBAT builds the placeholder top rows in code. `EMPTY` is a five-cell row, and
the related stock-party list uses the eight-cell `IN PARTY` row. Both are
entries in `assets/text/battle/party_panel.json`, set to
`font8_alphabet: original`, which uses the original FONT8 `stock_latin` glyph
set. Padding and centring are left to the renderer.

The MAZE stock-party list is also done. Its compact FONT8 renderer uses the same
319-demon, six-character name compiler as the COMP menu, but has its own MAZE
code caves and three call-site pointers. Long names use the packed-name path.
Edits can move the drawing code anywhere in its 2,048-byte space, and all three
calls are relinked to wherever it ends up.

#### Analyze

Pressing R in combat highlights a demon, and displays the demon analyze window on the right of the screen.

This window displays the following:
Line 1 (FONT8) "{demon race}:" (with the colon)
Line 2 (FONT8) "{demon name}"
Line 3 (FONT8) "H####/####"
Line 4 (FONT8) "M####/####"
Line 5 is blank, FONT8 height
Line 6 is "B.ST" for most demons. Not honestly sure what this means.
Then there's a small gap
Line 7 (FONT12) is the demon's affinity; 5 glyphs

If the player hasn't obtained the demon's analyze data, instead of showing anything beyond the top two lines, the game will show "NO DATA" centered in the area below them (around line 5).

Pressing R again pages the window. Lines 1 and 2 remain the same, but 3 onwards are replaced with a list of FONT8 strings for each of the demon's known skills (up to 7).

#### Help

Pressing X in combat opens a help window at the top of the screen. This displays 2 rows, 20 columns of FONT16 characters, and describes the currently-highlighted menu option.

This can be the command (i.e., FIGHT - "悪魔との戦闘") or more specific, like an item description.

#### Command List

These are displayed in English already, using the game's FONT8 text.

These command labels use the original Japanese FONT8 English letters on
purpose. The new font has to keep that alphabet as a separate glyph set;
ordinary mixed-case FONT8 text uses the new English letters instead.

Options include "FIGHT, TALK, ESCAPE, AUTO, SWORD, GUN, COMP, ITEM, MOVE, GUARD, GO, OFFENSE, DEFENSE, RETURN, PRESET, REPEAT".

The battle action table exists as three identical copies, in COMBAT, MAZE and
NORMCOM. The actual spellings there are `OFFENCE` and `DEFENCE`; these are kept
as screen-specific variants of the shared `OFFENSE` and `DEFENSE` terms. The
four item/skill actions and the rest of the table are listed. A full search of
COMBAT's data and the code that calls into it found no text records for the
main commands `FIGHT`, `TALK`, `ESCAPE`, `AUTO`, `PRESET` and `REPEAT`: their
English lettering is pre-drawn graphics/font data, not part of this table.
They still have entries for their meaning, but changing how they look means
editing those graphics, not adding a made-up text binding.

#### Item/Skill Windows

These windows consist of 9 rows, 2 columns, all FONT8 consumers.
Each item/skill is represented as a coloured icon, followed by space for 8 glyphs, and 2 numbers (quantity/cost).
The skill window also includes non-skill options, like ATTACK, MAGIC, EXTRA, GUARD, without leading icons.

#### Conversation

Talking to demons uses a very similar window to the standard event window. However, some additional actions can occur here.

The Japanese dialogue area is three rows of 20 FONT16 cells. The English
renderer has three rows, 300px wide. It's a separate
`battle.negotiation_dialogue` entry even though its size matches the event
window.

Three- and four-way replies use a two-by-two FONT16 grid, with each column
150px wide; text past 150px is clipped. The build reads which messages are
choices from each bank's script and fails on any choice over 150px. The editor
also warns past 142px, the longest clean line visible in the older English
build (`Because it will be convenie`).

Two-way replies can be longer: some Japanese options are 15 cells (240px), so
the build allows 240px for them. Their real layout hasn't been measured.

Demons can request items, which are highlighted in blue text.

Demons can also ask for the player to provision an item, money, or magnetite. The former opens an item window similar to the one specified directly above. The latter two provide an inline money selector, where the player moves left and right to select the highlighted digit, and up/down to decrement/increment it. Pressing A confirms the amount to provision.

#### Console Window

Taking actions in battle displays information in the top-left console window. A lot of this text is already in English, fixed-width, using the FONT8x12 resource.

The window provides enough space for 2-3 rows (depending on the action being performed in-battle), 16 glyphs wide each.
The game likes to end the bottom row with a special "blinking" glyph, similar to a command-line interface.

Examples include:
"SWORD
DAMAGE_10[]", [] being the blinking glyph.
"OFFENSE_EXTRA (an example of two terms being concatenated)
PICKING
Damage_6[]"

#### Demon Chat Window

When a demon takes action in battle, or when attempting to escape from demons, a "chat" window is displayed in the top-right.

This window uses FONT16 text, and has space for 2 rows, 11 glyphs each.
Example consumers include:
"ア～、ダル～。
チョット、マッテクレ。".

When escaping, the window shows two separate one-row lines instead: the
demon's reaction ("逃げるも、また策・・・") and then whether the escape worked
("逃さぬも、また策なり。"). The game puts the second line on the row below the
first, so a reaction that wraps is overwritten and a reply that wraps falls
outside the window. Each escape line must fit on one row.

#### Result Window

On defeating the enemies, the game displays a result window, all using FONT8 consumers.

Row 1: [macca symbol] [amount of macca]
Row 2: [player name, 8 glyphs] [rei's name, 8 glyphs]
Row 3: "EXP" [exp earned]
Row 4: "ITEM"
Rows 5-7(?): Items obtained from the battle, if any; else empty
Bottom row: "ませき" [number of lifestones obtained] "ほうぎょく" [number of beads obtained]

The English battle code covers party names, the Analyze race heading, name and
affinity, item and skill lists, the help strip, Demon Chat, result names and
labels, and the whole fixed-width console bank. Measured English limits:

| Text | Limit |
| --- | --- |
| Item, skill and party names | 80px |
| Analyze names and affinities | 112px |
| Help | 300px, two rows |
| Demon Chat | 176px, two rows |
| Escape chat | 176px, one row |
| Result names | 88px |

The Analyze race heading is a fixed eight-cell FONT8 record rather than a
measured proportional slot.

### Ritual Console

The NORMCOM ritual sequence has its own `BUTU_SRF.MDT` FONT16 pointer table. It
isn't the same thing as Demon Chat, even though both look like console
overlays. All 144 rows are listed; 64 visible rows map to separate entries in
`ritual/console.json`, and the other 80 are blank and kept as-is. The English
renderer is 176px wide. The number of rows hasn't been measured yet and is left
as unknown rather than assuming Demon Chat's two rows.


### COMP Menu

The COMP menu consists of a top 2-row FONT16 Help strip, a block of the 6 active party panels, and another block of the 12 stock demons.

Its top-level FONT8 commands are `COMP`, `MAGIC`, `ITEM`, `EQUIP`, and `STATUS`.
They use the original FONT8 English letters, and can be edited separately from
the same words in battle or facilities.

The English COMP code handles the two-row, 300px help strip, the 80px active
and stock demon-name panels, and the 80px item/magic name grid. Each of the 319
demon names is one entry: 210 fit the original eight-byte records, and 109 go
into an overflow pool at runtime. The NORMCOM ritual console is built on top of
this but is a separate thing. The equipment and detailed-status screens are
built as separate stages on top, rather than being folded into the COMP code.

There's also a window in the top-left with the submenus listed. This window serves as an effective margin for the Help window when it's visible.

#### Party Panel

This is identical to the combat version, albeit with stock party members showing "IN PARTY" instead of "EMPTY" when they're in the active party.

#### Help Strip

Extending from the Combat implementation, this also includes a section on the right for previewing how much it costs to summon a demon, when the player has a demon highlighted.

It's 4 rows of FONT8
"INV."
" {Macca symbol} {current macca}"
"COST"
" {Macca symbol} {summon cost}"

#### Magic/Item Windows

Similar to the Combat implementation, but without the non-icon options (ATTACK, EXTRA). It's also 10 rows, 3 columns.

#### Equipment Window

In the top right of the window are the options "おすすめ" and "はずす". Each has both yellow text and a yellow bounding box cursor when highlighted.
Moving the cursor below these, the player has a list of 7 inventory slots. Each has an icon, which the bounding box outlines when the cursor is on it, and the equipped item name (or "________" when empty), highlighted in yellow for the cursor.
When an option is highlighted, the player can see relevant items listed on the far right of the screen in an item list.
This item list is a single-column version of the other item windows, with 10 rows of space.
The game lists the recommended gear that will be equipped when おすすめ is highlighted, and the available alternative pieces of gear in the player's inventory when an individual slot is highlighted. The player can press A to move over to this list and select a piece of gear to swap/equip.

Between the left equipment list, and the right equipment items window, in the center is the stat table.
This shows narrow FONT8x12 (I believe?) stat glyphs, and beside each one, the corresponding stat number value.
We have 力　知　魔　耐　速　運 stacked vertically, with space beside them for 2 FONT8 digits.
Then, another column of 剣攻撃 ＿命中 (the _ represents an empty space here for alignment, not a literal underscore)　銃攻撃　＿命中　防衛　回避　魔法威力　＿＿防衛.

`equipment.ui` treats this screen and the shop's equipment panel as two uses of
the same text. Auto/Unequip are 40px FONT8 labels; base and derived stat
headings get 23px and 48px; item names get 80px. The shop comparison also has a
72px character-name slot and the existing 16px `Inv.` label. Cursor boxes and
numbers are handled by the engine; every visible word comes from `assets/text`.

#### Status Screen

##### Human Status

The human status screen has the player/human's codename/name in the top-left in FONT16.
It uses the same eight-cell, 128x16 name image as the demon detail view. Text
starts at x=2, leaving 126px for English.

Below is a 5-line list in FONT8 of :
LV ##
HP ####/####
MP ####/####
EXP #####
NEXT #####

In NORMCOM these are drawn as separate one-row FONT8 pieces, not as free text.
`LV` and `CP` put their value at x=40; `EXP` and `NEXT` at x=80. `HP` and `MP`
put the current value at x=40, the shared one-cell separator at x=48, and the
maximum at x=80. The `LV`, `HP`, `MP`, `EXP` and `CP` labels can be three
glyphs; `NEXT` can be seven. These start positions don't tell us the maximum
number of digits or where the numbers end, so the full row widths aren't
measured.

In the middle is a hexagon graph of the player's stat distribution. At the six points of the hexagon are the six in-game stats, 力　知　魔　耐　速　運.

In the top-right  is the player's AUTO setting (i.e., AUTO SWORD), and the party alignment (i.e., "P.A. LAW"). FONT8

This applies to both the NORMCOM version used by the field/COMP menu and the
duplicate EVENT version used by the Gouma-Den, healer, gym and shops. Both rows
use FONT8.

- The AUTO value starts at x=40 and can safely extend to x=110.
- Generic AUTO commands still use fixed cells. Item and magic choices look up
  the full item/spell name for the current human or demon and draw it
  proportionally in that 70px space, which removes the original
  eight-character limit.
- Names that fit stay on one line (shifted down). Wider names wrap at a space
  or between glyphs, across y=0 and y=8.
- The AUTO and P.A. labels and values all move down four pixels together, so
  nothing gets clipped off the top.
- `AUTO` uses four of the five cells before the value; `P.A.` is exactly four
  cells, with the fifth left as space. The space in each template marks that
  split; it isn't a separately positioned glyph.
- The party alignment value uses the original fixed-cell ASCII/FONT8 glyphs,
  but reads the `law.party_label`, `neutral.party_label` and
  `chaos.party_label` entries from new records with no length limit. The 70px
  slot fits up to eight original cells. The old fixed records are kept unused,
  as markers the code still checks against.

The AUTO item selection grid uses the same full-name proportional drawing as
the magic grid. When opened, it also puts the original icon set back after the
detailed-status screen has replaced it in the shared cache.

On the right are the player's derived stats. FONT 12 with the values as FONT8 beside, aligned to the bottom of the text.
剣攻撃力
剣命中力

銃攻撃力
銃命中力
防衛力
回避力
魔法威力
魔法防衛

##### Demon Status

The demon status screen replaces the human name with two text consumers. The kanji representation of the demon's race, and the demon's name, both separate FONT16 strings.

The demon name is a 128x16 image starting at x=2, leaving 126px for English;
the race is a 48x16 image starting at x=2, leaving 46px. In Japanese these are
eight and three FONT16 glyphs. The current `Avatar` and `Element` translations
are 47px and 50px in the older FONT16 renderer, so both are too wide for the
46px slot. That's left as a known issue to review rather than being cut off.

The top-left stat block is a 96x60 image with LV, HP, MP and CP (summon cost).
The four FONT8 rows start at y=0, 12, 24 and 36, and each value starts at x=40.
These labels reuse the shared status templates rather than having separate
Analyze copies.

The bottom left now shows a skill table.
It's a 96x80 FONT8 image with six visible rows from y=8 to y=68, 12 pixels
apart. Skill names start at x=0 and get 80px; the cost number sits at x=80 and
its one-letter unit at x=88. The templates are `{cost}M` for MP costs and
`{cost}H` for HP costs. The original shows M for ability IDs up to 159 and H
for anything above. Items don't appear here.

The top right now shows just the AUTO command (i.e., "AUTO GO").
Instead of derived stats, the right shows three new parameters:
忠誠度 (FONT12)  # (FONT8)
CTRL   1ST (or similar; both FONT8)
TYPE (FONT8)  [personality string (FONT12 Kanji)]

The English Loyalty and personality images each have 38px. Loyalty's FONT8
number starts at x=72; its maximum number of digits and where it ends aren't
known yet. `TYPE` has its own four-cell FONT8 label and the personality is a
separate image, so neither translation can use the space between them. `CTRL`
is a ten-cell FONT8 row: the label starts at x=0 and can use five cells, and
the three-cell rank starts at x=56. The cells in between are layout. Each
L/N/C/L/D alignment axis label is one FONT8 cell. Law and Light are separate
entries even though both are `L` by default; the code keeps the original shared
pointer while they match, and only adds a separate Light pointer if they're
edited to differ.

The bottom right shows a 2D alignment axis, LNC and LND.

Pressing right pages to replace the right-hand components.
On this page we have the derived stats in the top-right:
攻撃力
命中力
防衛力
回避力
魔法威力
魔法防衛

And below these, a 2 row, 8 glyph window for affinity text.
The affinity image is 128x32. Japanese uses two rows of eight FONT12 glyphs;
English uses FONT8 and can go up to 127px while keeping the full 128px area.


### Level Up

#### Main Panel

The level-up panel is its own thing in `LEVEL_UP.BIN`. `LEVEL UP` is one fixed
FONT8 row of eight cells. The character name image is 128x16: Japanese draws up
to eight FONT16 cells, while the older English version uses a 96px safe limit
for the five fixed names. The player's codename uses the same image but is
handled separately and gets the full 128px row; the fixed-name limit doesn't
apply to what the player types.

The stats reuse the six base-stat labels, eight derived-stat labels, and the
generic Attack and Accuracy labels from the status screen:

| Labels | Japanese | English |
| --- | --- | --- |
| Base stats | one 16x16 cell | 12px (compressed) |
| Derived stats | four FONT12 cells | 46px |
| Generic Attack/Accuracy | three FONT12 cells | 46px |

These are drawn separately by LEVEL_UP, even though they share entries with the
status screen.

`LV`, `HP`, `MP`, `EXP` and `NEXT` are fixed FONT8 labels with live numbers
beside them. Not all of their number widths are known, and they shouldn't be
guessed from the general nine-digit number drawing code. The remaining-points
display has a right-aligned number, a four-cell decoration and a four-cell
`LEFT` label. The whole thing is at most 17 FONT8 cells: nine for the number,
four for the decoration, four for the label. The four spaces stored before
`LEFT` make room for the decoration and aren't part of the text.

Two special number rows are still text, even though the original builds them in
code. At max level, the seven-cell NEXT value becomes `-------`. A character
with no MP shows `---/---` across the current/max MP layout. The renderer adds
one fixed alignment cell after the slash, giving eight cells on screen, but
that gap isn't part of the translation. Both use the original FONT8 interpunct
cell (via its `-` alias) and the original slash cell.

The confirmation step draws an `OK` label in a two-cell FONT8 slot next to a
button glyph, plus `YES` and `NO` stacked in three-cell FONT8 slots. The space
stored before `NO` is for centring, not part of the word.

#### Learned Magic Window

Learning an ability uses a separate image that only appears when needed, not
another row of the main panel. In normal play this happens for Rei, not for
demons. Surface 19 is 144x32 with two FONT16 rows. The heading is drawn at
x=2, y=0 and takes five Japanese glyph cells; the English limit is a cautious
128px, and `Learned Magic` is currently 74px. The learned ability name is drawn
at x=2, y=16 and allows eight Japanese glyph cells or 128 English pixels. The
heading and the ability name are separate pieces of text.


### Fusion
Most fusion consumers are FONT12.

#### Demon Compendium

The demon compendium doesn't exist in the original Saturn release. However, it was included in a non-gameplay form with a bonus pack-in disc "Akuma Zensho".
This disc includes demon lore entries that would later appear in-game in the PSP version. For that reason, these should be translated and paired with their respective parent demons.

> The translated *Akuma Zensho* build is currently broken in game. The details
> below describe how it's meant to work.

The bonus disc's executable draws each demon profile from a fixed 0x1dc-byte
block at the end of its record:

| Field | Size |
| --- | --- |
| Origin | one 144px row |
| Summary | four 224px rows |
| Full detail | twelve 224px rows |
| Demon and ability names | one 128px row |
| Race labels | one 48px row |

English uses the narrow FONT8 glyphs embedded in the compendium code; the
original fixed-cell drawing is still used for untranslated data and non-text
graphics. The status view's six two-letter base-stat labels use a dedicated
single-glyph adapter; its six derived-stat rows use the same compact row codec
as the rest of the compendium text.

The same executable has 48 race description layouts, each a 224px heading plus
four 224px rows of text. Three of them just say `NO DATA` with no text below.
There are eleven fusion-condition help entries, each two 320px rows. All of
these, including Vengeful Spirit and Fiend, are translated and built by
`compendium.text`. Two raw placeholder race rows are still unresolved because
nobody has worked out what they're for.

#### Top Menus
We have nested windows.
２身合体
３身合体
合体記号の見方
合体検索
    合体法則
        通常の２身合体表
        通常の３身合体表
        表の見方 -- displays full screen help
        前へもどる
    合体可能な悪魔
        一覧表示 -- displays the search list
        並び方の変更 -- displays the ordering settings
        前へもどる
    前へもどる
ステータスをみる
前へもどる

#### Fusion Help Text

This strip is a FONT12 consumer at the top of the screen, one line tall. It displays Victor's dialogue on these top-level screens.

#### Fusion Confirmation

The prompt and status messages are one 300px FONT16 line inside a 320px area,
with 10px margins on each side. YES and NO keep their own 48px strips on the
next two rows. Each label is right-aligned in its strip, and the strips are
placed so they line up on the right edge.

#### Fusion Chart

The fusion chart displays a header text (i.e., 通常の２身合体表).
It also displays a scrollable 2D table, with green race headers along the first row and column in green. These are sticky headers.
Within the table content, the cells are grey if not in the active pair of axes, otherwise yellow. The cells alternate slightly in their brightness for legibility.
Every cell is either a 2-kanji race text, or a wide "X" character for invalid combinations.
For the 3D fusion table, the top-right shows a third selectable race name.

#### Fusion Table

The fusion table lists all demons in the player's stock in a tabular view.
We have a 2-kanji column for race, an 8 char column for name, and an up-to-12 column set of combination status symbols.

#### Status List

A list of all the human and demon members of the party. FONT12 with space for 8 chars.
Opens the status view on selection.

### Shop

Shops have four top-level options, BUY SELL EQUIP EXIT.

These FONT8 labels, and the bar and healer labels below, use the original
FONT8 English letters. The game stores `REVIVE` and `STATUS` as combined FONT8
cells, but here they're editable as normal words, with a mapping to the
original cells.

#### BUY/SELL pages

Each page shows 8 'item' blocks, and can be vertically scrolled.
The player can press left/right to adjust the quantity to buy/sell, and C to confirm.

##### Item Block

This consists of two rows of FONT8 text.
Top row is the coloured icon representing the item's type, followed by the item name over 8 kana, and finally 2 digits for quantity.
Bottom row is the yen symbol, and the unit cost (right-aligned, space for 6 digits)

#### Info Windows

Top-right on all shop views, this consists of 3 stacked small windows in FONT8.

First, a window with 3 rows:
{yen symbol} {held money}
TOTAL
{yen symbol} {current purchase total}

Next, the amount of the selected item currently held:
"Inv." (this seems to be its own glyph)  ###/###

Finally, the player and heroine names. These are highlighted yellow when the item in question is an upgrade:
[equip icon glyph, if the item is equipped][codename]
[equip icon glyph, if the item is equipped][rei's name]


#### Help Window

The help window is at the top. For the parent options, it displays one line of FONT16 text, limited to 20 glyphs.
When the cursor is over items, it extends upward to hold space for two lines.

#### Equipment Window

The equipment window is identical here to the COMP iteration.
There is a list of the human party members to choose the EQUIP target.

### Bar

Top-level options are ORDER TALK STATUS EXIT.
There are similar info windows to the Shop screen, displaying current money, and the human party member names.

#### Drink List
ORDER shows a list of 2-row drink blocks, 7 in total.
Each drink is represented as two rows.
Top is 8 chars of FONT8 kana, bottom is yen symbol, with space for 7 digits (right-aligned).
In English, the drink name is one FONT8 line with a 64px limit.

#### Patron List
TALK shows a list of 1-row patron names, each FONT8 with space for 8 kana.
In English, patron names also have a 64px limit.

#### Status List
Like the fusion status list window, but FONT8.
The bar's party/info names and status names share the older English build's
104px FONT8 name pool.

#### Help Window

The help window is essentially identical to the Shop Help window.

### Healer

Top-level options are ALL HEAL CURE CURSE REVIVE STATUS EXIT.
The top-right info window is the same money/TOTAL/total three-row window from the shop screen.

#### Heal All List
Each target is represented as two rows FONT8.
Top row: An interpunct, followed by space for 8 glyphs.
Bottom row: yen, followed by space for a cost of 6 glyphs.
The list is prefaced with "メンバーすべて" as one of the targets.
The list shows up to 8 targets, and can be scrolled.
In English, the all-members row has its own drawing code and a 144px FONT8
limit. Ordinary character and demon rows use the shared 104px facility name
pool instead.

#### Heal One List
Similar to the Heal All list, however the window has been widened.
Each unit shows, after the top row name, HP ####/####, and after the bottom row cost, MP ####/####.

#### Status List

Like the fusion status list window, but FONT8.
Character and demon names use the same 104px facility name limit.

### MAG Exchange

Top-level options are displayed in an event text window and may not require a special renderer hook. They should still have editable entries.

When converting mag, two additional FONT8 help windows appear.
{yen symbol} {current yen}
{mag symbol} {current mag}

and
RATE
{mag symbol}10={yen symbol}{current rate} (or vice-versa, depending on the exchange).

## Developer Diagnostic Overlays

SNDTEST shows a fixed-cell ASCII title, two request-number prefixes and an exit
message. TEST3D shows a title, five parameter labels and a launch prompt, drawn
the same way. These eleven entries are for developers, but they do appear on
screen, so they're ordinary editable text in `assets/text/diagnostics/`. The
original records must be ASCII, end in a NUL, and fit each field's exact size.
Trailing spaces in the parameter prefixes are there for spacing or alignment,
so don't strip them.
