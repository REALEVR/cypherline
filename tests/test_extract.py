"""extract.py guards, tested with a stub librosa so no DSP stack is needed."""

import math
import types

import pytest

from cypherline import extract


def _stub(samples=(0.1, 0.2), beat_frames=(0, 1, 2), onset_frames=(3, 4), times=None):
    """A minimal fake of the librosa surface extract.py touches."""
    mod = types.SimpleNamespace()
    mod.load = lambda path, mono=True: (list(samples), 22050)
    mod.beat = types.SimpleNamespace(
        beat_track=lambda **kw: (120.0, list(beat_frames))
    )
    mod.onset = types.SimpleNamespace(onset_detect=lambda **kw: list(onset_frames))
    mod.frames_to_time = lambda frames, sr: (
        list(times) if times is not None else [f * 0.5 for f in frames]
    )
    return mod


@pytest.fixture
def use(monkeypatch):
    def _use(**kw):
        monkeypatch.setattr(extract, "_require_librosa", lambda: _stub(**kw))
    return _use


def test_grid_from_audio_returns_grid(use):
    use()
    assert extract.grid_from_audio("x.wav").beat_times == (0.0, 0.5, 1.0)


def test_grid_rejects_empty_audio(use):
    use(samples=())
    with pytest.raises(ValueError, match="no audio samples"):
        extract.grid_from_audio("silent.wav")


def test_grid_rejects_too_few_beats(use):
    use(beat_frames=(0,))
    with pytest.raises(ValueError, match="usable beat"):
        extract.grid_from_audio("short.wav")


def test_grid_rejects_non_finite_beats(use):
    use(beat_frames=(0, 1), times=[0.0, math.nan])
    with pytest.raises(ValueError, match="non-finite"):
        extract.grid_from_audio("bad.wav")


def test_onsets_returns_times(use):
    use()
    assert extract.onsets_from_audio("x.wav") == [1.5, 2.0]


def test_onsets_rejects_empty_audio(use):
    use(samples=())
    with pytest.raises(ValueError, match="no audio samples"):
        extract.onsets_from_audio("silent.wav")


def test_onsets_rejects_no_onsets(use):
    use(onset_frames=(), times=[])
    with pytest.raises(ValueError, match="No onsets"):
        extract.onsets_from_audio("quiet.wav")


def test_onsets_rejects_non_finite(use):
    use(times=[0.1, math.inf])
    with pytest.raises(ValueError, match="non-finite"):
        extract.onsets_from_audio("bad.wav")
