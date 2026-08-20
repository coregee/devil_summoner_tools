# Devil Summoner: Text Consumer Specs

This document enumerates the observed behaviour of all text consumers in the game, and is intended as a reference for aligning the AI's existing code with what a user will intuitively understand from playing the game.

The purpose of this document is to help in auditing the existing text surfaces for accuracy, aligning where mis-implementations may have occurred, relabelling where mis-identifications may have occurred, and hooking where surfaces may have been otherwise missed.

Hopefully, by referencing this, we'll be able to rewrite the Saturn codebase to be much more intuitive and maintainable going forward.

These text surfaces are externally-viewed only. The game may duplicate surfaces that appear similar/identical from the user's point of view for architectural/efficiency reasons.

Every player-visible string, label, fragment, and complete dynamic template must
be represented by an editable authored asset under `assets/text`, including
stock-English text and text rendered from code or images. Runtime code may
select an asset, substitute typed values, format numbers, measure it, and render
it; runtime code must not own player-visible wording or punctuation. References
below to text not needing a hook mean only that no special renderer change is
currently required.

## Saturn Consumers

### Title Screen

The game has the logos for "真・女神転生" and "デビルサマナー" scale down onto the title screen.

There is also the logo "悪魔召喚師" (literally Devil Summoner, in Japanese). The current English policy may leave this logo untranslated, but its text and visual binding must still be surfaced for potential editing.

The title screen itself is another image, displayed after a white flash transition. These three logos are pre-baked into it.

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

All 38 live text records for these two pages are represented by
`assets/text/ui/options.json` and bind explicitly to `CFG_SET.BIN`. The visible
serif `CONFIG` heading is graphical. A stock table row also contains those
codes, but its paired length is zero and every known draw path skips it, so it
is preserved as dormant binary data rather than misrepresented as editable
runtime text. The menu is split into five text surfaces: primary labels,
setting values, the four-row ordering popup, controller actions, and the two
footer states. Japanese labels retain their nine-cell limit, values four cells,
popup rows five cells, controller actions eight cells, and footers nine cells.
The mature English renderer proves 80-pixel popup rows, 128-pixel controller
actions, and 144-pixel footers; translated primary-label and value limits remain
unmeasured. Any packed or compound glyphs used to meet these limits are
generated from the complete authored words and are not separately maintained
text.

### Save/Load Screens

SAVE and LOAD list three slots using FONT16. Their headings and top selectors are
image lettering, not FONT text: LOAD, NEW GAME, and SAVE remain stock image
glyphs, while the 104-by-24 INTERNAL/CARTRIDGE selector variants are owned by
the visual package. `assets/text/save_load.json` still owns those semantic
labels so another platform or a future regenerated raster does not need to
invent them, but the Saturn text package must not catalogue their pixels as
physical text records.

An empty slot displays `未使用` / `EMPTY`. The stock source stores five visible
cells and the English field has an 80-pixel bound. SAVE and LOAD contain
identical physical copies; the source manifest validates both through one
semantic record. Inter-character centring blanks and the slot's unused
one-glyph left margin are geometry, not authored text.

A populated slot has two rows. The first row contains a player name followed
by a location. The original name segment is three given-name cells, one
separator cell, and three family-name cells. The translated renderer has an
eight-cell/128-pixel strip. The complete editable template is
`{first_name} {last_name}`: the renderer supplies the saved values and may omit
the asset-owned separator when either value is empty. The current Saturn
compiler still requires `{first_name}` before `{last_name}` because its trusted
path reads the adjacent save fields in that order; honoring a reversed template
requires a second renderer path and remains explicit debt. This
`save_load.json` field controls visible slot layout only. The shared
`NAME_FW_FULL` storage row is rebuilt independently from
`player_profile.json#full_name_storage.text`; both Profile Entry and LOAD use
that one authored order and separator, so editing the slot display cannot
silently change runtime player-name storage. A special fixed location has seven Japanese cells or
112 English pixels. A generated dungeon label has the same seven-cell stock
field but a proved 144-pixel translated limit because it may append an editable
floor form.

