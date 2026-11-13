# qwen_voice_manager

Speech/text -> Qwen -> validated JSON on `manager/commands` (consumed by `robot_task_handler`).
Prompt and places live in `ros2_ws/config/` (`rules.txt`, `map.json`).

## Code layout (`qwen_voice_manager/`)
| File | Class / role |
|---|---|
| `node.py` | `VoiceManager` ROS node: wires everything together, handles "stop" |
| `agent.py` | `QwenAgent`: sends text to Qwen, returns validated commands + reply |
| `validation.py` | checks the model's JSON (reach/teach lists, cancel/continue/error) |
| `recorder.py` | `PiRecorder`: wake word + VAD + Whisper speech to text |
| `speaker.py` | `ReplyPlayer`: Piper text to speech on a worker thread |
| `cli.py` | `ask_qwen` command: same pipeline without ROS |

## Input / output
| | |
|---|---|
| In | wake word (`hey_jarvis`) + speech, or text on `manager/text` (String) |
| Out | `manager/commands` (String, JSON; see robot_task_handler/README.md), `manager/transcripts` (String), spoken reply (Piper TTS) |

Qwen outputs: a task list of `reach`/`teach`, or a standalone `cancel`, `continue` ("I have taken the package") or `error`.
Every object also has a `reply` (spoken text); it is stripped before validation and never reaches ROS.
Typing exactly "stop"/"cancel"/"abort" cancels instantly without asking the model.

## Parameters
| Name | Default |
|---|---|
| `base_url` | `''` (agent default endpoint; change when the tunnel URL changes) |
| `model` | `qwen3-vl` |
| `request_timeout` | `30.0` s |
| `map_file`, `rules_file` | `~/ros2_ws/config/{map.json,rules.txt}` |
| `command_topic`, `text_topic`, `transcript_topic` | `manager/commands`, `manager/text`, `manager/transcripts` |
| `speech_enabled`, `speech_model`, `wake_words`, `input_device_index` | `true`, `base.en`, `hey_jarvis`, `-1` (default mic) |
| `tts_enabled`, `tts_model`, `output_device_index` | `true`, Piper model path, `-1` |

Env var `QWEN_API_KEY` overrides the API key. `rules.txt` and `map.json` are re-read on every request.
Default reach wait is 5 s (set in `rules.txt`); `wait_time` max 32767.
