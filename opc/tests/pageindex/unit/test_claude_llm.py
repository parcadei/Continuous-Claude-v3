"""Unit tests for Claude LLM adapter."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.pageindex.claude_llm import (
    claude_complete,
    claude_complete_async,
    map_openai_model_to_claude,
    ClaudeLLMAdapter,
)


@pytest.mark.unit
class TestMapOpenAIModelToClaude:
    def test_gpt4_maps_to_sonnet(self):
        assert map_openai_model_to_claude("gpt-4") == "sonnet"
        assert map_openai_model_to_claude("gpt-4-turbo") == "sonnet"
        assert map_openai_model_to_claude("GPT-4") == "sonnet"

    def test_gpt35_maps_to_haiku(self):
        assert map_openai_model_to_claude("gpt-3.5-turbo") == "haiku"

    def test_o1_maps_to_sonnet(self):
        assert map_openai_model_to_claude("o1-preview") == "sonnet"
        assert map_openai_model_to_claude("o1-mini") == "sonnet"

    def test_unknown_defaults_to_sonnet(self):
        assert map_openai_model_to_claude("unknown-model") == "sonnet"
        assert map_openai_model_to_claude("") == "sonnet"


@pytest.mark.unit
class TestClaudeComplete:
    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call")
    def test_successful_call(self, mock_cli_call, mock_cli_available):
        mock_cli_call.return_value = "Hello, world!"

        result = claude_complete("Say hello", model="sonnet")

        assert result == "Hello, world!"
        mock_cli_call.assert_called_once_with("Say hello", "sonnet")

    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call")
    def test_failed_call_raises(self, mock_cli_call, mock_cli_available):
        mock_cli_call.side_effect = RuntimeError("Claude CLI call failed: Error")

        with pytest.raises(RuntimeError, match="Claude CLI call failed"):
            claude_complete("Test prompt")

    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call")
    def test_timeout_raises(self, mock_cli_call, mock_cli_available):
        mock_cli_call.side_effect = RuntimeError("Claude CLI call timed out")

        with pytest.raises(RuntimeError, match="timed out"):
            claude_complete("Test prompt")

    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call")
    def test_invalid_json_raises(self, mock_cli_call, mock_cli_available):
        mock_cli_call.side_effect = RuntimeError("Failed to parse Claude CLI response")

        with pytest.raises(RuntimeError, match="Failed to parse"):
            claude_complete("Test prompt")

    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call")
    def test_uses_correct_model(self, mock_cli_call, mock_cli_available):
        mock_cli_call.return_value = "ok"

        claude_complete("Test", model="haiku")

        mock_cli_call.assert_called_once_with("Test", "haiku")

    @patch("scripts.pageindex.claude_llm._cli_available", return_value=False)
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("scripts.pageindex.claude_llm._anthropic_sdk_call")
    def test_falls_back_to_api(self, mock_api_call, mock_cli_available):
        mock_api_call.return_value = "API response"

        result = claude_complete("Test")

        assert result == "API response"
        mock_api_call.assert_called_once()


@pytest.mark.unit
class TestClaudeCompleteAsync:
    @pytest.mark.asyncio
    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call_async")
    async def test_successful_async_call(self, mock_cli_call_async, mock_cli_available):
        mock_cli_call_async.return_value = "Async hello!"

        result = await claude_complete_async("Say hello async", model="sonnet")

        assert result == "Async hello!"

    @pytest.mark.asyncio
    @patch("scripts.pageindex.claude_llm._cli_available", return_value=True)
    @patch("scripts.pageindex.claude_llm._cli_call_async")
    async def test_async_timeout_raises(self, mock_cli_call_async, mock_cli_available):
        mock_cli_call_async.side_effect = RuntimeError("Claude CLI call timed out")

        with pytest.raises(RuntimeError, match="timed out"):
            await claude_complete_async("Test")


@pytest.mark.unit
class TestClaudeLLMAdapter:
    def test_init_with_default_model(self):
        adapter = ClaudeLLMAdapter()
        assert adapter.default_model == "sonnet"  # Default is sonnet for CLI

    def test_init_with_custom_model(self):
        adapter = ClaudeLLMAdapter(default_model="haiku")
        assert adapter.default_model == "haiku"

    def test_init_with_prefer_api(self):
        adapter = ClaudeLLMAdapter(prefer_api=True)
        assert adapter.prefer_api is True

    @patch("scripts.pageindex.claude_llm.claude_complete")
    def test_chat_complete_without_history(self, mock_complete):
        mock_complete.return_value = "Response text"

        adapter = ClaudeLLMAdapter()
        result = adapter.chat_complete(model="gpt-4", prompt="Hello")

        assert result == "Response text"
        mock_complete.assert_called_once_with("Hello", model="sonnet", prefer_api=False)

    @patch("scripts.pageindex.claude_llm.claude_complete")
    def test_chat_complete_with_history(self, mock_complete):
        mock_complete.return_value = "Response"

        adapter = ClaudeLLMAdapter()
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        adapter.chat_complete(model="gpt-4", prompt="New question", chat_history=history)

        call_prompt = mock_complete.call_args[0][0]
        assert "USER: Previous question" in call_prompt
        assert "ASSISTANT: Previous answer" in call_prompt
        assert "USER: New question" in call_prompt

    @pytest.mark.asyncio
    @patch("scripts.pageindex.claude_llm.claude_complete_async")
    async def test_chat_complete_async(self, mock_complete_async):
        mock_complete_async.return_value = "Async response"

        adapter = ClaudeLLMAdapter()
        result = await adapter.chat_complete_async(model="gpt-4", prompt="Hello async")

        assert result == "Async response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
