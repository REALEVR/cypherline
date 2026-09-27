"""Cypherline — one AI-generated beat, many voices, aligned to the rhythm.

The rhythm-matching pipeline the project brief names as the first build target:

    from cypherline import BeatGrid, score_take, plan_correction

    grid = BeatGrid.from_bpm(90, duration_sec=200)
    analysis = score_take(onset_times, grid)
    if analysis.verdict is Verdict.REJECT:
        ...            # ask for another take; never force this one
    plan = plan_correction(analysis)

Audio extraction lives in `cypherline.extract` and needs the `[audio]` extra.
Everything else is stdlib-only.
"""

from .align import CorrectionPlan, TakeRejected, plan_correction
from .fit import FitAnalysis, Verdict, score_take
from .grid import BeatGrid

__all__ = [
    "BeatGrid",
    "CorrectionPlan",
    "FitAnalysis",
    "TakeRejected",
    "Verdict",
    "plan_correction",
    "score_take",
]
__version__ = "0.1.0"
