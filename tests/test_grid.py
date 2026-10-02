from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cypherline.grid import BeatGrid  # noqa: E402


def test_from_bpm_produces_the_stated_tempo():
    g = BeatGrid.from_bpm(120, duration_sec=10)
    assert g.bpm == pytest.approx(120.0)
    assert g.mean_interval == pytest.approx(0.5)


def test_rejects_a_grid_too_short_to_have_an_interval():
    with pytest.raises(ValueError, match="at least two beats"):
        BeatGrid(beat_times=(1.0,))


def test_rejects_unsorted_beats():
    with pytest.raises(ValueError, match="sorted"):
        BeatGrid(beat_times=(0.0, 2.0, 1.0))


def test_handles_a_non_uniform_grid():
    """Real beat tracking returns slightly uneven beats; mean_interval averages."""
    g = BeatGrid(beat_times=(0.0, 0.51, 0.99, 1.52))
    assert g.mean_interval == pytest.approx(1.52 / 3)


def test_subdivision_inserts_positions_without_dropping_beats():
    g = BeatGrid.from_bpm(120, duration_sec=4)
    beats = g.positions(1)
    sixteenths = g.positions(4)
    assert beats == g.beat_times
    # every beat must still be present in the finer grid
    for b in beats:
        assert any(abs(b - s) < 1e-9 for s in sixteenths)
    assert len(sixteenths) == (len(beats) - 1) * 4 + 1


def test_nearest_reports_a_signed_error():
    g = BeatGrid.from_bpm(120, duration_sec=4)  # beats at 0.0, 0.5, ...
    _, late = g.nearest(0.52, subdivision=1)
    _, early = g.nearest(0.48, subdivision=1)
    assert late > 0, "an event after the beat is late"
    assert early < 0, "an event before the beat is early"


def test_nearest_clamps_outside_the_grid():
    g = BeatGrid.from_bpm(120, duration_sec=2)
    pos, err = g.nearest(-5.0, subdivision=1)
    assert pos == g.beat_times[0]
    assert err == pytest.approx(-5.0)
    pos, err = g.nearest(99.0, subdivision=1)
    assert pos == g.beat_times[-1]


def test_bar_numbering_counts_from_the_first_downbeat():
    g = BeatGrid.from_bpm(120, duration_sec=8, beats_per_bar=4)
    assert g.bar_of(0.0) == 0
    assert g.bar_of(1.9) == 0   # still inside bar 1 (4 beats = 2.0 s)
    assert g.bar_of(2.1) == 1
