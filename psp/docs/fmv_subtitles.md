# START2 runtime subtitles

The PSP port presents the nine English START2 news cues without transcoding or
replacing the movie. `assets/text/fmv/subtitles.json` is the sole authored text
and timing source; `psp/fmv/config/start2_news.json` owns the PSP-specific PSMF,
timing, and placement contract.

## Source and timing contract

The compiler validates
`PSP_GAME/USRDIR/MOVIE/START2_320x224.pmf` at byte offset `257064960`:

- size `4511744` and SHA-256
  `6dc543ac681b3fc8def88b23d00415306720454e82438e3f73cf485ed9eccb90`;
- `PSMF0014`, a 2,048-byte header, and a 4,509,696-byte stream;
- a 320x224 presentation from tick 90,000 through 3,093,000; and
- exactly 1,000 video packets at `30000/1001` frames per second.

Centisecond cue boundaries are rounded upward to half-open decoded-frame
intervals. The nine resulting spans are `27..78`, `92..158`, `158..225`,
`225..329`, `350..504`, `504..609`, `622..724`, `724..828`, and `828..997`.

## Font and runtime contract

The font stage renders the 31 visible subtitle characters into the blank member
15 cells `0x0672..0x0690`; space remains advance-only code zero. CONFIG extends
the same page, so its larger `0x069d` draw limit also covers START2. The final
composed datapack remains byte-identical to the original project's checked
output.

The FMV stage measures and centers each line in the authored 320x224 canvas,
applies the eight-pixel difference between the movie and stock glyph origins,
and emits 437 visible placements. The engine stage serializes them into an
1,824-byte cue table at `0x0013f000`. A 360-byte position-independent wrapper
at `0x0013ee10` replaces ten proved movie-update JALs, calls the stock updater,
filters on the exact START2 basename pointer, and draws a black one-pixel shadow
followed by a white face through the stock FONT16 sprite routine.

Every JAL preimage, delay slot, R_MIPS_26 relocation record, and code-cave byte
is checked against the pinned BOOT binary. Structural tests reproduce the
original wrapper hash
`1437fac03c4f9fd27df40e3e0dfb290e34382bcd147f0b8a98963691bbd6c291`
and the real cue-table hash
`7be070a9e97f34d800429bf04a1032df6e4cc49efffbc4b9ca80f349ab307c6d`.

Runtime acceptance still requires replaying all nine cues in PPSSPP, checking
centering and shadow readability, confirming non-START2 movies remain stock,
and testing movie skip/cleanup paths.