The second row has independently bounded fields:

- `Lv{level}`: four Japanese cells or 64 English pixels;
- `{day}／{month}` / `{day}/{month}`: five cells or 80 pixels;
- `{hour}：{minute}` / `{hour}:{minute}`: five cells or 80 pixels.

Day, month, hour, minute, level, location identity, floor number, and player
names are runtime values. They are not translatable literals. Alignment blanks
and the non-zero-padded numeric field geometry also remain layout. The visible
`Lv`, date slash, time colon, and `地下…階` floor scaffold are authored text:
their identical SAVE/LOAD FONT16 copies are extracted and bound as literal
scaffolds of the complete `save_load.json` slot templates and
`field/location_formats.json` floor template. The same floor record supplies
the final `階` glyph for positive floors; the complete above-ground form remains
an independently editable template even though it has no separate stock
literal record.

On SAVE, selecting an occupied slot opens a one-row prompt (`記録の更新をしますか？`
or `ゲームを終了しますか？`) followed by the FONT16 choices `YES` and `NO`.
Prompts are 11 Japanese cells or 176 English pixels; choices are three cells or
48 pixels. The stock-English choice records are physical text and remain
editable despite needing no translation.

SAVE/LOAD system text has separate contracts rather than one generic message
surface: small failures are three rows of 11 Japanese cells or 176 English
pixels; capacity messages are two rows of 17 cells or 272 pixels; the start
warning is four rows of 20 cells or 320 pixels; and the storage-management
warning is six rows of 20 cells or 320 pixels. The standalone capacity display
is three cells. `capacity_number.text` is the sole authored owner of `129`;
typed `{capacity_blocks}` substitutions materialize that value into each
complete prose template and the direct LOAD record at `LOAD.BIN` `0xB1AE`.
Translated rows must satisfy both their pixel width and their encoded-glyph
ceiling. Those ceilings are 16 for a special location, 24 for a dungeon
location, 17 for the joined player name, 4 for level, 5 for date/time and the
empty state, 11 for prompts, 3 for choices, 24 per small-message row, 25 per
capacity-message row, 63 per warning row, and 3 for the capacity value.

PSP reuses the shared location identities and general save semantics without
copying translations. Its game title, slot title, difficulty labels, cancel
prompts, fallback location, and complete `psp_detail` template remain PSP-only
fields because that savedata presentation is a different consumer layout from
the Saturn two-row slot.


### Event Window

Most of the game's dialogue displays through this window.
There is space for 20 FONT16 characters per row, and 3 rows.
The game rendered resolution can change. It's always the internal 352x224, but depending on the scene, black bars are used to reduce the effective resolution down to a width of 320px. At its minimum width, it renders with no margins, across this full 320px span.

Patch policy: the English renderer intentionally wraps within 300px, using a
10px margin on each side of that 320px surface. This shared geometry matches
the PSP implementation for translation and preview parity; it is not intended
to reproduce the stock edge-to-edge wrap.

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

### Profile Entry

The player fills out their profile by progressing through several inputs. For each input, they need to provide a valid input value, and confirm with END to advance.

The game renders each input screen with a top prompt section, consisting of a FONT16 question (i.e., "コードネームは？") and an input area (a series of underline characters to indicate available length/spacing, with a white bounding box to indicate the active input character target).

`ui/profile_entry.json` owns every prompt, choice, occupation, tab label,
English replacement row, and default value. The shared complete-name storage
template lives at `player_profile.json#full_name_storage.text`; Profile Entry
and SAVE/LOAD both rebuild `NAME_FW_FULL` from its authored placeholder order
and one literal separator. Either placeholder order is valid, with each field
appearing exactly once. The visible SAVE/LOAD slot template remains a
separate consumer layout. Confirmation draws the first and last fields at
independent x positions, so its much wider visual gap is layout and does not
override the shared storage format. Underline slots, cursor rectangles,
highlight colours, and centering blanks are visual/layout state rather than
additional text.

