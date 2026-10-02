"""Correction planning, and the refusal that matters more than the planning."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cypherline.align import CorrectionPlan, TakeRejected, plan_correction  # noqa: E402
from cypherline.fit import Verdict, score_take  # noqa: E402
from cypherline.grid import BeatGrid  # noqa: E402

BPM = 90.0
GRID = BeatGrid.from_bpm(BPM, duration_sec=32.0)
SIXTEENTH = (60.0 / BPM) / 4


def on_grid(count: int) -> list[float]:
    pos = GRID.positions(4)
    return [pos[i * 2] for i in range(count)]


def worst_grid_error(times: list[float]) -> float:
    return max(abs(GRID.nearest(t, subdivision=4)[1]) for t in times)


def test_a_rejected_take_gets_no_plan():
    """"Reject, don't force" as a type: there is nothing to render."""
    rng = random.Random(7)
    onsets = [t + rng.uniform(-SIXTEENTH * 0.5, SIXTEENTH * 0.5) for t in on_grid(24)]
    analysis = score_take(onsets, GRID)
    assert analysis.verdict is Verdict.REJECT

    with pytest.raises(TakeRejected) as exc:
        plan_correction(analysis)
    assert exc.value.analysis is analysis
    assert "not in time with itself" in str(exc.value)


def test_a_too_short_take_gets_no_plan_either():
    with pytest.raises(TakeRejected):
        plan_correction(score_take([0.0], GRID))


def test_plan_for_a_perfect_take_is_a_noop():
    plan = plan_correction(score_take(on_grid(24), GRID))
    assert plan.is_noop


def test_plan_actually_aligns_a_late_take():
    onsets = [t + 0.120 for t in on_grid(24)]
    plan = plan_correction(score_take(onsets, GRID))
    assert worst_grid_error(plan.apply_to(onsets)) < 0.002


def test_plan_actually_aligns_a_drifting_take():
    drift = 0.02
    base = on_grid(24)
    t0 = base[0]
    onsets = [t0 + (t - t0) * (1.0 + drift) for t in base]

    analysis = score_take(onsets, GRID)
    plan = plan_correction(analysis)

    assert plan.stretch_ratio == pytest.approx(1.0 / (1.0 + drift), abs=0.01)
    assert worst_grid_error(plan.apply_to(onsets)) < 0.01


def test_plan_handles_both_offset_and_drift_together():
    drift = 0.015
    base = on_grid(24)
    t0 = base[0]
    onsets = [t0 + (t - t0) * (1.0 + drift) + 0.090 for t in base]

    plan = plan_correction(score_take(onsets, GRID))
    assert worst_grid_error(plan.apply_to(onsets)) < 0.01


def test_apply_to_is_anchored_on_the_first_event():
    """A plan must not depend on where the take sits in absolute time."""
    plan = CorrectionPlan(shift_sec=0.05, stretch_ratio=1.01)
    a = plan.apply_to([10.0, 11.0, 12.0])
    b = plan.apply_to([100.0, 101.0, 102.0])
    assert [x - a[0] for x in a] == pytest.approx([x - b[0] for x in b])


def test_apply_to_handles_an_empty_take():
    assert CorrectionPlan(shift_sec=1.0, stretch_ratio=1.0).apply_to([]) == []
