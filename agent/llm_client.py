"""OpenAI-compatible LLM client with tool/function calling support."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


class LLMClient:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and configure your API key."
            )

        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = os.getenv("OPENAI_MODEL", "")
        if not self.model:
            self.model = (
                "deepseek-v4-flash"
                if "deepseek" in base_url.lower()
                else "gpt-4o-mini"
            )
        print(f"[LLM] base_url={base_url}  model={self.model}")

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0")),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            err = str(exc)
            if "invalid_request_error" in err and "model" in err.lower():
                raise ValueError(
                    f"LLM model rejected by API ({self.model}). "
                    f"Check OPENAI_MODEL in .env matches your provider."
                ) from exc
            raise
        message = response.choices[0].message

        result: dict[str, Any] = {
            "content": message.content,
            "tool_calls": [],
        }

        if message.tool_calls:
            for call in message.tool_calls:
                result["tool_calls"].append(
                    {
                        "id": call.id,
                        "name": call.function.name,
                        "arguments": json.loads(call.function.arguments),
                    }
                )

        return result
