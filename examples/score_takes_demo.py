"""Score three synthetic takes against a 90 BPM grid and print what the pipeline decides.

Run from the repo root:  python examples/score_takes_demo.py

Stdlib only. Shows the distinction the project turns on: a take that is merely
*late* is fixable with a shift, while a take that *scatters* is rejected.
"""

import random

from cypherline import BeatGrid, TakeRejected, plan_correction, score_take

BPM = 90
SIXTEENTH = 60 / BPM / 4


def make_take(offset_sec: float, jitter_sec: float, count: int = 64, seed: int = 7) -> list[float]:
    """Onsets on a sixteenth-note lattice, shifted by `offset_sec`, with Gaussian jitter."""
    rng = random.Random(seed)
    return [i * SIXTEENTH * 2 + offset_sec + rng.gauss(0, jitter_sec) for i in range(count)]


def main() -> None:
    grid = BeatGrid.from_bpm(BPM, duration_sec=200)
    takes = {
        "on the beat": make_take(0.0, 0.004),
        # 120 ms late is 47 ms short of the next sixteenth (166.7 ms), so the plan shifts later by 47 ms.
        "uniformly 120 ms late": make_take(0.120, 0.004),
        "scattered (±90 ms)": make_take(0.0, 0.090),
    }
    for name, onsets in takes.items():
        analysis = score_take(onsets, grid)
        print(f"{name}: verdict={analysis.verdict.value} score={analysis.score:.2f}")
        print(f"  {analysis.reason}")
        try:
            plan = plan_correction(analysis)
            print(f"  plan: shift={plan.shift_sec * 1000:+.0f} ms, stretch={plan.stretch_ratio:.4f}")
        except TakeRejected:
            print("  plan: none — take rejected, ask the contributor to re-record")


if __name__ == "__main__":
    main()
