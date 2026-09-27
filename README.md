# Cypherline

One AI-generated beat. Many voices, recorded separately, each taking a verse. Cypherline aligns every take to the rhythm and compiles them into one continuous 3–4 minute track — a crowdsourced cypher built on a shared instrumental.

Full project brief: [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).

## Status

The rhythm-matching pipeline exists: beat-grid detection, rhythm-fit scoring, and correction planning, with 29 tests. That is the brief's stated first build target — "the part the rest of the product depends on actually working".

Not built: the product around it. No beat publishing, no slot management, no submission storage, no compilation. **Nothing here accepts a real contributor's recording**, which is deliberate — the brief names two things that must be settled first, and both are still open:

- **Suno's terms.** Whether a Suno-generated instrumental can legally be redistributed and recorded over as the backbone of a product depends on their current ToS and the plan that generated it. Needs a real read, not an assumption.
- **Contributor consent and ownership.** Every contributor submits a recording of their own voice into a compiled work others will hear. Explicit consent, and a clear answer to who owns the compiled track, are needed before the first real submission.

Scoring timing is unaffected by either, which is why it was safe to build first.

## What the scoring actually decides

Not "is this on beat" but **"is this *fixably* off beat"** — which is the distinction the whole thing turns on. Three separable causes, and they are not equally forgivable:

| Cause | Meaning | Fix |
|---|---|---|
| **offset** | The take is uniformly early or late — they hit record a moment late | Shift. Lossless. |
| **drift** | The take's tempo differs from the beat's, so error grows across the verse | Time-stretch, bounded |
| **scatter** | What remains once offset and drift are removed — the take's timing against itself | **None** |

The score comes from **scatter alone**. A take uniformly 120 ms late is a good take needing a shift; a take whose syllables scatter ±90 ms is not in the pocket, and no processing makes it one. Conflating them is how a pipeline ends up either rejecting good takes or force-quantising bad ones — both of which the brief rules out.

"Reject, don't force" is a type, not a guideline: `plan_correction` raises `TakeRejected` for a take that is not in time with itself, so a caller cannot accidentally render one.

## Two things worth knowing about the implementation

**Timing error is an angle, not a number.** An onset 90% of a step late is also 10% early. Snapping each onset to its nearest grid position throws that away, and any offset past a half-step aliases to the next position — which breaks precisely the cases this module exists for, since offset and drift routinely exceed a half-step. So phase is handled with circular statistics, where wrapping is free and a take's tightness is the *concentration* of its phases — offset-invariant by construction.

**Scoring defaults to sixteenth notes.** Rap phrasing sits on sixteenths; scoring a verse against quarter notes alone reads ordinary syncopation as bad timing.

A fitted drift is believed only when it leaves the take genuinely tight. Drift is a free parameter, so on a loose take some tempo ratio always lines the noise up better by chance — measured at +0.23–0.33 concentration gain on pure noise, against a real 2% drift's +0.96. A gain threshold cannot separate those; the concentration *reached* can. Without that guard a scattered take gets diagnosed as a tempo problem, and the contributor goes off to re-record against a metronome when the real problem is their timing.

## Install

```bash
pip install -e '.[dev]'          # scoring + tests, no DSP stack needed
pip install -e '.[dev,audio]'    # adds librosa/soundfile for audio extraction
```

The grid, fit and align modules are **stdlib-only**. Only `cypherline.extract` needs librosa, which keeps the scoring logic — the part with the actual product judgement in it — testable without audio fixtures. CI installs without the `[audio]` extra on purpose, to keep that true.

## Use

```python
from cypherline import BeatGrid, Verdict, plan_correction, score_take

grid = BeatGrid.from_bpm(90, duration_sec=200)     # or grid_from_audio(path)
analysis = score_take(onset_times, grid)           # or onsets_from_audio(path)

if analysis.verdict is Verdict.REJECT:
    send_back(analysis.reason)                     # never force the take
else:
    plan = plan_correction(analysis)
    render(take, shift=plan.shift_sec, stretch=plan.stretch_ratio)
```

`plan.stretch_ratio` must be applied with a **time-stretch** algorithm (phase vocoder / WSOLA), not by changing playback rate — the latter transposes the voice.

## Tests

```bash
python -m pytest -q
```

They exist to falsify the central claim, not to confirm it: `test_late_and_scattered_are_scored_differently` fails if a uniformly-late take and a sloppy one ever collapse into the same verdict, and `test_concentration_is_offset_invariant` fails if measured tightness depends on where the take sits relative to the beat.
