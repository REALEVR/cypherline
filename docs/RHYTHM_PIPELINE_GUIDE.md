# Rhythm-Matching Pipeline Guide

Companion to [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md). The brief says *what* the pipeline must do; this guide walks through *how a single take moves through it* and gives a worked example of fit scoring so implementers and reviewers share the same mental model.

> Status: design documentation. Thresholds below are illustrative starting points to be tuned against real recordings, not validated constants.

## Stages at a glance

```
Beat audio ──► 1. Beat grid ──────────────┐
                                          ├─► 3. Fit score ─► accept / retry
Take audio ──► 2. Onset detection ────────┘                       │
                                                                  ▼
                                                  4. Time-align (only if score is in the correctable band)
```

| Stage | Input | Output | Typical tooling |
|---|---|---|---|
| 1. Beat grid | Suno instrumental | `bpm`, `downbeats[]` (sec), `barBoundaries[]` | `librosa.beat`, `essentia` RhythmExtractor |
| 2. Onset detection | Vocal take | `onsets[]` (sec), `startOffset` | `librosa.onset`, energy/spectral-flux peaks |
| 3. Fit score | Grid + onsets | `rhythmFitScore` in `[0, 1]`, `medianOffsetMs`, `driftMsPerBar` | Custom (see below) |
| 4. Time-align | Take + score details | Stretched take | Phase-vocoder / WSOLA time-stretch (never pitch-shift) |

## Stage 1 — Beat grid

Run once per beat and cache the result on the `Beat` record (`bpm`, `beatGrid`). Sanity-check the output before trusting it:

- Tempo estimators commonly return half or double the true tempo. Compare against the tempo Suno reports for the track, if available, and prefer the octave that matches.
- Confirm downbeats land on a regular spacing (`60 / bpm * beatsPerBar`). A grid with irregular bar lengths should fail publication of the beat rather than silently propagate.

## Stage 2 — Take onsets

Vocals are not percussive, so onset detection is noisier than on drums. Practical notes:

- Trim leading silence and record `startOffset`; a take that starts late is a common, correctable issue.
- Ignore onsets closer together than ~60 ms; they are usually consonant bursts within one syllable.
- Keep the raw onset list; the scoring stage decides which onsets matter.

## Stage 3 — Fit score

The brief asks for a "does this flow" score, not just "is this on the beat". Use two components:

1. **Grid alignment** — for each onset, distance to the nearest grid subdivision (e.g. 16th notes). Report the median absolute offset.
2. **Drift** — fit a line to signed offsets over time. The slope is `driftMsPerBar`; a steady lean early or late is correctable, wandering is not.

### Worked example

Beat at 90 BPM → one beat = 666.7 ms, one 16th note = 166.7 ms. A take yields these signed offsets (ms, negative = early) against the nearest 16th-note position:

```
+12, -8, +15, +4, -20, +9, +31, +6
```

- Median absolute offset = 11 ms
- Slope ≈ small and not consistently signed → no meaningful drift

Suggested mapping (illustrative):

```
gridScore  = clamp(1 - medianAbsOffsetMs / 80, 0, 1)   # 80 ms ≈ clearly off-grid
driftScore = clamp(1 - |driftMsPerBar| / 40, 0, 1)
rhythmFitScore = 0.7 * gridScore + 0.3 * driftScore
```

For the example: `gridScore = 1 - 11/80 = 0.86`, `driftScore ≈ 1.0`, so `rhythmFitScore ≈ 0.90` — in the pocket.

### Decision bands

| Score | Meaning | Action |
|---|---|---|
| ≥ 0.85 | In the pocket | Accept as-is |
| 0.60 – 0.85 | Correctable | Time-align (stage 4), then rescore |
| < 0.60 | Rhythmically incompatible | Reject; ask the contributor to retry |

The brief's rule stands: **reject, don't force.** Stage 4 must never be used to rescue a take in the reject band.

## Stage 4 — Time alignment

- Apply a constant shift for `startOffset`, then a slow tempo-map stretch for drift.
- Stretch ratios beyond roughly ±5% tend to introduce audible artifacts; if correction needs more, treat the take as rejected.
- Always **rescore after alignment** and store both scores so reviewers can see the before/after.

## What to log per submission

Store enough to debug a disputed rejection: `rhythmFitScore`, `medianOffsetMs`, `driftMsPerBar`, whether alignment was applied, and the stretch ratio. This maps onto the `Submission` entity in the brief.

## Open questions

- Should the score weight phrase-level alignment (bar starts) more than syllable-level?
- How should rap that is intentionally off-grid (swung, triplet, behind-the-beat) be treated? The grid subdivision set may need to include triplets.
- Threshold tuning needs a small labeled set of real takes (accepted / correctable / rejected) before any numbers here are trusted.
