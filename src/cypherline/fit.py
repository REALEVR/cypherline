"""Rhythm-fit scoring: does this take actually land in the pocket?

This is what the brief calls the real technical core, and the decision it has to
get right is not "is this on beat" but "is this *fixably* off beat".

A home recording is almost never aligned to the instrumental, and three
different things cause that. They are not equally forgivable:

  offset    The take is uniformly early or late — the contributor hit record a
            moment late. Fixed by shifting. Musically harmless.

  drift     The take's tempo differs slightly from the beat's, so error grows
            across the verse. Fixed by time-stretching, within limits. Also
            harmless.

  scatter   What remains once offset and drift are removed: the take's timing
            relative to itself. This is the only component that says whether the
            performer was in time, and the only one that cannot be fixed without
            mangling the audio.

The score therefore comes from scatter alone. A take uniformly 120 ms late is a
good take needing a shift; a take whose syllables scatter ±90 ms is not in the
pocket, and no processing makes it one. Conflating them is how a pipeline ends
up either rejecting good takes or force-quantising bad ones — both of which the
brief rules out.

WHY CIRCULAR STATISTICS
Timing error against a periodic grid is an angle, not a number. An onset 90% of
a step late is also 10% of a step early, and snapping each onset to its nearest
grid position throws that away: any offset past a half-step aliases to the next
position and the measurement collapses. Since offset and drift routinely exceed
a half-step, that failure mode covers most of the cases this module exists for.
So phase is handled on the circle, where wrapping is free, and the tightness of
a take is the *concentration* of its phases — which is offset-invariant by
construction, exactly the property we want.

Stdlib only, operating on plain lists of onset times, so the scoring logic is
testable without audio or a DSP stack. Getting those onset times out of real
audio is `extract.py`'s job and needs librosa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from statistics import median

from .grid import BeatGrid

#: Scatter below this fraction of a grid step is an unambiguously tight take.
TIGHT_SCATTER_PHASE = 0.10
#: Scatter above this fraction of a grid step cannot be rescued.
MAX_SCATTER_PHASE = 0.25
#: Time-stretch beyond this ratio is audible even without pitch shifting.
MAX_DRIFT_RATIO = 0.06
#: Below this many onsets, drift cannot be told from noise, so we do not claim
#: to have measured it.
MIN_ONSETS_FOR_DRIFT = 8
#: How far the drift search looks. Wider than MAX_DRIFT_RATIO on purpose: we
#: must be able to *measure* unrescuable drift in order to reject it.
DRIFT_SEARCH_RANGE = 0.25
#: Drift is a free parameter fitted to the data, so on a loose take some tempo
#: ratio always lines the noise up somewhat better by chance — measured at
#: +0.23..+0.33 concentration gain on pure noise, which a gain threshold alone
#: cannot separate from a real 2% drift's +0.96.
#:
#: What does separate them is the concentration REACHED: genuine drift resolves
#: to ~1.0, noise plateaus near 0.5. So a fitted drift is believed only if it
#: leaves the take genuinely tight. Otherwise the drift is discarded and scatter
#: becomes the diagnosis — which is the honest thing to tell a contributor, who
#: would otherwise go re-record against a metronome when the real problem is
#: their timing.


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    """Already in the pocket. Use as-is."""

    CORRECTABLE = "CORRECTABLE"
    """In time with itself; needs a shift and/or stretch to lock in."""

    REJECT = "REJECT"
    """Not in time with itself. Ask for another take — never force this one."""

    TOO_SHORT = "TOO_SHORT"
    """Not enough onsets to judge. Not a failure of the performance."""


@dataclass(frozen=True)
class FitAnalysis:
    onset_count: int
    grid_step: float
    """Seconds per grid position at the subdivision used."""

    offset_sec: float
    """The shift that best aligns the take, in [-step/2, +step/2).

    Only ever identifiable modulo one grid step: a take a full step late is
    indistinguishable from one on time that starts a step later. That ambiguity
    is real and musical, not a bug, so the *smallest* equivalent shift is
    reported. Positive means the take should move later.
    """

    drift_ratio: float
    """Fractional tempo mismatch; +0.02 means the take runs 2% slow. Fixed by
    time-stretching. 0.0 when there were too few onsets to measure it."""

    drift_measured: bool

    scatter_sec: float
    """Spread of timing error once offset and drift are removed."""

    scatter_phase: float
    """scatter_sec as a fraction of a grid step — the scale-free number."""

    concentration: float
    """Circular concentration of onset phases, 0..1. 1.0 is machine-tight."""

    score: float
    """0.0–1.0, derived from scatter alone."""

    verdict: Verdict
    reason: str

    @property
    def needs_correction(self) -> bool:
        return self.verdict is Verdict.CORRECTABLE


def _circular(phases: list[float]) -> tuple[float, float]:
    """Mean direction and concentration of phases given in turns [0, 1).

    Returns (mean_turn, R). R is the length of the mean unit vector: 1.0 when
    every phase coincides, ~0 when they are spread evenly round the circle.
    """
    s = sum(math.sin(2 * math.pi * p) for p in phases)
    c = sum(math.cos(2 * math.pi * p) for p in phases)
    n = len(phases)
    r = math.hypot(s, c) / n
    mean = (math.atan2(s, c) / (2 * math.pi)) % 1.0
    return mean, r


#: Ceiling on reported scatter, in turns. Circular SD diverges as concentration
#: goes to zero, so it needs a cap — but the cap MUST sit above
#: MAX_SCATTER_PHASE, or a maximally scattered take clamps exactly onto the
#: reject threshold and compares as "not greater than" it, i.e. never rejects.
#: Half a step is the largest error that means anything: beyond that an onset is
#: simply nearer the next grid position.
MAX_REPORTED_SCATTER_TURNS = 0.5


def _scatter_turns(r: float) -> float:
    """Circular standard deviation, in turns, from concentration R."""
    if r >= 1.0:
        return 0.0
    if r <= 1e-9:
        return MAX_REPORTED_SCATTER_TURNS
    return min(MAX_REPORTED_SCATTER_TURNS, math.sqrt(-2.0 * math.log(r)) / (2 * math.pi))


def _phases(onsets: list[float], origin: float, step: float, drift: float) -> list[float]:
    """Onset phases in turns, after undoing a candidate drift."""
    t0 = onsets[0]
    return [
        (((t0 + (t - t0) / (1.0 + drift)) - origin) / step) % 1.0
        for t in onsets
    ]


def _best_drift(onsets: list[float], origin: float, step: float) -> tuple[float, float]:
    """Drift ratio maximising phase concentration, plus that concentration.

    Coarse sweep then a local refine. The correct tempo ratio is the one at
    which the onsets stop smearing round the circle, so concentration is the
    objective — the same quantity the score is built from.
    """
    def concentration(d: float) -> float:
        return _circular(_phases(onsets, origin, step, d))[1]

    best_d, best_r = 0.0, concentration(0.0)
    steps = 200
    for i in range(steps + 1):
        d = -DRIFT_SEARCH_RANGE + (2 * DRIFT_SEARCH_RANGE) * i / steps
        r = concentration(d)
        if r > best_r:
            best_d, best_r = d, r

    span = (2 * DRIFT_SEARCH_RANGE) / steps
    for _ in range(4):  # refine ~4 orders of magnitude finer
        span /= 8
        for i in range(-8, 9):
            d = best_d + span * i / 8
            r = concentration(d)
            if r > best_r:
                best_d, best_r = d, r
    return best_d, best_r


def score_take(
    onsets: list[float] | tuple[float, ...],
    grid: BeatGrid,
    *,
    subdivision: int = 4,
) -> FitAnalysis:
    """Measure how well `onsets` sit on `grid`.

    `subdivision` defaults to sixteenth notes because that is the resolution rap
    phrasing occupies. Scoring against quarter notes alone would read ordinary
    syncopation as bad timing.

    Phase is computed against a uniform grid of `grid.mean_interval /
    subdivision`. For a quantised, machine-generated instrumental — which the
    shared Suno beat is — that is exact. For a hand-played backing track whose
    tempo genuinely wanders, it is an approximation, and the drift term absorbs
    only the linear part of that wander.
    """
    onsets = sorted(float(o) for o in onsets)
    step = grid.mean_interval / subdivision
    origin = grid.beat_times[0]

    if len(onsets) < 2:
        return FitAnalysis(
            onset_count=len(onsets), grid_step=step, offset_sec=0.0,
            drift_ratio=0.0, drift_measured=False, scatter_sec=0.0,
            scatter_phase=0.0, concentration=0.0, score=0.0,
            verdict=Verdict.TOO_SHORT,
            reason="Need at least two onsets to measure timing.",
        )

    _, r_at_zero = _circular(_phases(onsets, origin, step, 0.0))
    drift_measured = len(onsets) >= MIN_ONSETS_FOR_DRIFT

    if drift_measured:
        drift, r = _best_drift(onsets, origin, step)
        # Believe it only if the corrected take is actually tight; see above.
        if _scatter_turns(r) > TIGHT_SCATTER_PHASE:
            drift, r = 0.0, r_at_zero
    else:
        drift, r = 0.0, r_at_zero

    mean_turn, _ = _circular(_phases(onsets, origin, step, drift))
    # Wrap to the smallest equivalent shift, and negate: a phase of +0.2 turns
    # means the take sits 0.2 of a step LATE, so it must move earlier.
    wrapped = mean_turn if mean_turn <= 0.5 else mean_turn - 1.0
    offset_sec = -wrapped * step

    scatter_phase = _scatter_turns(r)
    scatter_sec = scatter_phase * step
    score = max(0.0, min(1.0, 1.0 - scatter_phase / MAX_SCATTER_PHASE))
    verdict, reason = _judge(scatter_phase, drift, drift_measured)

    return FitAnalysis(
        onset_count=len(onsets),
        grid_step=step,
        offset_sec=offset_sec,
        drift_ratio=drift,
        drift_measured=drift_measured,
        scatter_sec=scatter_sec,
        scatter_phase=scatter_phase,
        concentration=r,
        score=score,
        verdict=verdict,
        reason=reason,
    )


def _judge(scatter_phase: float, drift: float, drift_measured: bool) -> tuple[Verdict, str]:
    if scatter_phase > MAX_SCATTER_PHASE:
        return (
            Verdict.REJECT,
            f"Timing scatters {scatter_phase:.0%} of a grid step even after "
            f"correcting lead/lag and tempo — the take is not in time with "
            f"itself, so shifting or stretching would not help.",
        )

    if drift_measured and abs(drift) > MAX_DRIFT_RATIO:
        return (
            Verdict.REJECT,
            f"Take runs {abs(drift):.1%} {'slow' if drift > 0 else 'fast'} "
            f"against the beat. Correcting that needs more time-stretching than "
            f"stays inaudible.",
        )

    if scatter_phase <= TIGHT_SCATTER_PHASE:
        return Verdict.ACCEPT, "In the pocket."

    return (
        Verdict.CORRECTABLE,
        f"In time with itself (scatter {scatter_phase:.0%} of a grid step) but "
        f"needs aligning to the beat.",
    )
