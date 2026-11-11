"""Speech input for the Raspberry Pi: openWakeWord + Silero VAD + faster-whisper.

One call to text() runs this pipeline and returns the transcript:

    microphone -> wake word -> wait for speech -> record until silence -> Whisper

    wake word : openWakeWord  (ONNX, no per-CPU binaries, so it runs on a Pi 5)
    speech/silence : Silero VAD (shipped inside openWakeWord)
    transcription  : faster-whisper on the CPU

VoiceManager only needs two methods: text() to wait for one spoken request,
and shutdown() to stop listening.
"""

import logging
from pathlib import Path
from queue import Empty, Queue
import threading

import numpy as np

SAMPLE_RATE = 16000          # Whisper, the VAD and openWakeWord all want 16 kHz mono
FRAME = 1280                 # samples per frame = 80 ms, the size openWakeWord expects
FRAMES_PER_SECOND = SAMPLE_RATE / FRAME

log = logging.getLogger(__name__)


class PiRecorder:
    def __init__(
        self,
        model='base.en',                  # Whisper model size; try 'tiny.en' on a slow Pi
        compute_type='int8',              # int8 keeps Whisper fast and small on the CPU
        wake_words='hey_jarvis',          # openWakeWord model name(s) or path(s); '' = no wake word
        wake_threshold=0.5,               # wake score (0-1) needed to count as a detection
        vad_threshold=0.5,                # speech probability (0-1) needed to count as speech
        post_speech_silence_duration=0.8,  # seconds of silence that end an utterance
        wake_listen_timeout=6.0,          # seconds to wait for speech after the wake word
        max_record_seconds=20.0,          # hard cap so a noisy room cannot record forever
        language='en',
        input_device_index=None,          # None = system default microphone
        on_recording_start=None,          # called when the user starts speaking
        on_recording_stop=None,           # called when silence ends the recording
    ):
        self.wake_threshold = wake_threshold
        self.vad_threshold = vad_threshold
        self.silence_frames = max(1, round(post_speech_silence_duration * FRAMES_PER_SECOND))
        self.listen_timeout_frames = round(wake_listen_timeout * FRAMES_PER_SECOND)
        self.max_frames = round(max_record_seconds * FRAMES_PER_SECOND)
        self.input_device_index = input_device_index
        self.on_start = on_recording_start or (lambda: None)
        self.on_stop = on_recording_stop or (lambda: None)

        self._frames = Queue()               # microphone frames waiting to be processed
        self._stream = None                  # opened lazily by _open_microphone()
        self._closed = threading.Event()
        self._has_listened = False           # nothing can be stale before the first text()

        self.use_wake_word = bool(str(wake_words).strip())
        self.wake = self._load_wake_model(wake_words) if self.use_wake_word else None
        self.vad = self._load_vad()
        self.transcribe = self._load_whisper(model, compute_type, language)

    # ------------------------------------------------------------------ models
    # Heavy imports stay inside these methods so this file imports on any machine.

    @staticmethod
    def _load_wake_model(wake_words):
        import openwakeword
        from openwakeword.model import Model

        requested = [w.strip() for w in str(wake_words).split(',') if w.strip()]
        # Accept a built-in model name (e.g. 'hey_jarvis') or a path to a custom .onnx file.
        models = [w for w in requested if w in openwakeword.MODELS or Path(w).is_file()]
        if not models:
            log.warning('%s is not an openWakeWord model (built in: %s); using hey_jarvis',
                        requested, sorted(openwakeword.MODELS))
            models = ['hey_jarvis']

        def build():
            # 'onnx' avoids tflite-runtime, which has no wheel for many Pi setups.
            return Model(wakeword_models=models, inference_framework='onnx')

        try:
            return build()
        except Exception:
            # First run: the model files are not on disk yet. Download them once and retry.
            openwakeword.utils.download_models([Path(m).stem for m in models if not Path(m).is_file()])
            return build()

    @staticmethod
    def _load_vad():
        from openwakeword.vad import VAD
        return VAD()

    @staticmethod
    def _load_whisper(model, compute_type, language):
        from faster_whisper import WhisperModel
        whisper = WhisperModel(model, device='cpu', compute_type=compute_type)

        def transcribe(samples):
            audio = samples.astype(np.float32) / 32768.0       # int16 -> float in [-1, 1]
            segments, _ = whisper.transcribe(
                audio, language=language,
                beam_size=1,                                    # greedy decoding: fastest
                condition_on_previous_text=False)               # utterances are independent
            return ' '.join(segment.text.strip() for segment in segments).strip()

        return transcribe

    # ------------------------------------------------------------------- audio

    def _open_microphone(self):
        """Start capturing. Frames arrive on a driver thread and are queued for text()."""
        if self._stream is not None:
            return
        import sounddevice as sd

        def on_audio(indata, frame_count, time_info, status):
            self._frames.put(indata[:, 0].copy())          # mono channel, copied off the driver buffer

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype='int16', blocksize=FRAME,
            device=self.input_device_index, callback=on_audio)
        self._stream.start()

    def _next_frame(self):
        """Return the next 80 ms of audio, or None once shutdown() was called."""
        while not self._closed.is_set():
            try:
                return self._frames.get(timeout=0.2)       # timeout lets us notice shutdown
            except Empty:
                continue
        return None

    def _discard_buffered_audio(self):
        """Drop audio captured while we were busy (e.g. while Qwen was answering)."""
        while not self._frames.empty():
            try:
                self._frames.get_nowait()
            except Empty:
                break

    # ---------------------------------------------------------------- pipeline

    def _wait_for_wake_word(self):
        """Block until the wake word is heard. Returns False if shut down first."""
        self.wake.reset()                                  # forget the previous detection
        while (frame := self._next_frame()) is not None:
            scores = self.wake.predict(frame)              # {model name: score 0-1}
            if any(score >= self.wake_threshold for score in scores.values()):
                return True
        return False

    def _record_utterance(self):
        """Record from the first spoken frame until silence.

        Returns the audio as one int16 array, or None if nobody spoke before
        the timeout (or the recorder was shut down meanwhile).
        """
        self.vad.reset_states()                            # the VAD is stateful across frames
        recorded = []                                      # frames from the start of speech on
        waited = 0                                         # frames spent waiting for speech
        silent = 0                                         # consecutive silent frames after speech

        while (frame := self._next_frame()) is not None:
            is_speech = float(self.vad.predict(frame)) >= self.vad_threshold

            if not recorded:                               # still waiting for the user to speak
                if not is_speech:
                    waited += 1
                    if waited > self.listen_timeout_frames:
                        return None                        # woke up, but nobody said anything
                    continue
                self.on_start()

            recorded.append(frame)                         # keep silence too, so words are not clipped
            silent = 0 if is_speech else silent + 1
            if silent >= self.silence_frames or len(recorded) >= self.max_frames:
                self.on_stop()
                return np.concatenate(recorded)
        return None

    # --------------------------------------------------- interface for the node

    def text(self, callback=None):
        """Wait for one spoken request. Returns its transcript (also passed to callback).

        Returns None if shut down, if no one spoke, or if nothing was recognised.
        """
        self._open_microphone()
        if self._has_listened:
            self._discard_buffered_audio()
        self._has_listened = True

        if self.use_wake_word and not self._wait_for_wake_word():
            return None
        audio = self._record_utterance()
        if audio is None:
            return None

        text = self.transcribe(audio)
        if text and not self._closed.is_set():
            if callback is not None:
                callback(text)
        return text or None

    def shutdown(self):
        """Stop the microphone and make any blocked text() call return."""
        self._closed.set()
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                log.error('Closing the microphone failed: %s', exc)

