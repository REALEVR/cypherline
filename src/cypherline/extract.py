"""Audio in, timing out. The only module that needs a DSP stack.

Everything else in this package works on plain lists of times, which is what
keeps the scoring logic testable without audio fixtures or a librosa install.
This module is the boundary: it is the one place that reads waveforms, and it is
an optional extra (`pip install cypherline[audio]`).

Kept deliberately thin. Beat tracking and onset detection are solved problems
with well-tested implementations; the product's own contribution is what
`fit.py` does with their output, not a hand-rolled onset detector.
"""

from __future__ import annotations

from .grid import BeatGrid

_MISSING = (
    "Audio extraction needs librosa and soundfile, which are an optional extra:\n"
    "    pip install 'cypherline[audio]'\n"
    "The grid, fit and align modules work without them, on onset times you "
    "supply yourself."
)


def _require_librosa():
    try:
        import librosa  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(_MISSING) from exc
    return librosa


def grid_from_audio(path: str, *, beats_per_bar: int = 4) -> BeatGrid:
    """Detect the beat grid of an instrumental.

    Returns explicit beat times rather than a single BPM, because that is what
    BeatGrid wants and what survives a track whose tempo is not perfectly
    constant.
    """
    librosa = _require_librosa()
    y, sr = librosa.load(path, mono=True)
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    times = librosa.frames_to_time(beat_frames, sr=sr)
    if len(times) < 2:
        raise ValueError(f"Could not find a usable beat in {path!r}.")
    return BeatGrid(beat_times=tuple(float(t) for t in times), beats_per_bar=beats_per_bar)


def onsets_from_audio(path: str, *, backtrack: bool = True) -> list[float]:
    """Detect note/syllable onsets in a vocal take.

    `backtrack` moves each detected onset back to the nearest preceding energy
    minimum, which lands it on the start of the syllable rather than its loudest
    moment. That matters here: an unbacktracked onset sits systematically late by
    a consonant's length, and `fit.score_take` would read that as lag.
    """
    librosa = _require_librosa()
    y, sr = librosa.load(path, mono=True)
    frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames", backtrack=backtrack)
    return [float(t) for t in librosa.frames_to_time(frames, sr=sr)]
