"""The beat grid: where the rhythm actually is.

A grid is a sorted list of beat times in seconds, plus how those beats group
into bars. Beat times are stored explicitly rather than derived from a single
BPM, because a real track's tempo is never perfectly constant and the whole
point of this module is measuring small timing differences.

`from_bpm` exists for tests and for the one case where tempo genuinely is
constant (a quantised, machine-generated instrumental — which a Suno track
usually is).
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class BeatGrid:
    """Beat positions of one instrumental."""

    beat_times: tuple[float, ...]
    beats_per_bar: int = 4
    #: Index into beat_times of the first downbeat (beat 1 of a bar).
    downbeat_index: int = 0

    def __post_init__(self) -> None:
        if len(self.beat_times) < 2:
            raise ValueError("A grid needs at least two beats to have an interval.")
        if list(self.beat_times) != sorted(self.beat_times):
            raise ValueError("beat_times must be sorted ascending.")
        if self.beats_per_bar < 1:
            raise ValueError("beats_per_bar must be at least 1.")
        if not 0 <= self.downbeat_index < len(self.beat_times):
            raise ValueError("downbeat_index is outside beat_times.")

    @classmethod
    def from_bpm(
        cls,
        bpm: float,
        *,
        duration_sec: float,
        first_beat_sec: float = 0.0,
        beats_per_bar: int = 4,
    ) -> BeatGrid:
        """A perfectly constant grid. Convenient, but real audio drifts."""
        if bpm <= 0:
            raise ValueError("bpm must be positive.")
        interval = 60.0 / bpm
        n = int((duration_sec - first_beat_sec) / interval) + 1
        if n < 2:
            raise ValueError("duration_sec is too short for two beats at this bpm.")
        return cls(
            beat_times=tuple(first_beat_sec + i * interval for i in range(n)),
            beats_per_bar=beats_per_bar,
        )

    @property
    def mean_interval(self) -> float:
        """Average seconds per beat across the whole grid."""
        return (self.beat_times[-1] - self.beat_times[0]) / (len(self.beat_times) - 1)

    @property
    def bpm(self) -> float:
        return 60.0 / self.mean_interval

    @property
    def duration(self) -> float:
        return self.beat_times[-1] - self.beat_times[0]

    def positions(self, subdivision: int = 4) -> tuple[float, ...]:
        """Grid times at a finer resolution than the beat.

        subdivision=1 gives the beats themselves; 4 gives sixteenth notes in
        4/4. The default is 4 on purpose: rap phrasing sits on sixteenths, and
        scoring a verse against quarter notes alone would flag ordinary
        syncopation as sloppy timing. See `fit.score_take`.
        """
        if subdivision < 1:
            raise ValueError("subdivision must be at least 1.")
        if subdivision == 1:
            return self.beat_times

        out: list[float] = []
        for i, t in enumerate(self.beat_times[:-1]):
            step = (self.beat_times[i + 1] - t) / subdivision
            out.extend(t + k * step for k in range(subdivision))
        out.append(self.beat_times[-1])
        return tuple(out)

    def nearest(self, t: float, *, subdivision: int = 4) -> tuple[float, float]:
        """The closest grid position to `t`, and the signed error `t - position`.

        A positive error means the event is late.
        """
        grid = self.positions(subdivision)
        i = bisect_left(grid, t)
        if i == 0:
            return grid[0], t - grid[0]
        if i == len(grid):
            return grid[-1], t - grid[-1]
        before, after = grid[i - 1], grid[i]
        if abs(t - before) <= abs(after - t):
            return before, t - before
        return after, t - after

    def bar_of(self, t: float) -> int:
        """Which bar `t` falls in, counting from 0 at the first downbeat.

        Uses the beat at or *before* `t`: an event 0.4 of a beat before the next
        downbeat still belongs to the bar it is currently in, not the next one.
        Times before the first downbeat clamp to bar 0.
        """
        beat = bisect_right(self.beat_times, t) - 1
        if beat < self.downbeat_index:
            return 0
        return (beat - self.downbeat_index) // self.beats_per_bar
