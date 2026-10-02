"""The claim this module makes is falsifiable, so these tests try to falsify it.

Central behaviour: a take that is uniformly off the beat is a GOOD take needing
alignment, and a take whose timing scatters is a BAD take that must be rejected.
If those two ever score alike, the pipeline is worthless.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cypherline.fit import (  # noqa: E402
    MAX_DRIFT_RATIO,
    FitAnalysis,
    Verdict,
    score_take,
)
from cypherline.grid import BeatGrid  # noqa: E402

BPM = 90.0
GRID = BeatGrid.from_bpm(BPM, duration_sec=32.0)
SIXTEENTH = (60.0 / BPM) / 4  # ~166.7 ms


def on_grid(count: int, *, every: int = 2, start: int = 0) -> list[float]:
    """Onsets sitting exactly on grid positions — a machine-tight take."""
    pos = GRID.positions(4)
    return [pos[start + i * every] for i in range(count)]


def alignment_error(onsets: list[float], analysis: FitAnalysis) -> float:
    """Worst remaining distance to a grid position after applying the correction.

    This is what the analysis is *for*: if applying the reported offset and drift
    does not actually land the take on the grid, the numbers are decoration.
    """
    t0 = onsets[0]
    worst = 0.0
    for t in onsets:
        undrifted = t0 + (t - t0) / (1.0 + analysis.drift_ratio)
        corrected = undrifted + analysis.offset_sec
        _, err = GRID.nearest(corrected, subdivision=4)
        worst = max(worst, abs(err))
    return worst


def test_perfect_take_is_accepted():
    a = score_take(on_grid(24), GRID)
    assert a.verdict is Verdict.ACCEPT
    assert a.score == pytest.approx(1.0)
    assert a.concentration == pytest.approx(1.0, abs=1e-6)


def test_uniformly_late_take_is_not_penalised():
    """The whole point: constant lag is a recording artefact, not bad timing."""
    lag = 0.120  # 120 ms — past the 83 ms half-step, so it aliases naively
    onsets = [t + lag for t in on_grid(24)]
    a = score_take(onsets, GRID)

    assert a.verdict in (Verdict.ACCEPT, Verdict.CORRECTABLE)
    assert a.score > 0.9, "a uniformly late take must still score highly"
    assert a.scatter_sec == pytest.approx(0.0, abs=0.005), "lag is not scatter"
    assert alignment_error(onsets, a) < 0.002, "the reported shift must align it"


def test_offset_is_reported_as_the_smallest_equivalent_shift():
    """Offset is only knowable modulo a grid step; report the smaller one."""
    onsets = [t + 0.120 for t in on_grid(24)]
    a = score_take(onsets, GRID)
    assert abs(a.offset_sec) <= SIXTEENTH / 2 + 1e-9


def test_scattered_take_is_rejected():
    rng = random.Random(7)
    scatter = SIXTEENTH * 0.5
    onsets = [t + rng.uniform(-scatter, scatter) for t in on_grid(24)]
    a = score_take(onsets, GRID)

    assert a.verdict is Verdict.REJECT
    assert a.score < 0.5
    assert "not in time with itself" in a.reason


def test_late_and_scattered_are_scored_differently():
    """The two must never collapse into the same verdict."""
    rng = random.Random(11)
    base = on_grid(24)
    late = score_take([t + 0.120 for t in base], GRID)
    sloppy = score_take(
        [t + rng.uniform(-SIXTEENTH * 0.5, SIXTEENTH * 0.5) for t in base], GRID
    )
    assert late.score > sloppy.score + 0.4
    assert late.verdict is not Verdict.REJECT
    assert sloppy.verdict is Verdict.REJECT


def test_small_tempo_drift_is_measured_and_survivable():
    drift = 0.02  # runs 2% slow; accumulates well past a half-step over 32 s
    base = on_grid(24)
    t0 = base[0]
    onsets = [t0 + (t - t0) * (1.0 + drift) for t in base]
    a = score_take(onsets, GRID)

    assert a.drift_measured
    assert a.drift_ratio == pytest.approx(drift, abs=0.005)
    assert a.verdict is not Verdict.REJECT
    assert a.scatter_sec == pytest.approx(0.0, abs=0.005), (
        "drift must be removed before measuring scatter, not counted as it"
    )
    assert alignment_error(onsets, a) < 0.005


def test_excessive_drift_is_rejected():
    drift = MAX_DRIFT_RATIO * 2.5
    base = on_grid(24)
    t0 = base[0]
    onsets = [t0 + (t - t0) * (1.0 + drift) for t in base]
    a = score_take(onsets, GRID)

    assert a.verdict is Verdict.REJECT
    assert "time-stretching" in a.reason


def test_drift_is_not_claimed_from_too_few_onsets():
    a = score_take(on_grid(4), GRID)
    assert a.drift_measured is False
    assert a.drift_ratio == 0.0


def test_one_onset_is_not_a_performance_failure():
    a = score_take([0.0], GRID)
    assert a.verdict is Verdict.TOO_SHORT
    assert "two onsets" in a.reason


def test_syncopation_is_not_mistaken_for_bad_timing():
    """Rap sits on sixteenths. Scoring against quarter notes would flag this."""
    pos = GRID.positions(4)
    offbeats = [pos[i] for i in range(1, 80, 2)]  # offbeat eighths only

    fine = score_take(offbeats, GRID, subdivision=4)
    coarse = score_take(offbeats, GRID, subdivision=1)

    assert fine.verdict is Verdict.ACCEPT, "offbeat placement is musically fine"
    assert coarse.score < fine.score, (
        "quarter-note scoring looks worse — which is why subdivision defaults to 4"
    )


def test_outlier_onset_does_not_condemn_a_tight_take():
    onsets = on_grid(24)
    onsets[10] += SIXTEENTH * 0.8  # one fluffed syllable
    a = score_take(onsets, GRID)
    assert a.verdict is not Verdict.REJECT


def test_concentration_is_offset_invariant():
    """Tightness must not depend on where the take sits relative to the beat."""
    base = on_grid(24)
    tight = score_take(base, GRID).concentration
    for shift in (0.03, 0.08, 0.120, 0.150):
        assert score_take([t + shift for t in base], GRID).concentration == pytest.approx(
            tight, abs=1e-6
        ), f"shifting by {shift}s changed measured tightness"


def test_analysis_is_immutable():
    a = score_take(on_grid(12), GRID)
    with pytest.raises(Exception):
        a.score = 0.0  # type: ignore[misc]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_onsets_raise_instead_of_scoring_as_a_reject(bad):
    """A broken extractor must not read as a bad performance."""
    grid = BeatGrid.from_bpm(90.0, duration_sec=32.0)
    with pytest.raises(ValueError, match="finite"):
        score_take([0.1, bad, 0.5, 0.9], grid)
