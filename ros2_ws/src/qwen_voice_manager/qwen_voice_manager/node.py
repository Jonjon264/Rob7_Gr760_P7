"""Keep audio capture, model requests, and ROS dispatch independent."""

import json
import importlib.util
import os
from pathlib import Path
from queue import Empty, Queue
import re
import threading

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def load_project_module(name):
    """Load the original project script installed by this package."""
    runtime = Path(get_package_share_directory('qwen_voice_manager')) / 'runtime'
    spec = importlib.util.spec_from_file_location(name, runtime / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VoiceManager(Node):
    def __init__(self, agent=None, recorder_factory=None, reply_player=None, **kwargs):
        super().__init__('qwen_voice_manager', **kwargs)
        config = Path(get_package_share_directory('qwen_voice_manager')) / 'config'
        self.declare_parameter('command_topic', 'manager/commands')
        self.declare_parameter('text_topic', 'manager/text')
        self.declare_parameter('transcript_topic', 'manager/transcripts')
        self.declare_parameter('speech_enabled', True)
        self.declare_parameter('speech_model', 'base.en')
        self.declare_parameter('speech_device', 'cpu')
        self.declare_parameter('wake_words', 'bumblebee')
        self.declare_parameter('input_device_index', -1)
        self.declare_parameter('map_file', str(config / 'map.json'))
        self.declare_parameter('rules_file', str(config / 'rules.txt'))
        self.declare_parameter('request_timeout', 30.0)
        self.declare_parameter('tts_enabled', True)
        self.declare_parameter('tts_model', os.environ.get(
            'PIPER_MODEL', '/opt/piper/en_US-hfc_male-medium.onnx'))
        self.declare_parameter('output_device_index', -1)

        if agent is None:
            QwenAgent = load_project_module('qwen_agent').QwenAgent
            # Use the existing endpoint/model/auth defaults; QWEN_API_KEY overrides auth.
            self.declare_parameter('base_url', '')
            self.declare_parameter('model', 'qwen3-vl')
            options = dict(
                model=self.get_parameter('model').value,
                map_file=self.get_parameter('map_file').value,
                rules_file=self.get_parameter('rules_file').value,
                timeout=self.get_parameter('request_timeout').value,
            )
            if self.get_parameter('base_url').value:
                options['base_url'] = self.get_parameter('base_url').value
            agent = QwenAgent(**options)
        self.agent = agent
        self._recorder_factory = recorder_factory
        self._recorder = None
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._generation = 0
        self._requests = Queue()
        self._results = Queue()
        self._transcripts = Queue()
        self.command_publisher = self.create_publisher(
            String, self.get_parameter('command_topic').value, 10)
        self.transcript_publisher = self.create_publisher(
            String, self.get_parameter('transcript_topic').value, 10)
        self.text_subscription = self.create_subscription(
            String, self.get_parameter('text_topic').value,
            lambda message: self.submit_text(message.data), 10)
        self._timer = self.create_timer(0.05, self._publish_pending)
        self._handle_reply = load_project_module('ask_qwen').handle_reply
        self._reply_player = reply_player
        if self._reply_player is None and self.get_parameter('tts_enabled').value:
            ReplyPlayer = load_project_module('reply_audio').ReplyPlayer
            output_device = self.get_parameter('output_device_index').value
            self._reply_player = ReplyPlayer(
                model_path=self.get_parameter('tts_model').value,
                device=output_device if output_device >= 0 else None,
                on_error=self.get_logger().error,
            )
        self._model_thread = threading.Thread(target=self._model_loop, daemon=True)
        self._model_thread.start()
        self._speech_thread = None
        if self.get_parameter('speech_enabled').value:
            self._speech_thread = threading.Thread(target=self._speech_loop, daemon=True)
            self._speech_thread.start()
        self.get_logger().info('Voice manager ready; text input is also available on manager/text')

    def submit_text(self, text):
        text = text.strip()
        if not text or self._closed.is_set():
            return
        self._transcripts.put(text)
        # Unambiguous standalone stop commands bypass an in-flight model request.
        # Never allow that request's late result to restart navigation after Cancel.
        normalized = re.sub(r'[.!?]+$', '', text.lower()).strip()
        with self._lock:
            if normalized in {'stop', 'stop now', 'cancel', 'cancel task', 'cancel the task', 'abort'}:
                self._generation += 1
                self._results.put((
                    self._generation, {'action': 'cancel'},
                    'I will cancel the current task.',
                ))
            else:
                self._requests.put((self._generation, text))

    def _model_loop(self):
        while not self._closed.is_set():
            request = self._requests.get()
            if request is None:
                return
            generation, text = request
            with self._lock:
                if generation != self._generation:
                    continue
            try:
                commands, reply = self.agent.ask(text)
            except Exception as exc:
                # Keep listening after endpoint, file, or inference failures.
                commands = {'action': 'error', 'message': f'Qwen request failed: {type(exc).__name__}'}
                reply = 'I could not process that request.'
            with self._lock:
                if generation != self._generation or self._closed.is_set():
                    continue
                if isinstance(commands, dict) and commands.get('action') == 'cancel':
                    self._generation += 1
                    generation = self._generation
                self._results.put((generation, commands, reply))

    def _publish_pending(self):
        while not self._transcripts.empty():
            try:
                text = self._transcripts.get_nowait()
            except Empty:
                break
            self.get_logger().info(f'Transcribed: {text}')
            self.transcript_publisher.publish(String(data=text))
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
            try:
                # Commands are published before touching any audio device.
                if (self._reply_player is not None and isinstance(commands, dict)
                        and commands.get('action') == 'cancel'):
                    self._reply_player.cancel()
                with self._lock:
                    if generation != self._generation or self._closed.is_set():
                        continue
                    if self._reply_player is not None:
                        self._reply_player.submit(reply)
                self._handle_reply(reply)
            except Exception as exc:
                self.get_logger().error(f'Reply handler failed: {type(exc).__name__}')

    def _speech_loop(self):
        recorder = None
        try:
            factory = self._recorder_factory
            if factory is None:
                factory = load_project_module('ask_qwen').create_recorder
            options = dict(
                model=self.get_parameter('speech_model').value,
                device=self.get_parameter('speech_device').value,
                wake_words=self.get_parameter('wake_words').value,
                on_recording_start=lambda: self.get_logger().info('Speech detected; recording'),
                on_recording_stop=lambda: self.get_logger().info('Silence detected; transcribing'),
            )
            if self.get_parameter('input_device_index').value >= 0:
                options['input_device_index'] = self.get_parameter('input_device_index').value
            self.get_logger().info('Loading ask_qwen Whisper/VAD recorder...')
            recorder = factory(**options)
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
                # shutdown() owns an already-registered recorder on node teardown.
                owns_recorder = self._recorder is recorder and not self._closed.is_set()
                if owns_recorder:
                    self._recorder = None
            if recorder is not None and owns_recorder:
                recorder.shutdown()

    def close(self):
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
