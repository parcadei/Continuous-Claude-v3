"""Simple Fireworks AI inference client.

OpenAI-compatible API for fast LLM inference.

Usage:
    llm = LLM()
    response = await llm.chat("Hello!")

    # With function calling
    result = await llm.call_function(
        "What's 2+2?",
        functions=[{"name": "calculate", ...}]
    )
"""

import os
import json
from typing import Any, AsyncIterator

import httpx


class LLM:
    """Minimal Fireworks AI client."""

    BASE_URL = "https://api.fireworks.ai/inference/v1"

    # Available models
    MODELS = {
        "fast": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "smart": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "best": "accounts/fireworks/models/qwen2p5-72b-instruct",
        "deepseek": "accounts/fireworks/models/deepseek-v3",
    }

    def __init__(
        self,
        model: str = "fast",
        api_key: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("FIREWORKS_API_KEY")
        self.model = self.MODELS.get(model, model)
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        message: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Simple chat completion."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        response = await self._call_api(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        message: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        async with self._client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

    async def call_function(
        self,
        message: str,
        functions: list[dict[str, Any]],
        system: str | None = None,
    ) -> dict[str, Any]:
        """Function calling / tool use.

        Returns the function call result with name and arguments.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        # Convert to OpenAI tools format
        tools = [
            {"type": "function", "function": f}
            for f in functions
        ]

        response = await self._call_api(
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response["choices"][0]["message"]

        if msg.get("tool_calls"):
            call = msg["tool_calls"][0]
            return {
                "name": call["function"]["name"],
                "arguments": json.loads(call["function"]["arguments"]),
            }

        # No function called, return content
        return {"content": msg.get("content", "")}

    async def _call_api(self, **kwargs) -> dict:
        """Make API call."""
        if not self.api_key:
            raise ValueError("FIREWORKS_API_KEY required")

        payload = {
            "model": self.model,
            **kwargs,
        }

        response = await self._client.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()


# Quick test
async def _test():
    llm = LLM()

    # Test simple chat
    print("Testing chat...")
    response = await llm.chat("Say 'Hello, hackathon!' in exactly 3 words.")
    print(f"Response: {response}")

    # Test function calling
    print("\nTesting function calling...")
    result = await llm.call_function(
        "What's the weather in San Francisco?",
        functions=[{
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        }],
    )
    print(f"Function call: {result}")

    await llm.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
