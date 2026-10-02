"""Turning a fit analysis into a correction — or refusing to.

`fit.py` measures. This decides what to do about it, and the important part is
what it will not do: a take the analysis rejected gets no plan at all. The brief
is explicit that a rhythmically incompatible take is rejected or sent back, never
"algorithmically mangled into fitting", so refusal is a first-class outcome here
rather than a clamp on some correction factor.

Two corrections exist, and both are safe because neither touches pitch:

  shift    Move the whole take earlier or later. Lossless.
  stretch  Resample the take's duration to match the beat's tempo. This must be
           done with a time-stretch algorithm (phase vocoder / WSOLA), NOT by
           changing playback rate, which would transpose the voice. Bounded by
           fit.MAX_DRIFT_RATIO so the artefacts stay inaudible.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fit import FitAnalysis, Verdict


@dataclass(frozen=True)
class CorrectionPlan:
    """What to do to a take to lock it to the grid."""

    shift_sec: float
    """Move the take this many seconds later (negative = earlier)."""

    stretch_ratio: float
    """Multiply the take's duration by this. 1.0 means leave it alone."""

    @property
    def is_noop(self) -> bool:
        return abs(self.shift_sec) < 1e-4 and abs(self.stretch_ratio - 1.0) < 1e-6

    def apply_to(self, times: list[float] | tuple[float, ...]) -> list[float]:
        """Apply this plan to a list of event times.

        Used to verify a plan without touching audio — the same arithmetic a
        renderer performs on samples. Anchored on the first event so the plan is
        independent of where the take sits in absolute time.
        """
        times = sorted(float(t) for t in times)
        if not times:
            return []
        t0 = times[0]
        return [t0 + (t - t0) * self.stretch_ratio + self.shift_sec for t in times]


class TakeRejected(Exception):
    """Raised when asked to plan a correction for a take that must be re-recorded."""

    def __init__(self, analysis: FitAnalysis) -> None:
        super().__init__(analysis.reason)
        self.analysis = analysis


def plan_correction(analysis: FitAnalysis) -> CorrectionPlan:
    """The correction that locks this take to the grid.

    Raises TakeRejected for a take that is not in time with itself. That is the
    brief's "reject, don't force" rule expressed as a type: a caller cannot
    accidentally render an unusable take, because there is no plan to render.
    """
    if analysis.verdict is Verdict.REJECT:
        raise TakeRejected(analysis)
    if analysis.verdict is Verdict.TOO_SHORT:
        raise TakeRejected(analysis)

    # The take runs at (1 + drift) times the grid's tempo, so undo that.
    stretch = 1.0 / (1.0 + analysis.drift_ratio) if analysis.drift_ratio else 1.0
    return CorrectionPlan(shift_sec=analysis.offset_sec, stretch_ratio=stretch)