The sequence is as follows:
1. Full Name: ___ ___ - 3 glyphs for last/first names. This is not ideal in English. The patch currently splits this into two separate screens.
2. Codename: ________ - 8 glyphs.
3. Place of residence: ___市___区 - 3 glyphs for city/ward. This is also not ideal in English. The patch currently splits this into two separate screens as well. These fields are pre-filled with 平崎 and 朝日.
4. Occupation: N/A

#### Full Name + Place of Residence Input

The player can switch between three pages for the text input. 漢字, ひらがな, and カタカナ. The actively-highlighted page has yellow text instead of white. The position of the grid cursor is indicated by a yellow bounding box. This bounding box borders either the current glyph's cell, or the page's rectangle, depending on where it's positioned.

Each page consists of a navigable input grid. Ordinary grid cells are drawn
from `KANJI.FON`; the action cells are special, font-owned compound images.
Cells have different colourations:

- Blue characters: Used to indicate the start of a section on the kanji page (i.e., あ, い, う, え, お, か, き, etc.). If selected, is treated the same as a hiragana glyph input.

- White characters: Used to indicate ordinary glyphs.

- Green characters: Used to indicate actions. I.e., the left and right arrows move the active input cursor left/right. The "END" symbol confirms the current input and advances to the next screen if accepted.

- Empty cells: These are treated as space characters if selected.

The kanji page consists of a full-window grid, 8 rows tall, 19 rows wide, with the ability to scroll down. To assist in navigation, pressing the L/R buttons moves the cursor between the blue section characters, and scrolls the window to place the highlighted blue section at the top, if there are enough rows below it to allow this.

The hiragana and katakana pages consist of three small grids distributed evenly and centered inside the window.
Each grid is 6 rows, 5 columns. The first and second grids are the standard kana and small vowels/ya/yu/yo/tsu/katakana-vu. The third grid consists of dakuten/handakuten variants, and the dash and interpunct. It also has the left/right arrows and END command button.

The mature English replacement retires those pages in favour of three tabs,
`UPPER`, `lower`, and `SYMBOL`. It still draws eight navigable rows of 19 cells,
with up to 13 authored content cells starting at column three. Its six row
strings are editable assets. Every cleared navigable cell remains a selectable
blank; the trailing space in the second SYMBOL row is the one blank that is
part of authored row content. The grid text uses the named `KANJI.FON`
`stock_latin` reference set, which publishes the exact preserved digit,
uppercase, lowercase, punctuation, interpunct, and blank cells. It does not
regenerate or overwrite those retail glyphs.

Stock physically stores `漢字`, `ひらがな`, and `カタカナ` twice: once in the
combined tab row and once in each selected-tab template. Each byte-identical
pair has one semantic asset owner and two source locations. Katakana remains
inventoried even though the English runtime leaves it dormant. The city `市`
and ward `区` suffix glyphs are likewise physical editable records, although
the split English screens retire that stock address scaffold.

The left/right controls and `終了` are semantic text but their retail rasters are
font/image-owned compounds, not ordinary grid strings. `grid_end.text` records
the editable `END` meaning and the two original `FONT16` cells explicitly. The
mature English code selects the stock action through display code `0x01F7`, so
a different visible label requires coordinated engine/font output rather than
an asset-only substitution. The English replacement does not currently draw
the left/right actions.

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

The mature English confirmation builder has one known parity defect: it omits
the terminating `0x8000` word after its 19-cell template, allowing the stock
drawer to continue into the following `漢字` data. The rewrite should terminate
that span explicitly; this is a documented output correction, not wording to
preserve in an asset.

### 2D Map

