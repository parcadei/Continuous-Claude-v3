"""
Claude LLM wrapper for PageIndex.

Routes LLM calls through Claude Code CLI (preferred) or Anthropic SDK (fallback).
CLI uses sonnet-4.5, API uses haiku-4.5 for cost efficiency.
"""
import subprocess
import json
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Model IDs for Anthropic API (used when CLI not available)
API_MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",    # Claude Haiku 4.5
    "sonnet": "claude-sonnet-4-5-20250929",  # Claude Sonnet 4.5
    "opus": "claude-opus-4-20250514",        # Claude Opus 4
}

# Model names for Claude CLI
CLI_MODEL_MAP = {
    "haiku": "haiku",    # Maps to latest haiku
    "sonnet": "sonnet",  # Maps to sonnet-4.5
    "opus": "opus",      # Maps to latest opus
}

# Default models for each backend
CLI_DEFAULT_MODEL = "sonnet"   # CLI uses sonnet-4.5 (better quality)
API_DEFAULT_MODEL = "haiku"    # API uses haiku-4.5 (cost efficient)


def _anthropic_sdk_call(prompt: str, model: str, api_key: str) -> str:
    """Call Anthropic API directly using SDK."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    model_id = API_MODEL_MAP.get(model, API_MODEL_MAP[API_DEFAULT_MODEL])

    message = client.messages.create(
        model=model_id,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


async def _anthropic_sdk_call_async(prompt: str, model: str, api_key: str) -> str:
    """Async version of Anthropic SDK call."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    model_id = API_MODEL_MAP.get(model, API_MODEL_MAP[API_DEFAULT_MODEL])

    message = await client.messages.create(
        model=model_id,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def _cli_call(prompt: str, model: str) -> str:
    """Call Claude Code CLI - uses existing subscription."""
    cli_model = CLI_MODEL_MAP.get(model, CLI_DEFAULT_MODEL)

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--model", cli_model],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            logger.error(f"Claude CLI call failed: {result.stderr}")
            raise RuntimeError(f"Claude CLI call failed: {result.stderr}")

        response = json.loads(result.stdout)
        return response.get("result", "")
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI call timed out")
        raise RuntimeError("Claude CLI call timed out after 120 seconds")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude CLI response: {e}")
        raise RuntimeError(f"Failed to parse Claude CLI response: {e}")


async def _cli_call_async(prompt: str, model: str) -> str:
    """Async version using asyncio subprocess."""
    cli_model = CLI_MODEL_MAP.get(model, CLI_DEFAULT_MODEL)

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt, "--output-format", "json", "--model", cli_model,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error(f"Claude CLI call failed: {stderr.decode()}")
            raise RuntimeError(f"Claude CLI call failed: {stderr.decode()}")

        response = json.loads(stdout.decode())
        return response.get("result", "")
    except asyncio.TimeoutError:
        logger.error("Claude CLI async call timed out")
        raise RuntimeError("Claude CLI call timed out after 120 seconds")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude CLI response: {e}")
        raise RuntimeError(f"Failed to parse Claude CLI response: {e}")


def _cli_available() -> bool:
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def claude_complete(prompt: str, model: str = "sonnet", prefer_api: bool = False) -> str:
    """
    Call Claude - CLI first (sonnet-4.5), API fallback (haiku-4.5).

    Args:
        prompt: The prompt to send to Claude
        model: Model tier to use (haiku, sonnet, opus)
        prefer_api: If True, use API first instead of CLI

    Returns:
        The model's response text
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if prefer_api and api_key:
        # API preferred
        logger.debug(f"Using Anthropic API with model {model}")
        return _anthropic_sdk_call(prompt, model, api_key)
    elif _cli_available():
        # CLI primary (default)
        logger.debug(f"Using Claude CLI with model {model}")
        return _cli_call(prompt, model)
    elif api_key:
        # API fallback
        logger.debug(f"CLI not available, falling back to API with model {model}")
        return _anthropic_sdk_call(prompt, model, api_key)
    else:
        raise RuntimeError("Neither Claude CLI nor ANTHROPIC_API_KEY available")


async def claude_complete_async(prompt: str, model: str = "sonnet", prefer_api: bool = False) -> str:
    """
    Async version - CLI first (sonnet-4.5), API fallback (haiku-4.5).

    Args:
        prompt: The prompt to send to Claude
        model: Model tier to use (haiku, sonnet, opus)
        prefer_api: If True, use API first instead of CLI

    Returns:
        The model's response text
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if prefer_api and api_key:
        logger.debug(f"Using Anthropic API (async) with model {model}")
        return await _anthropic_sdk_call_async(prompt, model, api_key)
    elif _cli_available():
        logger.debug(f"Using Claude CLI (async) with model {model}")
        return await _cli_call_async(prompt, model)
    elif api_key:
        logger.debug(f"CLI not available, falling back to API (async) with model {model}")
        return await _anthropic_sdk_call_async(prompt, model, api_key)
    else:
        raise RuntimeError("Neither Claude CLI nor ANTHROPIC_API_KEY available")


def map_openai_model_to_claude(model: str) -> str:
    """Map OpenAI model names to Claude equivalents."""
    if "gpt-4" in model.lower() or "o1" in model.lower():
        return "sonnet"
    elif "gpt-3.5" in model.lower():
        return "haiku"
    else:
        return "sonnet"


class ClaudeLLMAdapter:
    """
    Drop-in replacement for OpenAI client that routes to Claude.

    Uses Claude CLI (sonnet-4.5) by default, falls back to API (haiku-4.5).

    Usage:
        adapter = ClaudeLLMAdapter()
        response = adapter.chat_complete(model="gpt-4", prompt="Hello")
    """

    def __init__(self, default_model: str = "sonnet", prefer_api: bool = False):
        self.default_model = default_model
        self.prefer_api = prefer_api

    def chat_complete(
        self,
        model: str,
        prompt: str,
        chat_history: Optional[list] = None,
        temperature: float = 0
    ) -> str:
        """
        Synchronous chat completion.

        Args:
            model: OpenAI model name (will be mapped to Claude)
            prompt: User prompt
            chat_history: Optional conversation history (formatted into prompt)
            temperature: Ignored (using default)

        Returns:
            Model response text
        """
        claude_model = map_openai_model_to_claude(model)

        if chat_history:
            formatted_history = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in chat_history
            ])
            full_prompt = f"{formatted_history}\nUSER: {prompt}"
        else:
            full_prompt = prompt

        return claude_complete(full_prompt, model=claude_model, prefer_api=self.prefer_api)

    async def chat_complete_async(
        self,
        model: str,
        prompt: str,
        chat_history: Optional[list] = None,
        temperature: float = 0
    ) -> str:
        """Async version of chat_complete."""
        claude_model = map_openai_model_to_claude(model)

        if chat_history:
            formatted_history = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in chat_history
            ])
            full_prompt = f"{formatted_history}\nUSER: {prompt}"
        else:
            full_prompt = prompt

        return await claude_complete_async(full_prompt, model=claude_model, prefer_api=self.prefer_api)
