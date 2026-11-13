"""Command-line voice loop for trying the pipeline without ROS 2.

    wake word -> speech -> Whisper -> Qwen -> printed commands and reply

Run with `ask_qwen`. The ROS node (node.py) does the same on the real robot.
"""

import json

from .agent import QwenAgent
from .recorder import PiRecorder


def main():
    agent = QwenAgent()

    def process_text(text):
        print(f"Transcribed: {text}")
        commands, reply = agent.ask(text)
        print(json.dumps(commands, indent=2))
        if reply:
            print(f"Reply: {reply}")

    print("Loading wake-word, VAD and Whisper models (please wait)...")
    recorder = PiRecorder(
        on_recording_start=lambda: print(">>> Speech detected, recording..."),
        on_recording_stop=lambda: print(">>> Silence detected, transcribing..."),
    )
    print("Ready. Say the wake word (hey jarvis), then your request.")

    try:
        while True:
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        recorder.shutdown()


if __name__ == '__main__':
    main()
