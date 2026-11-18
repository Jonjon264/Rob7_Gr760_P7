
"""
QwenAgent: image input -> Qwen -> JSON response.

Flow:
1. Load rules.txt at startup.
2. Load reference images from four folders.
3. Encode and store reference images in memory.
4. Receive a new JPG image through ask().
5. Send the image and reference context to Qwen.
6. Return Qwen's JSON response.
"""

import base64
import mimetypes
import os
import json

from pathlib import Path
from openai import OpenAI

from . import DEFAULT_CONFIG_DIR


DEFAULT_BASE_URL = "LINK_ON_GOD"
DEFAULT_API_KEY = "API_KEY_TRUST" 
MAX_TOKENS = 265000
MODEL = "qwen3-vl"


class QwenAgent:

    def __init__(self):

        # Initialize Qwen client
        self.client = OpenAI(
            base_url=DEFAULT_BASE_URL,
            api_key=DEFAULT_API_KEY,
        )

        self.model = MODEL

        # Define paths
        self.people_dir = DEFAULT_CONFIG_DIR / "people"
        self.rules_file = DEFAULT_CONFIG_DIR / "rules.txt"

        # Load rules
        with open(self.rules_file, "r", encoding="utf-8") as file:
            self.rules = file.read()

        # Load reference images at startup
        self.people_images = self.load_image_folder(
            self.people_dir
        )

        # Build reference context
        self.reference_context = self.build_reference_context()

        print("QwenAgent initialized.")

        for folder, images in self.people_images.items():
            print(f"  {folder}: {len(images)} images")

    # --------------------------------------------------
    # Encode reference images from disk
    # --------------------------------------------------

    @staticmethod
    def encode_reference_image(image_path):

        mime_type, _ = mimetypes.guess_type(image_path)

        with open(image_path, "rb") as file:
            encoded = base64.b64encode(
                file.read()
            ).decode("utf-8")

        return f"data:{mime_type};base64,{encoded}"

    # --------------------------------------------------
    # Encode incoming JPG bytes
    # --------------------------------------------------

    @staticmethod
    def encode_input_image(image):

        encoded = base64.b64encode(
            image
        ).decode("utf-8")

        return f"data:image/jpeg;base64,{encoded}"

    # --------------------------------------------------
    # Load reference image folders
    # --------------------------------------------------

    def load_image_folder(self, folder):

        locations = {}

        for location_folder in sorted(folder.iterdir()):

            if not location_folder.is_dir():
                continue

            images = []

            for image_path in sorted(location_folder.iterdir()):

                if image_path.suffix.lower() not in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ]:
                    continue

                images.append({
                    "path": image_path,
                    "data": self.encode_reference_image(image_path)
                })

            if images:
                locations[location_folder.name] = images

        return locations

    # --------------------------------------------------
    # Build reference context
    # --------------------------------------------------

    def build_reference_context(self):

        content = [
            {
                "type": "text",
                "text": (
                    "The following are reference images of people "
                    "organized into categories.\n"
                    "Each category is identified by its folder name.\n"
                    "Use these images as visual context when "
                    "identifying people in future input images."
                )
            }
        ]

        for folder_name, images in self.people_images.items():

            content.append({
                "type": "text",
                "text": f"Reference category: {folder_name}"
            })

            for image in images:

                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image["data"]
                    }
                })

        return content

    # --------------------------------------------------
    # System prompt
    # --------------------------------------------------

    def system_prompt(self):

        return (
            self.rules
            + "\n\n"
            + "Use the reference images to identify people in new images. "
            + "Return your answer ONLY as valid JSON with a boolean for the identification, "
            "and a string to tell the person to get their package."
        )

    # --------------------------------------------------
    # Ask Qwen
    # --------------------------------------------------

    def ask(self, prompt, image):

        encoded_image = self.encode_input_image(image)

        messages = [
            {
                "role": "system",
                "content": self.system_prompt()
            },
            {
                "role": "user",
                "content": self.reference_context
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"This is the prompt: {prompt}\n"
                             "Does the person in the image match the name referenced in the prompt?\n"
                             "If yes, return a JSON object with a boolean 'match' set to true and a string "
                             "'message' telling the person to get their package.\n"
                             "If no, return a JSON object with 'match' set to false and a string 'message' "
                             "telling the mentioned person to step into frame."

                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": encoded_image
                        }
                    }
                ]
            }
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            max_tokens=MAX_TOKENS,
            stream=False,
        )

        result = response.choices[0].message.content

        return json.loads(result)
