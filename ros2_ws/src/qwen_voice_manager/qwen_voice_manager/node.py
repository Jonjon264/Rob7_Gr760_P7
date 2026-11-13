"""VoiceManager: the ROS node that ties speech input, the Qwen agent and spoken replies together.

    microphone (recorder.py) --+
                               +--> text --> QwenAgent --+--> manager/commands (JSON String)
    manager/text (String) -----+                         +--> spoken reply (speaker.py)

Three threads keep slow work off the ROS callbacks:
  speech thread : waits for a spoken request (only when speech_enabled)
  model thread  : asks Qwen, one request at a time
  ROS timer     : publishes results and starts the spoken reply

Stop handling: "stop"/"cancel"/"abort" skip the model entirely. Each one bumps
`_generation`, which invalidates every earlier request and result, so a slow
answer can never restart navigation after a cancel.
"""

import json
import os
from queue import Empty, Queue
import re
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from . import DEFAULT_CONFIG_DIR

# Phrases that cancel immediately without asking the model.
STOP_PHRASES = {'stop', 'stop now', 'cancel', 'cancel task', 'cancel the task', 'abort'}
STOP_REPLY = 'I will cancel the current task.'


class VoiceManager(Node):
    """Parameters and topics are listed in README.md.

    agent, recorder_factory and reply_player can be injected (used by tests);
    by default they are built from the parameters.
    """

    def __init__(self, agent=None, recorder_factory=None, reply_player=None, **kwargs):
        super().__init__('qwen_voice_manager', **kwargs)
        self._declare_parameters()

        self.agent = agent if agent is not None else self._build_agent()
        self._recorder_factory = recorder_factory
        self._reply_player = reply_player if reply_player is not None else self._build_reply_player()
        self._recorder = None

        self._closed = threading.Event()
        self._lock = threading.Lock()   # guards _generation, _recorder and result hand-off
        self._generation = 0
        self._requests = Queue()        # (generation, text) waiting for the model
        self._results = Queue()         # (generation, commands, reply) ready to publish
        self._transcripts = Queue()     # texts to echo on the transcript topic

        self.command_publisher = self.create_publisher(
            String, self.get_parameter('command_topic').value, 10)
        self.transcript_publisher = self.create_publisher(
            String, self.get_parameter('transcript_topic').value, 10)
        self.text_subscription = self.create_subscription(
            String, self.get_parameter('text_topic').value,
            lambda message: self.submit_text(message.data), 10)
        self._timer = self.create_timer(0.05, self._publish_pending)

        self._model_thread = threading.Thread(target=self._model_loop, daemon=True)
        self._model_thread.start()
        self._speech_thread = None
        if self.get_parameter('speech_enabled').value:
            self._speech_thread = threading.Thread(target=self._speech_loop, daemon=True)
            self._speech_thread.start()
        self.get_logger().info('Voice manager ready; text input is also available on manager/text')

    # ------------------------------------------------------------ setup
    def _declare_parameters(self):
        config_dir = DEFAULT_CONFIG_DIR
        defaults = {
            # topics
            'command_topic': 'manager/commands',
            'text_topic': 'manager/text',
            'transcript_topic': 'manager/transcripts',
            # speech to text (-1 = system default device)
            'speech_enabled': True,
            'speech_model': 'base.en',
            'wake_words': 'hey_jarvis',  # an openWakeWord model name or .onnx path
            'input_device_index': -1,
            # Qwen ('' base_url = the agent's built-in default endpoint)
            'base_url': '',
            'model': 'qwen3-vl',
            'map_file': str(config_dir / 'map.json'),
            'rules_file': str(config_dir / 'rules.txt'),
            'request_timeout': 30.0,
            # text to speech
            'tts_enabled': True,
            'tts_model': str(config_dir / 'piper' / 'en_US-hfc_male-medium.onnx'),
            'output_device_index': -1,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)

    def _build_agent(self):
        from .agent import QwenAgent  # imported here so injected agents need no openai package
        options = dict(
            model=self.get_parameter('model').value,
            map_file=self.get_parameter('map_file').value,
            rules_file=self.get_parameter('rules_file').value,
            timeout=self.get_parameter('request_timeout').value,
        )
        if self.get_parameter('base_url').value:
            options['base_url'] = self.get_parameter('base_url').value
        return QwenAgent(**options)

    def _build_reply_player(self):
        if not self.get_parameter('tts_enabled').value:
            return None
        from .speaker import ReplyPlayer
        device = self.get_parameter('output_device_index').value
        return ReplyPlayer(
            model_path=self.get_parameter('tts_model').value,
            device=device if device >= 0 else None,
            on_error=self.get_logger().error,
        )

    # ------------------------------------------------------------ input
    def submit_text(self, text):
        """Entry point for typed text and for transcribed speech."""
        text = text.strip()
        if not text or self._closed.is_set():
            return
        self._transcripts.put(text)
        normalized = re.sub(r'[.!?]+$', '', text.lower()).strip()
        with self._lock:
            if normalized in STOP_PHRASES:
                self._generation += 1  # invalidates everything still queued or in flight
                self._results.put((self._generation, {'action': 'cancel'}, STOP_REPLY))
            else:
                self._requests.put((self._generation, text))

    # ------------------------------------------------------------ model thread
    def _model_loop(self):
        while not self._closed.is_set():
            request = self._requests.get()
            if request is None:
                return
            generation, text = request
            with self._lock:
                if generation != self._generation:
                    continue  # a stop arrived while this request was queued
            started = time.monotonic()
            try:
                commands, reply = self.agent.ask(text)
                self.get_logger().info(f'Qwen answered in {time.monotonic() - started:.1f}s')
            except Exception as exc:
                # Keep listening after endpoint, file, or inference failures.
                commands = {'action': 'error', 'message': f'Qwen request failed: {type(exc).__name__}'}
                reply = 'I could not process that request.'
            with self._lock:
                if generation != self._generation or self._closed.is_set():
                    continue  # stale: a stop arrived while the model was thinking
                if isinstance(commands, dict) and commands.get('action') == 'cancel':
                    self._generation += 1
                    generation = self._generation
                self._results.put((generation, commands, reply))

    # ------------------------------------------------------------ publishing (ROS timer)
    def _publish_pending(self):
        self._publish_transcripts()
        while not self._results.empty():
            try:
                generation, commands, reply = self._results.get_nowait()
            except Empty:
                break
            with self._lock:
                if generation != self._generation or self._closed.is_set():
                    continue
                payload = json.dumps(commands, allow_nan=False)
                self.command_publisher.publish(String(data=payload))
            self.get_logger().info(f'Manager output: {payload}')
            self._speak(generation, commands, reply)

    def _publish_transcripts(self):
        while not self._transcripts.empty():
            try:
                text = self._transcripts.get_nowait()
            except Empty:
                break
            self.get_logger().info(f'Transcribed: {text}')
            self.transcript_publisher.publish(String(data=text))

    def _speak(self, generation, commands, reply):
        """Play the reply. Always runs after the commands were published."""
        if self._reply_player is None:
            return
        try:
            if isinstance(commands, dict) and commands.get('action') == 'cancel':
                self._reply_player.cancel()  # cut off anything still being said
            with self._lock:
                if generation != self._generation or self._closed.is_set():
                    return
                self._reply_player.submit(reply)
        except Exception as exc:
            self.get_logger().error(f'Reply handler failed: {type(exc).__name__}')

    # ------------------------------------------------------------ speech thread
    def _speech_loop(self):
        recorder = None
        try:
            recorder = self._create_recorder()
            with self._lock:
                closing = self._closed.is_set()
                if not closing:
                    self._recorder = recorder
            if closing:
                recorder.shutdown()
                return
            self.get_logger().info('Recorder loaded; speak the wake word and your instruction')
            while not self._closed.is_set():
                recorder.text(self.submit_text)
        except Exception as exc:
            if not self._closed.is_set():
                self.get_logger().error(
                    f'Speech input failed ({type(exc).__name__}: {exc}); '
                    'text input remains available on manager/text')
        finally:
            with self._lock:
                # close() owns an already-registered recorder on node teardown.
                owns_recorder = self._recorder is recorder and not self._closed.is_set()
                if owns_recorder:
                    self._recorder = None
            if recorder is not None and owns_recorder:
                recorder.shutdown()

    def _create_recorder(self):
        factory = self._recorder_factory
        if factory is None:
            from .recorder import PiRecorder  # heavy audio/ML imports only when speech is on
            factory = PiRecorder
        options = dict(
            model=self.get_parameter('speech_model').value,
            wake_words=self.get_parameter('wake_words').value,
            on_recording_start=lambda: self.get_logger().info('Speech detected; recording'),
            on_recording_stop=lambda: self.get_logger().info('Silence detected; transcribing'),
        )
        if self.get_parameter('input_device_index').value >= 0:
            options['input_device_index'] = self.get_parameter('input_device_index').value
        self.get_logger().info('Loading wake-word, VAD and Whisper models...')
        return factory(**options)

    # ------------------------------------------------------------ shutdown
    def close(self):
        """Stop all threads and audio devices. Safe to call twice."""
        if self._closed.is_set():
            return
        self._closed.set()
        self._requests.put(None)
        if self._reply_player is not None:
            self._reply_player.close()
        with self._lock:
            recorder = self._recorder
            self._recorder = None
        if recorder is not None:
            recorder.shutdown()
        if self._speech_thread is not None:
            self._speech_thread.join(timeout=2)
        self._model_thread.join(timeout=2)

    def destroy_node(self):
        self.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = VoiceManager()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