Every proved player-facing `MAP2D.BIN` string is ordinary FONT16 data. No
MAP2D label crosses into a baked image-glyph surface. The physical inventory
keeps the runtime pieces visible instead of treating the mature renderer's
omissions as deleted prose: `朝日` at `0x1E684` and `平崎` at `0x1E6C0` are
initial values shared with Profile Entry, `区` is stored at both `0x1E688` and
`0x1E6DE`, `市` at both `0x1E6C4` and `0x1E6E2`, and `全図` at `0x1E6CA`.
Extraction verifies each pair of suffix copies byte-for-byte. The independently
terminated `雲` at `0x1E6D4` remains an editable unresolved asset: no absolute
reference or live destination selector for it has yet been proved.

#### World Map

The world map has two text consumers. All use FONT16.

In the bottom-left is a grey rectangle with the complete source template
`{city}市全図`. The city component is centered within its four-cell allocation;
the complete human-facing rectangle is six Japanese cells or 96 translated
pixels. `ui/map_2d.json#world_city_label.text` owns the template and translates
it as `{city}`. The mature English adapter constructs the city inside a stricter
64-pixel internal component and deliberately omits both suffixes. That internal
policy does not shrink the 96-pixel surface contract or leave `市全図` as
hand-maintained renderer text.

In the top-right are conditionally displayed destination rectangles. Each is
four Japanese cells or 64 translated pixels and is horizontally centered. The
dynamic source template is `{ward}区`, translated as `{ward}`. Five fixed
records reuse the shared location catalogue: Rinkai Park, Mt. Kasagi, Yarai
Ward, Chuo Ward, and Hibarigaoka. Only Mount Kasagi needs a MAP2D-specific
compact variant: the canonical `Mount Kasagi` is 69 pixels, while `Mt. Kasagi`
is 55 pixels and fits this strip. Identical fixed forms are not copied into a
second map catalogue.

#### Area Map

Within each area, the bottom-left rectangle has eight Japanese cells or 128
translated pixels. Stock draws two independently centered four-cell components:
the complete `{city}市` city label followed by the current `{area}` label. These
are separately authored templates. The mature English adapter explicitly
suppresses the city component on this screen and renders the area alone; the
asset does not silently discard a city placeholder, and the human surface
remains the proved eight-cell rectangle.

While exploring the map, the player may traverse over a conversation point. This displays on the screen in a large pair of green boxes:
"＞誰かいる。話しかけますか？"
and vertically stacked, "YES", "NO".

The prompt and choices reuse the shared field-message assets. The prompt is a
14-cell/224-pixel FONT16 surface; its mature English text is 32 proportional
glyphs advancing 171 pixels and is precomposed into those cells. Each choice
uses the proved three-cell/48-pixel surface, with a three-glyph encoded-row
ceiling. Their physical records remain at `0x1E756`, `0x1E774`, and `0x1E77C`
respectively.

### 3D Map

#### Location Window

In the top-right of the 3D map is the compass and location text.
The location text is displayed as a row of 4 FONT16 glyphs. Examples include 氷川神社, カーサ乾, 図書館. These are left-justified.
Below the location text is another 4 glyph strip for floor information. The format is an optional 地下 prefix, followed by an up-to 2 digit number, followed by 階. These are right-justified. The game never combines 'underground' with a floor that requires more than 1 digit.

In the top-left of the 3D map is the moon phase and currency information. The game uses FONT8 to render two rows of 4 letters for the moon phase. These can include English texts, "NEW", "FULL" and "MOON". The first two being on the top row, the latter being on the bottom.

#### Analyze Grid

All of the grid text is rendered in FONT8.

Pressing R (default) in the 3D Map view opens the Demon Analyze table. The table includes columns for "RACE", "NAME', "LV", "HP", "MP', "ATK", "DEF". Highlighting a column header sorts the table by that metric. The player can scroll down the table to view the demons they've encountered thus far.

