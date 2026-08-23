# PSP FMV subtitles

This package converts the canonical START2 timed-text asset into PSP runtime
placements. It does not decode, transcode, or replace the PMF.

`config/start2_news.json` owns the physical PSMF, timing, and screen-placement
contract. `util/subtitles.py` validates the nine canonical cues, the generated
FONT16 mapping, and the exact unchanged PMF before compiling half-open frame
spans and centered glyph coordinates. `build.py` publishes those placements and
their provenance under the ignored `generated/game/` directory for the engine
stage.

```powershell
python -B psp/fmv/build.py all
python -B psp/fmv/build.py all --check
python -m unittest discover -s psp/fmv/tests -v
```

See [`../docs/fmv_subtitles.md`](../docs/fmv_subtitles.md) for the binary and
runtime acceptance contracts.
