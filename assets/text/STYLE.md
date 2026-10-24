# Translation style guide

How the English script is written, so that changes stay consistent. It covers
tone, the technical rules every line has to follow, names and terms, and how
each character and negotiation personality talks.

## Tone

*Devil Summoner* is a hardboiled occult detective story set in an ordinary
Japanese city in the mid-1990s. The English should read like that: plain,
spoken and a little dry, not grand or fantasy-flavored.

- **Meaning first, then natural English.** Keep what the line says and how the
  speaker feels about it. Reword freely to get there; don't follow Japanese
  word order or sentence breaks.
- **Tense follows the Japanese.** Non-past Japanese (〜る, 〜ようだ, 〜いる,
  〜ない) stays present; 〜た stays past. Don't shift tense for style.
- **Short.** The windows are small. Prefer the shorter of two equally good
  wordings, and cut filler (`really`, `just`, `quite`) that the Japanese doesn't
  carry.
- **Spoken, not written.** Contractions are normal for almost everyone. Avoid
  them only for the characters and personalities below who speak formally.
- **No added jokes or modern slang.** Keep it 1995. No memes, no internet
  speak, no references the original doesn't make.
- **Don't explain.** If a term is unfamiliar in Japanese too, leave it
  unfamiliar in English. Add a word of context only when the Japanese reader
  would get it and an English reader wouldn't.
- **Swearing follows the Japanese.** `クソ`, `野郎`, `てめえ` are rude; render them
  as rude (`damn`, `bastard`, `you son of a bitch`) at roughly the same
  strength. Don't escalate.

## Technical rules

These are enforced by the build or the editor, or the text will look wrong
in game.

- **Placeholders** such as `{item}`, `{ward}`, `{city}`, `{first_name}`,
  `{codename}`, `{kyouji_name}` must appear the same number of times as in the
  reference. They can move within the line. `{city}` and `{ward}` default to
  `Hirasaki` and `Asahi` but the player can rename them, so they never include
  "City" or "Ward": write `{city} City` or `in {ward}` as the sentence needs.
- **`{n}`** forces a line break. Story dialogue wraps automatically at 300px and
  spills onto extra pages, so `{n}` is only needed where a break reads better.
  Keep every explicit line within 300px, or it re-wraps mid-line.
- **Negotiation timing codes** `{WAIT}` and `{BEAT}` are pauses. Keep the same
  number in roughly the same places, so the rhythm survives. `{OP:xxxx}` codes
  change text color and come in pairs; keep both.
- **Window sizes:**
  - story dialogue: three lines of 300px per page;
  - negotiation dialogue: three lines of 300px;
  - three- and four-way negotiation choices: one line of 150px (142px is safer);
  - two-way negotiation choices: one line of 240px;
  - other screens: see [`consumers.md`](../consumers.md) or the editor.
- **Characters.** The font has plain ASCII only: letters, digits and
  `` !"#$%&'(),-./:<=>?~ ``. Accented letters and other symbols don't exist.
  Curly quotes and `…` are converted automatically, but `—` becomes a single
  hyphen, so:
  - dashes: `--` (`Find my daughter--please!`);
  - ellipses: `...` (or `…`, which becomes `...`). Use them where the speaker
    trails off or hesitates, not as general punctuation;
  - quotes: straight double quotes for titles and quoted words;
  - interrobang: `?!`, not `!?`.
- **Speaker labels** are `Name: ` at the start of the first line, matching the
  label list in the glossary.
- **Narration and system lines** start with `> ` where the Japanese has `＞`.
  Keep them flat, and follow the Japanese tense: past where it's past
  (出かけていった → `> Rei Reiho headed out.`), present where it isn't
  (開けられるようだ → `> It looks like the stone door can be opened.`,
  誰もいない → `> There is no one here...`).

## Names

Japanese names are given name first, in Hepburn romanization, with the long
vowels the script already uses: `Kyouji`, `Yatou`, `Isono`. Keep established
spellings even where another system would differ. Honorifics are dropped;
use `Mr.`/`Ms.` where politeness matters (`Mr. Kuzunoha`) and titles as English
(`Professor Azuma`, `Inspector Momochi`, `Detective Isono`). Chinese names use
pinyin (`Chen Jianmin`).

