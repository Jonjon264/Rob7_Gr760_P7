"""Tests for the Pi speech pipeline using fake audio, VAD and Whisper (no models needed)."""

import importlib.util
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    'pi_recorder', Path(__file__).parents[1] / 'runtime' / 'pi_recorder.py')
pi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pi)


class FakeWake:
    """Reports the wake word on its second frame."""
    def __init__(self):
        self.calls = 0

    def reset(self):
        pass

    def predict(self, frame):
        self.calls += 1
        return {'hey_jarvis': 0.9 if self.calls == 2 else 0.0}


class FakeVad:
    """A frame counts as speech when its samples are loud (> 100)."""
    def reset_states(self):
        pass

    def predict(self, frame):
        return 1.0 if frame[0] > 100 else 0.0


def make_recorder(levels, wake_words, **options):
    """PiRecorder whose models and microphone are replaced; `levels` = loudness per 80 ms frame."""
    transcribed = []                                       # sample counts handed to "Whisper"

    class TestRecorder(pi.PiRecorder):
        _load_wake_model = staticmethod(lambda wake_words: FakeWake())
        _load_vad = staticmethod(lambda: FakeVad())

        @staticmethod
        def _load_whisper(model, compute_type, language):
            return lambda samples: transcribed.append(len(samples)) or 'go to the charging station'

        def _open_microphone(self):
            for level in levels:
                self._frames.put(np.full(pi.FRAME, level, dtype=np.int16))

    return TestRecorder(wake_words=wake_words, post_speech_silence_duration=0.16, **options), transcribed


def test_wake_word_then_speech_is_transcribed():
    # frames: quiet, quiet(wake word heard), speech, speech, then silence ends the utterance
    recorder, transcribed = make_recorder([0, 0, 500, 500, 0, 0, 0], wake_words='hey_jarvis')
    heard = []
    assert recorder.text(heard.append) == 'go to the charging station'
    assert heard == ['go to the charging station']
    assert transcribed == [pi.FRAME * 4]                   # 2 speech + 2 trailing silence frames


def test_works_without_wake_word():
    recorder, _ = make_recorder([500, 500, 0, 0], wake_words='')
    assert recorder.text() == 'go to the charging station'


def test_no_speech_after_wake_word_times_out():
    recorder, transcribed = make_recorder([0, 0, 0, 0, 0], wake_words='hey_jarvis',
                                          wake_listen_timeout=0.16)
    assert recorder.text() is None and transcribed == []
