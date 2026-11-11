"""Command-line voice loop for trying the pipeline without ROS 2.

    wake word -> speech -> Whisper -> Qwen -> printed commands and reply

The ROS node (qwen_voice_manager/node.py) does the same with the real robot.
"""

import json


def handle_reply(reply):
    """Called with the human-facing reply text; here we just print it."""
    if reply:
        print(f"Reply: {reply}")


def main():
    from pi_recorder import PiRecorder
    from qwen_agent import QwenAgent

    agent = QwenAgent()

    def process_text(text):
        print(f"Transcribed: {text}")
        commands, reply = agent.ask(text)
        print(json.dumps(commands, indent=2))
        handle_reply(reply)

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
