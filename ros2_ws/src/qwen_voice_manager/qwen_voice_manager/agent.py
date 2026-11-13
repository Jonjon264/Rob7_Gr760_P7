"""QwenAgent: one spoken sentence in, validated robot commands out.

Flow: text -> Qwen (rules.txt + map.json as system prompt) -> JSON -> validation.
Only validated JSON ever leaves the agent. The spoken "reply" is split off first
so it can never influence what the robot does.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

from . import DEFAULT_CONFIG_DIR
from .validation import ACTIONS, parse_json, split_reply, validate

DEFAULT_BASE_URL = "https://silk-band-magazines-accessories.trycloudflare.com/v1"
DEFAULT_API_KEY = "4o5p5BXmiHPc5_RmWKnY7eAkdpSsnEpb37PQYSJiSDU"  # QWEN_API_KEY env var overrides
MAX_TOKENS = 265000


class QwenAgent:
    def __init__(
        self,
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        model="qwen3-vl",
        retries=1,        # extra attempts after an invalid answer
        map_file=None,
        rules_file=None,
        timeout=180,      # seconds per model request
    ):
        self.client = OpenAI(base_url=base_url, api_key=os.environ.get("QWEN_API_KEY", api_key), timeout=timeout)
        self.model = model
        self.retries = retries
        self.map_file = Path(map_file) if map_file else DEFAULT_CONFIG_DIR / "map.json"
        self.rules_file = Path(rules_file) if rules_file else DEFAULT_CONFIG_DIR / "rules.txt"

    def _system_prompt(self, map_data):
        """Fill the {map} and {actions} placeholders of rules.txt."""
        rules = self.rules_file.read_text(encoding="utf-8-sig")
        return (
            rules.replace("{map}", json.dumps(map_data, indent=2))
            .replace("{actions}", str(sorted(ACTIONS)))
        )

    def _complete(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=0,
            stream=False,
            # Qwen3 "thinks" for many seconds before answering by default; the rules
            # already force a short JSON answer, so skip it. Servers that don't know
            # this option ignore it.
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return response.choices[0].message.content

    def ask(self, text):
        """Return (validated commands, spoken reply) for one user sentence.

        On repeated invalid model output the commands are an "error" object.
        """
        # Re-read both files on every call so edits (e.g. teach) apply immediately.
        map_data = json.loads(self.map_file.read_text(encoding="utf-8-sig"))
        messages = [
            {"role": "system", "content": self._system_prompt(map_data)},
            {"role": "user", "content": text},
        ]
        error = None
        for _ in range(self.retries + 1):
            reply = self._complete(messages)
            try:
                commands, spoken = split_reply(parse_json(reply))
                return validate(commands, map_data), spoken
            except (ValueError, KeyError, AttributeError) as e:
                error = e
                # Show the model its mistake and let it try again.
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"Invalid output ({e}). Reply again with valid JSON only, following the rules."},
                ]
        return (
            {"action": "error", "message": f"invalid model output: {error}"},
            "I could not understand that request.",
        )
