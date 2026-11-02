"""extract.py guards, tested with a stub librosa so no DSP stack is needed."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cypherline import extract  # noqa: E402


def _stub(monkeypatch, *, samples=(0.1, 0.2), beats=(), onsets=(), times=None):
    lib = SimpleNamespace(
        load=lambda path, mono=True: (list(samples), 22050),
        beat=SimpleNamespace(beat_track=lambda **kw: (120.0, list(beats))),
        onset=SimpleNamespace(onset_detect=lambda **kw: list(onsets)),
        frames_to_time=lambda frames, sr: list(times if times is not None else frames),
    )
    monkeypatch.setattr(extract, "_require_librosa", lambda: lib)


def test_grid_from_audio_returns_beats(monkeypatch):
    _stub(monkeypatch, beats=(0.0, 0.5, 1.0))
    assert extract.grid_from_audio("a.wav").beat_times == (0.0, 0.5, 1.0)


def test_grid_rejects_empty_audio(monkeypatch):
    _stub(monkeypatch, samples=())
    with pytest.raises(ValueError, match="no audio samples"):
        extract.grid_from_audio("a.wav")


def test_grid_rejects_too_few_beats(monkeypatch):
    _stub(monkeypatch, beats=(0.0,))
    with pytest.raises(ValueError, match="usable beat"):
        extract.grid_from_audio("a.wav")


def test_grid_rejects_non_finite_beats(monkeypatch):
    _stub(monkeypatch, beats=(0.0, 1.0), times=[0.0, float("nan")])
    with pytest.raises(ValueError, match="non-finite"):
        extract.grid_from_audio("a.wav")


def test_onsets_returned_as_floats(monkeypatch):
    _stub(monkeypatch, onsets=(0.25, 0.75))
    assert extract.onsets_from_audio("a.wav") == [0.25, 0.75]


def test_onsets_rejects_silent_take(monkeypatch):
    _stub(monkeypatch, onsets=())
    with pytest.raises(ValueError, match="No onsets"):
        extract.onsets_from_audio("a.wav")


def test_onsets_rejects_empty_audio(monkeypatch):
    _stub(monkeypatch, samples=())
    with pytest.raises(ValueError, match="no audio samples"):
        extract.onsets_from_audio("a.wav")
