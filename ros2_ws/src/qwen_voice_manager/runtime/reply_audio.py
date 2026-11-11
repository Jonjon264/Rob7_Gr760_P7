"""Play reply strings with Piper, independently of model and ROS callbacks."""

import logging
import os
from pathlib import Path
from queue import Empty, Queue
import threading


def default_model_path():
    return os.path.expanduser('~/ros2_ws/config/piper/en_US-hfc_male-medium.onnx')


class PiperAudio:
    def __init__(self, model_path, device=None):
        path = Path(model_path).expanduser().resolve()
        if not path.is_file() or not Path(str(path) + '.json').is_file():
            raise FileNotFoundError(f'Piper model and companion .json required: {path}')
        import numpy as np
        import sounddevice as sd
        from piper import PiperVoice

        self.voice = PiperVoice.load(str(path))
        self.np = np
        self.sd = sd
        self.device = device

    def synthesize(self, text):
        audio = b''.join(chunk.audio_int16_bytes for chunk in self.voice.synthesize(text))
        return self.np.frombuffer(audio, dtype=self.np.int16), self.voice.config.sample_rate

    def play(self, data, sample_rate):
        self.sd.play(data, samplerate=sample_rate, device=self.device)

    def wait(self):
        self.sd.wait()

    def stop(self):
        self.sd.stop()


class ReplyPlayer:
    """submit() only queues text; one worker owns synthesis and playback.

    cancel() drops queued text and stops playback. In-flight inference may
    finish, but its samples are discarded. close() also prevents new work.
    """

    def __init__(self, model_path=None, device=None, on_error=None, backend_factory=None):
        self._factory = backend_factory or (
            lambda: PiperAudio(model_path or default_model_path(), device=device))
        self._on_error = on_error or logging.getLogger(__name__).error
        self._backend = None
        self._queue = Queue()
        self._stop_requests = Queue()
        self._lock = threading.Lock()
        self._play_lock = threading.Lock()
        self._closed = False
        self._generation = 0
        self._stop_pending = threading.Event()
        self._stop_pending.set()
        self._thread = threading.Thread(target=self._run, name='reply-playback', daemon=True)
        self._stop_thread = threading.Thread(
            target=self._stop_loop, name='reply-stop', daemon=True)
        self._stop_thread.start()
        self._thread.start()

    def submit(self, reply: str):
        if not isinstance(reply, str) or not reply.strip():
            return
        with self._lock:
            if not self._closed:
                self._queue.put((self._generation, reply))

    def _clear_locked(self):
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return

    def _stop_playback(self):
        if self._backend is not None:
            try:
                self._backend.stop()
            except Exception as exc:
                self._on_error(f'Audio stop failed: {type(exc).__name__}: {exc}')

    def cancel(self):
        with self._lock:
            if self._closed:
                return
            self._generation += 1
            self._clear_locked()
            self._request_stop_locked()

    def _request_stop_locked(self):
        # Even a slow sound-device stop must never run in a ROS callback.
        self._stop_pending = threading.Event()
        self._stop_requests.put(self._stop_pending)

    def _stop_loop(self):
        while True:
            finished = self._stop_requests.get()
            if finished is None:
                return
            try:
                with self._play_lock:
                    self._stop_playback()
            finally:
                finished.set()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            self._clear_locked()
            self._queue.put(None)
            self._request_stop_locked()
            self._stop_requests.put(None)
        self._thread.join(timeout=2)
        self._stop_thread.join(timeout=2)

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            generation, reply = item
            try:
                with self._lock:
                    if self._closed or generation != self._generation:
                        continue
                if self._backend is None:
                    backend = self._factory()
                    with self._lock:
                        self._backend = backend
                with self._lock:
                    if self._closed or generation != self._generation:
                        continue
                data, sample_rate = self._backend.synthesize(reply)
                with self._lock:
                    stopped = self._stop_pending
                stopped.wait()
                # Device initialization must not hold the submit() state lock.
                with self._play_lock:
                    with self._lock:
                        if self._closed or generation != self._generation or not len(data):
                            continue
                    self._backend.play(data, sample_rate)
                self._backend.wait()
            except Exception as exc:
                self._on_error(f'Reply playback failed: {type(exc).__name__}: {exc}')
