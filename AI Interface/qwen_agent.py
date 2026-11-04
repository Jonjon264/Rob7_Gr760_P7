import json
import re
from pathlib import Path
from openai import OpenAI

HERE = Path(__file__).parent
MAP_FILE = HERE / "map.json"
RULES_FILE = HERE / "rules.txt"

ACTIONS = {"navigate"}


def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("no JSON object in reply")
    return json.loads(match.group(0))


def validate(cmd, map_data):
    if cmd.get("action") == "error":
        return cmd
        
    if cmd.get("action") not in ACTIONS:
        raise ValueError(f"unknown action: {cmd.get('action')}")
    dest = cmd.get("destination", {})
    if dest not in [{"name": p["name"], "x": p["x"], "y": p["y"]} for p in map_data]:
        raise ValueError(f"destination not on map: {dest}")
        #here we will add sending a message to the debug topic/user so they can retry with another command 
    return cmd


class QwenAgent:
    def __init__(
        self,
        base_url="https://circuit-eric-certificates-donation.trycloudflare.com/v1",
        api_key="4o5p5BXmiHPc5_RmWKnY7eAkdpSsnEpb37PQYSJiSDU",
        model="qwen3-vl",
        retries=1,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=180)
        self.model = model
        self.retries = retries

    def _system_prompt(self, map_data):
        rules = RULES_FILE.read_text(encoding="utf-8")
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
        """Send one request, return a validated command dict. Never raises on bad model output."""
        # re-read both files on every call so edits from other scripts apply immediately
        map_data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
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
        return reply