On the 352-pixel raster, the header starts are x=28, 80, 156, 202, 236,
264, and 300. Their corresponding one-row limits are 52, 76, 46, 34, 28,
36, and 52 pixels. The stock header baseline is y=20. These fixed Latin
headings use the original Japanese FONT8 English alphabet rather than the
mixed-case replacement face.

The table shows 16 rows at y=32 through y=212 in 12-pixel steps. Row fields
start at x=28 for race, x=80 for name, then x=164, 208, 244, 280, and 316 for
the five numeric values. Each demon's Japanese row consists of a five-kana
race and an eight-glyph demon name. The translated race has 52 pixels and the
translated name has 84 pixels before the first numeric value. Wider names are
not clipped by the mature renderer, so over-limit authored values remain a
surface-validation issue rather than being silently truncated.
With the current FONT8 metrics, `Yamata-no-Orochi` advances 93 pixels and
`Yomotsu-Shikome` 88 pixels, so those two active names exceed the actual
84-pixel row gap. `Take-Mikazuchi` and `Jack-o'-Lantern` exceed the 76-pixel
header-column span but still fit the row's later numeric start.

The 43 physical grid race spellings are katakana source variants of the same
semantic race entries used by the FONT16 detail view. They do not create a
second translation catalogue.

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

The translated popup retains those three rows with a 64px limit per row. Its
separately stored `(No data)`, `Delete?`, `Yes`, and `No` fields are authored
text, not renderer literals. The MAZE interaction choices use their original
three-cell footprint, measured as a 48px translated row.

#### Auto Recovery

Pressing Y (default) on the 3D Map displays "オートリカバーON" in the green toast window briefly.

#### Field Messages

Along with having the existing "Someone is here, will you talk?" message prompts that appear on the 2D Map, there are other field messages that can appear, i.e., when discovering a treasure chest.

{item}を手に入れた
{item}を見つけた
{yen_symbol}{currency_amount}を手に入れた
{mag_symbol}{currency_amount}を手に入れた
etc.

The yen and magnetite paths use distinct leading symbol glyphs before the
formatted amount. Both currency paths and the successful item-acquisition path
reuse the same stored `を手に入れた` suffix, but they are separate
human-facing templates. The runtime selects the authored use and supplies the
typed item or amount; it must not own the symbol or surrounding wording.

Some may also appear briefly before an encounter transition, warning of an ambush or advantage.


### Combat

#### Party Panels

The party panels are a set of six rectangular panels located near the bottom of the screen.
Each panel consists of two rows. The top is a FONT8 consumer, 8 glyphs (though space for ~12); it's the demon/player/unit's name (left-justified) or "EMPTY" (centered) when no unit is present.
The bottom row uses FONT6 and consists of the HP/MP labels and dynamic values. It may not require a special renderer hook, but its visible labels/templates must still be asset-owned.

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

If the player hasn't obtained the demon's analyze data, instead of showing anyting beyond the top two lines, the game will show "NO DATA" centered in the area below them (around line 5).

Pressing R again pages the window. Lines 1 and 2 remain the same, but 3 onwards are replaced with a list of FONT8 strings for each of the demon's known skills (up to 7).

#### Help

Pressing X in combat opens a help window at the top of the screen. This displays 2 rows, 20 columns of FONT16 characters, and describes the currently-highlighted menu option.

This can be the command (i.e., FIGHT - "悪魔との戦闘") or more specific, like an item description.

#### Command List

These are displayed in English already, using the game's FONT8 text.

These command labels intentionally use the stock Japanese FONT8 Latin face.
The translated font must preserve that alphabet as a separately selectable
glyph set; ordinary mixed-case FONT8 consumers use the replacement English
face instead.

Options include "FIGHT, TALK, ESCAPE, AUTO, SWORD, GUN, COMP, ITEM, MOVE, GUARD, GO, OFFENSE, DEFENSE, RETURN, PRESET, REPEAT".

