from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
import requests

load_dotenv()


class AIServiceError(Exception):
    """Raised when an error occurs while communicating with the AI service."""
    pass


@dataclass
class AIResult:
    content: str
    model: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    cached_tokens: Optional[int]
    total_tokens: Optional[int]
    raw_usage: Optional[dict[str, Any]]


class AIService:

    def __init__(self):
        self.url = os.getenv("LM_STUDIO_URL")
        self.model = os.getenv("LM_MODEL")
        try:
            self.temperature = float(os.getenv("LM_TEMPERATURE", 0.4))
        except (ValueError, TypeError):
            self.temperature = 0.4

        try:
            self.max_tokens = int(os.getenv("LM_MAX_TOKENS", 150))
        except (ValueError, TypeError):
            self.max_tokens = 150

        try:
            self.timeout = float(os.getenv("LM_TIMEOUT", 60))
        except (ValueError, TypeError):
            self.timeout = 60.0

        self.system_prompt = self.load_prompt()

    def load_prompt(self):
        base_dir = Path(__file__).resolve().parent.parent.parent
        prompt_path = base_dir / "config" / "prompts" / "feedback_response.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as file:
                return file.read()
        except OSError:
            return ""

    def generate(self, messages):
        if not self.url or not self.model:
            raise AIServiceError("LM_STUDIO_URL and LM_MODEL must be configured.")

        if isinstance(messages, str):
            msg_list = [{"role": "user", "content": messages}]
        else:
            msg_list = list(messages)

        full_messages = [{"role": "system", "content": self.system_prompt}] + msg_list

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AIServiceError(f"Request to AI service failed: {exc}") from exc

        try:
            data = response.json()
            if not isinstance(data, dict):
                raise TypeError("Response root must be a dictionary")
            choices = data["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIServiceError(f"Malformed response from AI service: {exc}") from exc

        model = data.get("model")
        raw_usage = data.get("usage")

        prompt_tokens = None
        completion_tokens = None
        cached_tokens = None
        total_tokens = None

        if isinstance(raw_usage, dict):
            prompt_tokens = raw_usage.get("prompt_tokens")
            completion_tokens = raw_usage.get("completion_tokens")
            total_tokens = raw_usage.get("total_tokens")

            details = raw_usage.get("prompt_tokens_details")
            if isinstance(details, dict):
                cached_tokens = details.get("cached_tokens")
        else:
            raw_usage = None

        return AIResult(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            raw_usage=raw_usage,
        )
