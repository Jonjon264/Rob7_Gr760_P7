"""Voice interface: microphone -> Whisper -> Qwen -> manager/commands, plus spoken replies.

agent.py QwenAgent | validation.py output checks | recorder.py PiRecorder (speech to text)
speaker.py ReplyPlayer (text to speech) | node.py VoiceManager (ROS node) | cli.py no-ROS demo
"""

from pathlib import Path

DEFAULT_CONFIG_DIR = Path("~/ros2_ws/config").expanduser()  # holds map.json, rules.txt, piper/