The retail battle action table is present as three byte-identical physical
copies in COMBAT, MAZE, and NORMCOM. Its exact visible spellings are `OFFENCE`
and `DEFENCE`; these are retained as consumer-specific variants of the shared
`OFFENSE` and `DEFENSE` terminology. The four item/skill actions and the rest
of that table are physically catalogued. The render selectors for `FIGHT`,
`TALK`, `ESCAPE`, `AUTO`, `PRESET`, and `REPEAT` have not yet been proved, so
their authored fields remain explicit binding debt rather than inferred uses.

#### Item/Skill Windows

These windows consist of 9 rows, 2 columns, all FONT8 consumers.
Each item/skill is represented as a coloured icon, followed by space for 8 glyphs, and 2 numbers (quantity/cost).
The skill window also includes non-skill options, like ATTACK, MAGIC, EXTRA, GUARD, without leading icons.

#### Conversation

Talking to demons uses a very similar window to the standard event window. However, some additional actions can occur here.

The stock Japanese dialogue area is three rows of 20 FONT16 glyph cells. The
translated renderer has three rows and a 300-pixel usable width. This is a
separate `battle.negotiation_dialogue` consumer even though its measured
geometry matches the event window.

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

#### Result Window

On defeating the enemies, the game displays a result window, all using FONT8 consumers.

