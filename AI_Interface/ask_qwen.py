import json
from qwen_agent import QwenAgent
import warnings
import logging
from RealtimeSTT import AudioToTextRecorder
import numpy as np
import sounddevice as sd
from piper import PiperVoice

# here we load the model that we get from piper (the one i chose)
voice = PiperVoice.load("en_US-hfc_male-medium.onnx")
#here we define what happenes when the user starts talking ie after the wake word has been detected
def on_start():
    print("Speech detected now recording")
#this is what happenes when we have detected a certain amount of silence after the user has finised talking
def on_stop():
    print("silence detected now transcibing")
#here the main bulk of the code is, we now process the transcribed text.
def process_text(text):
    print(f"Transcribed: {text}")
    #we then send it to our agent
    response_text = agent.ask(text)
    print(response_text)
    #we then send it to our agent and get the response back
    response_text = agent.ask(text)

    # now the audio part of the code comes into effect
    audio_bytes = b""
    #here the audio gets made into chunks and in a data format of audio_int16_bytes which is then converted into an array that sounddevice can read and play through the speakers
    for chunk in voice.synthesize(response_text):
        audio_bytes += chunk.audio_int16_bytes
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
    # then we play it through the speakers using sounddevice with the sample rate from the voice model from piper
    sd.play(audio_data, samplerate=voice.config.sample_rate)
    sd.wait()
    #here we are writing our transcriptions to a file we call transcription.txt so we can keep a record of transcriptions and responses 
    with open("transcriptionAndResponses.txt", "a", encoding="utf-8") as file:
        file.write(f"{text}\n") 
        file.write(f"{response_text}\n")

if __name__ == '__main__':
    #here we call the agent from qwen_agent.py and thus load it and vad into memory
    agent = QwenAgent()
    print("1. Loading Whisper and VAD models into memory (please wait)...")
    recorder = AudioToTextRecorder(
        #here the whisper model is chosen, we use the base model for english
        model="base.en",
        language="en",
        #here we use cuda for device and float32 this is so it runs on gpu.
        device="cuda",
        compute_type="float32",
        spinner=False,
        level=logging.ERROR,
        #here we call the function we talked about before.
        on_recording_start=on_start,
        on_recording_stop=on_stop,
        #here we choose the wake word engine and the wake workd itself, we use picovoice porcupine
        wakeword_backend="pvporcupine", 
        wake_words="computer",          #there are some free wakewords such as "computer", "jarvis", "bumblebee", "alexa" picovoice lets us use
        # --- VAD Fix Parameters ---
        #here we initialize the Voice activity detection parameters.
        silero_sensitivity=0.3,              # Lowered value so room noise doesn't hold the mic open
        webrtc_sensitivity=1,                # Less aggressive (0=least sensitive, 3=most sensitive)
        silero_deactivity_detection=True,    # here we use Silero neural VAD to detect silence
        post_speech_silence_duration=0.8     # how many seconds of silence that is required in odre to stop recording
    )
    print("2. Models loaded! Speak into your microphone now...")
    
    try:
        while True:
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("\nExiting...")
        recorder.shutdown()