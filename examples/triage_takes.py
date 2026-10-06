"""Triage three synthetic takes against a 90 BPM grid, stdlib only.

Run from the repo root:  python examples/triage_takes.py

Shows the three outcomes the scorer distinguishes: a take that is merely late
(fixable by a shift), a take that runs slow (fixable by a stretch), and a take
that scatters against itself (rejected, never forced).
"""

import random

from cypherline import BeatGrid, TakeRejected, plan_correction, score_take

BPM = 90
SIXTEENTH = 60 / BPM / 4
ONSETS = 32


def take(offset: float = 0.0, drift: float = 0.0, jitter: float = 0.0, seed: int = 7) -> list[float]:
    """Sixteenth-note onsets with a uniform offset, tempo drift and random jitter."""
    rng = random.Random(seed)
    return [
        i * SIXTEENTH * (1 + drift) + offset + rng.uniform(-jitter, jitter)
        for i in range(ONSETS)
    ]


TAKES = {
    "late (120 ms)": take(offset=0.120),
    "slow (2% drift)": take(drift=0.02),
    "scattered (+/-90 ms)": take(jitter=0.090),
}


def main() -> None:
    grid = BeatGrid.from_bpm(BPM, duration_sec=20)
    for name, onsets in TAKES.items():
        analysis = score_take(onsets, grid)
        print(f"{name:22} {analysis.verdict.value:12} score={analysis.score:.2f}  {analysis.reason}")
        try:
            plan = plan_correction(analysis)
        except TakeRejected:
            print(f"{'':22} -> send back for a re-record")
        else:
            print(f"{'':22} -> shift {plan.shift_sec * 1000:+.0f} ms, stretch x{plan.stretch_ratio:.4f}")


if __name__ == "__main__":
    main()
