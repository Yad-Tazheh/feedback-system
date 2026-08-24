import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


class AIService:

    def __init__(self):
        self.url = os.getenv("LM_STUDIO_URL")
        self.model = os.getenv("LM_MODEL")
        self.temperature = float(os.getenv("LM_TEMPERATURE", 0.4))
        self.max_tokens = int(os.getenv("LM_MAX_TOKENS", 150))

        self.system_prompt = self.load_prompt()

    def load_prompt(self):
        base_dir = Path(__file__).resolve().parent.parent.parent

        prompt_path = base_dir / "config" / "prompts" / "feedback_response.txt"

        with open(prompt_path, "r", encoding="utf-8") as file:
            return file.read()

    def generate(self, user_message):

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        response = requests.post(
            self.url,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]