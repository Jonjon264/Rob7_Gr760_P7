import json

import logging

def on_start():
    print(">>> [VAD] Speech detected! Recording...")

def on_stop():
    print(">>> [VAD] Silence detected! Transcribing...")


def create_recorder(**overrides):
    """Shared recorder configuration for this CLI and the ROS 2 voice node."""
    from RealtimeSTT import AudioToTextRecorder

    settings = dict(
        model="base.en",
        language="en",
        device="cpu",
        compute_type="int8",
        spinner=False,
        level=logging.ERROR,
        on_recording_start=on_start,
        on_recording_stop=on_stop,
        wakeword_backend="pvporcupine", # Uses built-in Porcupine engine
        wake_words="bumblebee",          # Free built-in keywords: "computer", "jarvis", "bumblebee", "alexa"
        # --- VAD Fix Parameters ---
        silero_sensitivity=0.3,              # Lowered (0.0 to 1.0) so room noise doesn't hold the mic open
        webrtc_sensitivity=1,                # Less aggressive (0=least sensitive, 3=most sensitive)
        silero_deactivity_detection=True,    # Uses Silero neural VAD instead of WebRTC to detect silence
        post_speech_silence_duration=0.8     # Seconds of silence required to stop recording
    )
    settings.update(overrides)
    return AudioToTextRecorder(**settings)


def main():
    from qwen_agent import QwenAgent

    agent = QwenAgent()

    def process_text(text):
        print(f"Transcribed: {text}")
        print(json.dumps(agent.ask(text), indent=2))
        with open("transcription.txt", "a", encoding="utf-8") as file:
            file.write(f"{text}\n")

    print("1. Loading Whisper and VAD models into memory (please wait)...")
    recorder = create_recorder()
    print("2. Models loaded! Speak into your microphone now...")

    try:
        while True:
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        recorder.shutdown()


if __name__ == '__main__':
    main()
