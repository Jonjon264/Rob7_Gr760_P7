import json
import math
import os
import re
from pathlib import Path
from openai import OpenAI

HERE = Path(__file__).parent
MAP_FILE = HERE.parent / "config" / "map.json"
RULES_FILE = HERE.parent / "config" / "rules.txt"

ACTIONS = {"reach", "teach", "wait", "cancel"}


def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return json.loads(text)


def validate(cmd, map_data):
    if isinstance(cmd, list):
        if not cmd:
            raise ValueError("task list must not be empty")
        for task in cmd:
            validate_task(task, map_data)
        return cmd
    if not isinstance(cmd, dict):
        raise ValueError("output must be a task list or a standalone cancel/error object")
    action = cmd.get("action")
    if action == "error":
        if set(cmd) != {"action", "message"} or not isinstance(cmd["message"], str) or not cmd["message"].strip():
            raise ValueError("error requires only action and a non-empty message")
        return cmd
    if action == "cancel" and set(cmd) == {"action"}:
        return cmd
    raise ValueError("only cancel and error may be standalone objects; use a list for tasks")


def validate_task(cmd, map_data):
    if not isinstance(cmd, dict):
        raise ValueError("each task must be a JSON object")
    action = cmd.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError(f"unknown action: {action}")
    if action == "cancel":
        raise ValueError("cancel must be a standalone interrupt outside the task list")
    expected_fields = {
        "reach": {"action", "destination"},
        "teach": {"action"},
        "wait": {"action", "duration_seconds"},
    }[action]
    if set(cmd) != expected_fields:
        raise ValueError(f"{action} requires exactly these fields: {sorted(expected_fields)}")
    if action == "reach":
        dest = cmd["destination"]
        known = [{"name": p["name"], "x": p["x"], "y": p["y"]} for p in map_data]
        if (
            not isinstance(dest, dict)
            or set(dest) != {"name", "x", "y"}
            or type(dest["x"]) not in (int, float)
            or type(dest["y"]) not in (int, float)
            or dest not in known
        ):
            raise ValueError(f"destination is not on map: {dest}")
    elif action == "wait":
        duration = cmd["duration_seconds"]
        if type(duration) not in (int, float) or duration <= 0 or (
            isinstance(duration, float) and not math.isfinite(duration)
        ):
            raise ValueError("duration_seconds must be a positive finite number")
    return cmd


class QwenAgent:
    def __init__(
        self,
        base_url="https://circuit-eric-certificates-donation.trycloudflare.com/v1",
        api_key="4o5p5BXmiHPc5_RmWKnY7eAkdpSsnEpb37PQYSJiSDU",
        model="qwen3-vl",
        retries=1,
        map_file=None,
        rules_file=None,
        timeout=180,
    ):
        self.client = OpenAI(base_url=base_url, api_key=os.environ.get("QWEN_API_KEY", api_key), timeout=timeout)
        self.model = model
        self.retries = retries
        self.map_file = Path(map_file) if map_file else MAP_FILE
        self.rules_file = Path(rules_file) if rules_file else RULES_FILE

    def _system_prompt(self, map_data):
        rules = self.rules_file.read_text(encoding="utf-8-sig")
        return (
            rules.replace("{map}", json.dumps(map_data, indent=2))
            .replace("{actions}", str(sorted(ACTIONS)))
        )

    def _complete(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=265000,
            temperature=0,
            stream=False,
        )
        return response.choices[0].message.content

    def ask(self, text):
        """Return a validated task list or standalone cancel/error object."""
        # re-read both files on every call so edits from other scripts apply immediately
        map_data = json.loads(self.map_file.read_text(encoding="utf-8-sig"))
        messages = [
            {"role": "system", "content": self._system_prompt(map_data)},
            {"role": "user", "content": text},
        ]
        error = None
        for _ in range(self.retries + 1):
            reply = self._complete(messages)
            try:
                return validate(parse_json(reply), map_data)
            except (ValueError, KeyError, AttributeError) as e:
                error = e
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"Invalid output ({e}). Reply again with valid JSON only, following the rules."},
                ]
        return {"action": "error", "message": f"invalid model output: {error}"}
