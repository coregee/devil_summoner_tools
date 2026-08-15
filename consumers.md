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

### Save/Load Screens

#### Load Screen

The top-left of the load screen renders two texture buttons, "LOAD" and "NEW GAME".
The top-right of the load screen renders two more buttons, "本体" and "カートリッジ".

The load screen itself lists three save files. All of the text is in FONT16.

Empty save files display "未　使　用" (with equivalent spaces between) in the center of their bounding area.

Populated save files display across two rows. They are laid out as follows, with the number indicating the reserved glyphs.
[First Name - 3][Space - 1][Last Name - 3][Space - 1][Location - 7]
["Lv" + 1/2 numbers][Space - 2]["DD/MM" for non-zero padded date][Space - 1]["HH:MM" for non-zero padded 24 hour time]

There is a 1 glyph left margin for the populated save files that goes unused.

#### Save Screen

The save screen is similar to the LOAD screen, except the top left doesn't have "LOAD"/"NEW GAME" but instead a "SAVE" button.

Selecting a save file that already exists displays a prompt window, with FONT16 text, and below, the options "YES", "NO" also in FONT16, with a green bounding rectangle and orange text to indicate selection.

Prompts can include "記録の更新をしますか？", "ゲームを終了しますか？".


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

The sequence is as follows:
1. Full Name: ___ ___ - 3 glyphs for last/first names. This is not ideal in English. The patch currently splits this into two separate screens.
2. Codename: ________ - 8 glyphs.
3. Place of residence: ___市___区 - 3 glyphs for city/ward. This is also not ideal in English. The patch currently splits this into two separate screens as well. These fields are pre-filled with 平崎 and 朝日.
4. Occupation: N/A

#### Full Name + Place of Residence Input

The player can switch between three pages for the text input. 漢字, ひらがな, and カタカナ. The actively-highlighted page has yellow text instead of white. The position of the grid cursor is indicated by a yellow bounding box. This bounding box borders either the current glyph's cell, or the page's rectangle, depending on where it's positioned.

Each page consists of a navigable input grid. The grid consists entirely of FONT16 glyphs, with different colourations:

- Blue characters: Used to indicate the start of a section on the kanji page (i.e., あ, い, う, え, お, か, き, etc.). If selected, is treated the same as a hiragana glyph input.

- White characters: Used to indicate ordinary glyphs.

- Green characters: Used to indicate actions. I.e., the left and right arrows move the active input cursor left/right. The "END" symbol confirms the current input and advances to the next screen if accepted.

- Empty cells: These are treated as space characters if selected.

The kanji page consists of a full-window grid, 8 rows tall, 19 rows wide, with the ability to scroll down. To assist in navigation, pressing the L/R buttons moves the cursor between the blue section characters, and scrolls the window to place the highlighted blue section at the top, if there are enough rows below it to allow this.

The hiragana and katakana pages consist of three small grids distributed evenly and centered inside the window.
Each grid is 6 rows, 5 columns. The first and second grids are the standard kana and small vowels/ya/yu/yo/tsu/katakana-vu. The third grid consists of dakuten/handakuten variants, and the dash and interpunct. It also has the left/right arrows and END command button.

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

### 2D Map

#### World Map

The world map has two text consumers. All use FONT16.

In the bottom-left is a grey rectangle, with the text "＿＿＿市全図", dynamically inserting the player's chosen city. The left city text is actually centered within its available 4 glyph space. In total, this rectangle provides 6 glyphs of space.

In the top-right are multiple grey rectangles. These display conditionally based on the areas the player is permitted to access at their point in the story. There is enough space for 4 glyphs in each. Examples include "＿＿＿区" (player input substituted), "臨海公園", "中央区". All are horizontally centered.

#### Area Map

(All also FONT16).

Within each area, the game shows a rectangle in the bottom-left with 8 glyphs of available space.
The first 4 are the chosen ___市 centered within the allocated space. The next 4 are the current area's text centered within the allocated strip.

While exploring the map, the player may traverse over a conversation point. This displays on the screen in a large pair of green boxes:
"＞誰かいる。話しかけますか？"
and vertically stacked, "YES", "NO".

### 3D Map

#### Location Window

In the top-right of the 3D map is the compass and location text.
The location text is displayed as a row of 4 FONT16 glyphs. Examples include 氷川神社, カーサ乾, 図書館. These are left-justified.
Below the location text is another 4 glyph strip for floor information. The format is an optional 地下 prefix, followed by an up-to 2 digit number, followed by 階. These are right-justified. The game never combines 'underground' with a floor that requires more than 1 digit.

In the top-left of the 3D map is the moon phase and currency information. The game uses FONT8 to render two rows of 4 letters for the moon phase. These can include English texts, "NEW", "FULL" and "MOON". The first two being on the top row, the latter being on the bottom.

#### Analyze Grid

All of the grid text is rendered in FONT8.

Pressing R (default) in the 3D Map view opens the Demon Analyze table. The table includes columns for "RACE", "NAME', "LV", "HP", "MP', "ATK", "DEF". Highlighting a column header sorts the table by that metric. The player can scroll down the table to view the demons they've encountered thus far.

Each demon's row consists of a 5-kana race and 8-character demon name. Wider values would overrun the available space.

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

Options include "FIGHT, TALK, ESCAPE, AUTO, SWORD, GUN, COMP, ITEM, MOVE, GUARD, GO, OFFENSE, DEFENSE, RETURN, PRESET, REPEAT".

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


### COMP Menu

The COMP menu consists of a top 2-row FONT16 Help strip, a block of the 6 active party panels, and another block of the 12 stock demons.

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

#### Status Screen

##### Human Status

The human status screen has the player/human's codename/name in the top-left in FONT16.

Below is a 5-line list in FONT8 of :
LV ##
HP ####/####
MP ####/####
EXP #####
NEXT #####

In the middle is a hexagon graph of the player's stat distribution. At the six points of the hexagon are the six in-game stats, 力　知　魔　耐　速　運.

In the top-right  is the player's AUTO setting (i.e., AUTO SWORD), and the party alignment (i.e., "P.A. LAW"). FONT8

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

The top-left stat block is now LV, HP, MP, and CP (summon cost).

The bottom left now shows a skill table.
These are FONT8 8-glyph strings, with space for a 2 digit + letter FONT8 cost beside them (i.e., "12H", "14M").
There can be up to 7 skills.

The top right now shows just the AUTO command (i.e., "AUTO GO").
Instead of derived stats, the right shows three new parameters:
忠誠度 (FONT12)  # (FONT8)
CTRL   1ST (or similar; both FONT8)
TYPE (FONT8)  [personality string (FONT12 Kanji)]

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
This uses the FONT12 path.


### Level Up

When a demon learns a new magic or skill, the level-up screen displays a fixed
FONT16 learned-magic label and the corresponding magic/skill name through
separate text draws. The exact combined geometry still needs to be measured.
Both parts, and their composed presentation, are text consumers.


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