Demon names always match `demons.json`; race names match `races.json`; item,
spell and equipment names match their catalogues. Never rename one of these in
dialogue alone.

## Glossary

| Japanese | English | Notes |
| --- | --- | --- |
| 葛葉キョウジ | Kyouji Kuzunoha | |
| レイ・レイホゥ | Rei Reiho | |
| 秦野久美子 | Kumiko Hatano | |
| マリー | Marie | The fortune-teller across the street. Rei calls her `that old hag` (クソババァ, ババァ). |
| ヴィクトル | Victor | |
| シド・デイビス | Sid Davis | |
| タカシ | Takashi | |
| 吾妻教授 | Professor Azuma | |
| ドクター・スリル | Dr. Thrill | |
| マダム銀子 | Madame Ginko | |
| 百地警部 | Inspector Momochi | |
| 磯野刑事 | Detective Isono | |
| 陳健民 / 陳大人 | Chen Jianmin / Mr. Chen | |
| イナルナ姫 | Princess Inaruna | |
| 平崎（市） | Hirasaki (City) | Default for `{city}`. |
| 朝日区 | Asahi Ward | Default for `{ward}`. |
| 中央区 | Chuo Ward | Not "Central Ward". |
| 矢来区 | Yarai Ward | |
| 矢来銀座 | Ginza Arcade | |
| 矢東ビル | Yatou Building | |
| 北山大学 | Kitayama University | |
| 笠置山 | Mount Kasagi | |
| 雲雀ヶ丘 | Hibarigaoka | |
| 氷川神社 | Hikawa Shrine | |
| 臨海病院 / 臨海公園 | Rinkai Hospital / Rinkai Park | |
| 中央公園 | Central Park | |
| 東亜TV | Toa TV | |
| 業魔殿 | Gouma-den | Victor's hotel. |
| 占いの館 | House of Fortune | Marie's shop, when named (often in quotes). Plain 占い屋 is `the fortune-teller's`. |
| 喫茶「アフロ」 | Cafe Afro | |
| 天堂組 / 組員 | Tendou-gumi / Tendou-gumi Member | Not "Tendou Group" or "Tendou family". |
| 天堂天山 | Tenzan Tendou | |
| 山城議員 | Councilman Yamashiro | |
| 「組織」 | the Organization | Capitalized when it means the villains' organization. |
| 擬似アストラル界 | Pseudo-Astral Plane | Different from the location 擬似異界 (Astral Plane). |
| 三途の川 | River Styx | Charon's river. |
| 無間地獄 | Avici Hell | |
| 関帝聖君 / 関帝廟 | Guan Yu / Guan Di Temple | |
| 大破壊 | Great Cataclysm | |
| 現世 / 現界 | the world of the living / the real world | |
| 妖気 | demonic energy | |
| 龍脈 | dragon veins | |
| 祠 | small shrine | 神社 is `shrine`. |
| 暴力団 | yakuza | |
| ゼミ | seminar | |
| パソコン通信 | BBS | 1995 dial-up networking. |
| （笑） | (laugh) | Not "lol". |
| クローバー・ジム | Clover Gym | |
| 探偵事務所 | detective agency; office | `office` in casual speech. |
| デビルサマナー / サマナー | Devil Summoner / summoner | Capitalized as a title, lowercase as a common noun. |
| COMP / コンプ / マイコン | COMP | |
| 仲魔 | ally; (to) join | `Join me.` for 仲魔になれ. Not "demon partner". |
| 悪魔 | demon | |
| 悪魔合体 / 合体 | fusion; fuse | |
| 剣合体 | sword fusion | |
| 造魔 | Zoma | |
| 異界 / 異界化 | Otherworld | `has become an Otherworld`. Not "Expanse". |
| 擬似異界 | Astral Plane | |
| 封印 | seal | |
| 魔法陣 | magic circle | |
| 神降ろし | Divine Descent | Rei's ritual. |
| マグネタイト / MAG | Magnetite / MAG | |
| 魂 | soul | |
| 霊 | spirit; ghost (幽霊) | `vengeful spirit` for 怨霊. |
| 地上げ | land grabbing | Not "land sharking". |
| チンピラ | punk | |
| ヤマ (slang) | job; case | |
| ヒーホー | Hee-ho | |
| ギャラ | fee | |

## Characters

- **Protagonist.** Silent. Others react to them being in Kyouji's body: people
  who knew Kyouji think it's him, so `Kyouji` in dialogue often means the
  protagonist.
- **Rei Reiho.** Blunt, casual and quick, with a protective streak she hides
  behind teasing. Contractions, short sentences, mild swearing about Marie.
  `あんた` is just `you`; don't make her sound posh or cutesy.
- **Kyouji** (after his soul ends up in Takashi's body). Terse and practical.
  Short, clipped sentences; no small talk.
- **Kumiko Hatano.** A university student: friendly, a little bossy and
  sensible. Natural, warm, modern for 1995.
- **Marie.** An old fortune-teller and broker of jobs. Breezy, sly and
  mercenary, with an affected sweetness (`ちょうだい`, `おくれよ`). `Come on,
  dear`, `be a love` territory, used sparingly.
- **Victor.** Formal, old-world and precise. No contractions.
- **Sid Davis.** His Japanese ends sentences with katakana syllables, an odd,
  foreign, theatrical cadence. Render it as overly formal, mannered English
  with a self-satisfied edge (`Heh heh heh.`). Don't spell out an accent.
- **Takashi** (before the swap). A street punk: rough, cocky, slangy.
- **Dr. Thrill.** Kansai dialect: excitable and blustering. Loud, folksy, quick;
  not a regional US accent.
- **Madame Ginko.** Polished and flirtatious.
- **Inspector Momochi.** Hostile and rough. `You piece of trash!`
- **Jack Frost / Jack-o'-Lantern.** Childish and cheeky, ending lines with
  `Hee-ho!` where the Japanese does. Jack-o'-Lantern talks as `we`.

## Negotiation personalities

Each personality file in `negotiation/` is one way of talking, shared by every
demon of that type. Keep each one recognizably different.

| File | Japanese style | English voice |
| --- | --- | --- |
| `archaic.json` | Samurai/period speech (`そなた`, `〜いたせ`). | Formal and old-fashioned: no contractions, `shall`, `thou` never. |
| `beast.json` | All katakana, stiff. | ALL CAPS, grammatical but stilted, slow and weighty. |
| `feral.json` | Katakana, broken grammar. | ALL CAPS, broken grammar: `YOU ARE BAD ONE.` Keep it simple, not comic. |
| `boy.json` | A young boy (`ボク`, `おじさん`). | Childish, petulant; calls the player `mister`. |
| `little_girl.json` | A little girl, drawn-out vowels. | Sing-song, childish, simple words. |
| `girl.json` | A teenage girl, trendy. | Bubbly and bratty: `You're the worst!` |
| `young_man.json` | A rough young man. | Casual and brash; calls the player `old man`. |
| `cynical.json` | Bored and sarcastic. | Dry, curt, dismissive. |
| `manic.json` | Unhinged laughter. | Wild swings, stretched laughs (`Keh heh heh`). |
| `lady.json` | A mature woman. | Calm, teasing, a little motherly. |
| `highborn_lady.json` | An aristocratic lady (`わたくし`, `ですわ`). | Haughty and prim; no contractions. |
| `nobleman.json` | A polite gentleman (`貴方`). | Courteous and measured. |
| `old_man.json` | An old man with regional speech (`じゃのゥ`). | Folksy, grandfatherly: `Ohh, ohh.` |
| `kansai.json` | Kansai dialect. | Brash, fast, informal (`ya`, `ain't`), without a specific US accent. |
| `slime.json` | Garbled, voiced consonants. | Stuttering and slurred: `L-love ya!` |

## Leave alone or flag

- **The 30 negotiation choices** the build reports as too wide are being
  reworded separately.
- **Equipment names** are kana in the original, and some are brand parodies.
  Don't invent a meaning; leave the current name and note it if unsure.
- **Text the Japanese leaves in English** (`LAW`, `CHAOS`, `DDS-NET`, test and
  error strings) stays as it is.