Row 1: [macca symbol] [amount of macca]
Row 2: [player name, 8 glyphs] [rei's name, 8 glyphs]
Row 3: "EXP" [exp earned]
Row 4: "ITEM"
Rows 5-7(?): Items obtained from the battle, if any; else empty
Bottom row: "ませき" [number of lifestones obtained] "ほうぎょく" [number of beads obtained]

The translated shared battle runtime now covers the party names, Analyze race
heading/name/affinity fields, item and skill lists, the help strip, Demon Chat,
result names and labels, and the complete fixed-width console bank. Its measured
English limits are 80 pixels for item, skill, and party names; 112 pixels for
Analyze names and affinities; 300 pixels by two rows for help; 176 pixels by two
rows for Demon Chat; and 88 pixels for result names. The Analyze race heading is
an eight-cell FONT8 record rather than a measured variable-width slot.

### Ritual Console

The NORMCOM ritual sequence uses its own `BUTU_SRF.MDT` FONT16 pointer bank. It
is not a Demon Chat alias even though both are console-like overlays. All 144
physical rows remain catalogued; 64 visible rows bind to independently editable
`ritual/console.json` fields and the other 80 remain blank binary evidence. The
translated renderer has a proved 176-pixel width. Its row count has not yet been
measured and remains explicitly unknown rather than borrowing Demon Chat's
two-row contract.


### COMP Menu

The COMP menu consists of a top 2-row FONT16 Help strip, a block of the 6 active party panels, and another block of the 12 stock demons.

Its top-level FONT8 commands are `COMP`, `MAGIC`, `ITEM`, `EQUIP`, and `STATUS`.
They use the preserved stock Latin face and are separately editable from equal
words used by battle or facilities.

The translated COMP core now owns the two-row, 300-pixel help surface; the
80-pixel active and stock demon-name panels; and the 80-pixel item/magic name
grid. The 319 demon names remain single authored fields: 210 fit the direct
eight-byte retail records, while 109 use a runtime compact overflow pool. The
NORMCOM ritual console composes beneath this target but remains a distinct
consumer. The equipment and detailed-status layers compose as separate checked
stages on top rather than being hidden parts of the COMP core.

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

The implemented `equipment.ui` contract treats this and the shop equipment
panel as two consumers of one editable surface. Auto/Unequip are 40-pixel
FONT8 labels; base and derived headings have 23- and 48-pixel slots; item names
use 80 pixels. The shop comparison consumer additionally has a 72-pixel
character-name slot and the existing 16-pixel `Inv.` label. Cursor boxes and
numeric substitution remain engine layout; every visible word is resolved from
`assets/text`.

#### Status Screen

##### Human Status

The human status screen has the player/human's codename/name in the top-left in FONT16.

Below is a 5-line list in FONT8 of :
LV ##
HP ####/####
MP ####/####
EXP #####
NEXT #####

The traced NORMCOM layout keeps these as separate one-row FONT8 compositions,
not free-flowing strings. `LV` and `CP` place their dynamic value at x=40;
`EXP` and `NEXT` place it at x=80. `HP` and `MP` place the current value at
x=40, their shared one-cell separator at x=48, and the maximum value at x=80.
The `LV`, `HP`, `MP`, `EXP`, and `CP` prefixes allow three glyphs, while `NEXT`
allows seven. These starts do not establish the numbers' maximum digit counts
or final right edges, so the complete numeric-row widths remain unmeasured.

In the middle is a hexagon graph of the player's stat distribution. At the six points of the hexagon are the six in-game stats, 力　知　魔　耐　速　運.

In the top-right  is the player's AUTO setting (i.e., AUTO SWORD), and the party alignment (i.e., "P.A. LAW"). FONT8

Both are fixed one-row, twelve-cell FONT8 compositions. Their selected value
starts at x=40 and has seven cells. `AUTO` uses four of the five cells before
that value; `P.A.` is exactly four cells, leaving the fifth cell as layout
space. The separating space in each authored template declares that boundary;
it is not another freely positioned text glyph.

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

The selected demon name occupies a 128x16 raster and starts at x=2, leaving
126 translated pixels; the race occupies a 48x16 raster and starts at x=2,
leaving 46 pixels. The Japanese inputs are eight and three FONT16 glyphs
respectively.
The current `Avatar` and `Element` race translations advance 47 and 50 pixels
in the mature FONT16 renderer, so both exceed the strict 46-pixel detail slot;
that is retained as explicit review debt rather than hidden with truncation.

The top-left stat block is a 96x60 raster containing LV, HP, MP, and CP
(summon cost). The four FONT8 rows begin at y=0, 12, 24, and 36; each dynamic
value begins separately at x=40. These prefixes reuse the shared, editable
status templates rather than introducing Analyze-only copies.

The bottom left now shows a skill table.
This is a 96x80 FONT8 raster with six visible rows at y=8 through y=68 in
12-pixel steps. Skill names start at x=0 and have an 80-pixel contract; the
numeric cost is anchored at x=80 and its editable one-glyph unit at x=88.
The complete typed templates are `{cost}M` for magic/MP costs and `{cost}H`
for health/HP costs. The retail renderer selects M for ability IDs through 159
and H for IDs above 159. There is no item relation in this Analyze consumer.

The top right now shows just the AUTO command (i.e., "AUTO GO").
Instead of derived stats, the right shows three new parameters:
忠誠度 (FONT12)  # (FONT8)
CTRL   1ST (or similar; both FONT8)
TYPE (FONT8)  [personality string (FONT12 Kanji)]

The translated Loyalty and personality rasters each have 38 usable pixels.
Loyalty's FONT8 number begins separately at x=72; its maximum digits and final
right edge are not yet proved. `TYPE` occupies its own four-cell FONT8 prefix,
and the personality raster is a separate consumer, so the intervening layout
space cannot be borrowed by either translation. `CTRL` is a ten-cell FONT8
composition: its prefix begins at x=0 and may use five cells, while its
three-cell rank begins at x=56. The cells between those slots are layout, not
text. Each L/N/C/L/D alignment-axis label occupies one FONT8 cell. Law and
Light remain separate authored fields even though both default to `L`; the
runtime keeps the retail shared pointer when they agree and emits a dedicated
Light pointer only when an edit makes them differ.

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
The affinity raster is 128x32. Japanese uses two rows of eight FONT12 glyphs;
the translated consumer uses FONT8 and may advance through 127 pixels while
retaining the full 128-pixel surface.


### Level Up

#### Main Panel

The ordinary level-up panel is its own `LEVEL_UP.BIN` consumer. `LEVEL UP` is
one fixed FONT8 row of eight cells. The character-name texture is 128x16: the
Japanese path draws up to eight FONT16 cells, while the mature English path
uses a 96px safe limit for the five asset-backed fixed names. The live player
codename uses the same texture but is a separate dynamic consumer with the full
128px physical row; the fixed-name limit must not be misapplied to player input.

The parameter display reuses the six base-stat labels, eight derived-stat
labels, and the generic Attack and Accuracy variants from the detailed status
vocabulary. The Japanese base labels occupy one 16x16 cell; their compressed
English forms occupy 12px. Derived labels occupy four FONT12 cells in Japanese
and 46px in English. Generic Attack and Accuracy occupy three FONT12 cells in
Japanese and 46px in English. These are separate LEVEL_UP bitmap consumers even
though they share authored fields with the status screen.

`LV`, `HP`, `MP`, `EXP`, and `NEXT` are fixed FONT8 labels composed with live
numeric values. Their individual numeric extents are not all proved and must
not be inferred from the generic nine-digit number drawer. The remaining-point
display has a right-aligned value, a four-cell graphical ornament, and a
four-cell `LEFT` suffix. Its complete renderer spans at most 17 FONT8 cells:
nine numeric cells, four ornament cells, and four label cells. The four spaces
stored before `LEFT` reserve the ornament and are not authored text.

Two exceptional numeric rows are still authored text even though retail builds
them directly in code: maximum level replaces the seven-cell NEXT value with
`-------`, and a character with no MP capacity displays the authored `---/---`
form across the current/maximum MP layout. The renderer inserts one fixed
alignment cell after the slash, producing eight displayed cells without making
that gap translator-owned. Both fields use the preserved stock FONT8 hyphen and
slash cells.

The confirmation layer draws an `OK` action label in a two-cell FONT8 slot
beside a button glyph, plus vertical `YES` and `NO` choices in three-cell FONT8
slots. The stored leading space before `NO` is centering, not part of the
authored word.

#### Learned Magic Window

Learning an ability uses a separate conditional texture, not another row of
the main panel. In normal play it is reached for Rei, rather than for a demon.
Surface 19 is 144x32 and contains two FONT16 rows. The heading is drawn at
x=2, y=0 and occupies five Japanese glyph cells; the English contract is a
conservative 128px, with `Learned Magic` currently measuring 74px. The learned
magic or skill name is drawn independently at x=2, y=16 and permits eight
Japanese glyph cells or 128 English pixels. The heading, the selected ability,
and their two-row presentation are distinct text consumers.


### Fusion
Most fusion consumers are FONT12.

#### Demon Compendium

The demon compendium doesn't exist in the original Saturn release. However, it was included in a non-gameplay form with a bonus pack-in disc "Akuma Zensho".
This disc includes demon lore entries that would later appear in-game in the PSP version. For that reason, these should be translated and paired with their respective parent demons.

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

These FONT8 labels, and the corresponding bar and healer labels below, use the
preserved stock Latin face. `REVIVE` and `STATUS` are stored by the retail game
as compound FONT8 cells, but are exposed here as normal editable words through
explicit physical binding maps.

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

#### Patron List
TALK shows a list of 1-row patron names, each FONT8 with space for 8 kana.

#### Status List
Like the fusion status list window, but FONT8.

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

#### Heal One List
Similar to the Heal All list, however the window has been widened.
Each unit shows, after the top row name, HP ####/####, and after the bottom row cost, MP ####/####.

#### Status List

Like the fusion status list window, but FONT8.

### MAG Exchange

Top-level options are displayed in an event text window and may not require a special renderer hook. They must still be represented by editable assets.

When converting mag, two additional FONT8 help windows appear.
{yen symbol} {current yen}
{mag symbol} {current mag}

and
RATE
{mag symbol}10={yen symbol}{current rate} (or vice-versa, depending on the exchange).
