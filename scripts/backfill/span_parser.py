"""Parse Braintrust spans into structured facts.

Extracts key facts from tool calls, LLM responses, and metadata.

Key facts extracted:
- file_read: From Read tool spans
- file_written: From Write tool spans
- test_result: From Bash spans with pytest output
- agent_spawned: From Task tool spans
- tokens_used: From LLM spans
- skill_activated: From metadata.skill_name

SEMANTIC facts extracted (for embedding-based recall):
- llm_response: Claude's reasoning/response content (truncated)
- user_message: User's input message from Task spans
- agent_output: Agent summary from Task output
- bash_output: Command output for debugging context

IMPORTANT: tool_name is in metadata, NOT span_attributes.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SpanFact:
    """A single fact extracted from a span."""

    key: str
    value: str
    turn: int
    span_id: str | None = None
    content_hash: str | None = None  # For deduplication
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None


class SpanParser:
    """Extract structured facts from Braintrust spans."""

    # Regex patterns for test result detection
    PYTEST_PATTERN = re.compile(r"(\d+)\s+passed.*?(\d+)\s+failed", re.IGNORECASE)
    PYTEST_PASS_ONLY = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
    PYTEST_FAIL_ONLY = re.compile(r"(\d+)\s+failed", re.IGNORECASE)

    # Max chars for semantic content (keeps embeddings meaningful)
    MAX_CONTENT_LENGTH = 2000

    def parse_span(self, span: dict[str, Any] | None, turn: int) -> list[SpanFact]:
        """Extract facts from a single span.

        Handles:
        - tool spans (Read, Write, Bash, Task, etc.)
        - llm spans (token counts)
        - skill activations

        Args:
            span: The span dictionary from Braintrust
            turn: The turn number this span belongs to

        Returns:
            List of SpanFact objects extracted from the span
        """
        if not span or not isinstance(span, dict):
            return []

        try:
            span_attrs = span.get("span_attributes", {})
            span_type = span_attrs.get("type", "")

            facts: list[SpanFact] = []

            if span_type == "tool":
                facts.extend(self._parse_tool_span(span, turn))
            elif span_type == "llm":
                facts.extend(self._parse_llm_span(span, turn))

            # Check for skill activation in any span type
            skill_facts = self._parse_skill_activation(span, turn)
            facts.extend(skill_facts)

            # Compute content hashes for deduplication
            for fact in facts:
                if fact.content_hash is None:
                    fact.content_hash = self._compute_content_hash(fact)

            return facts

        except Exception:
            # Malformed span - return empty list
            return []

    def _parse_tool_span(self, span: dict[str, Any], turn: int) -> list[SpanFact]:
        """Parse tool-type span.

        IMPORTANT: tool_name is in metadata, NOT span_attributes.
        """
        facts: list[SpanFact] = []
        span_id = span.get("span_id")
        metadata = span.get("metadata", {}) or {}
        tool_name = metadata.get("tool_name", "")

        # Parse input JSON
        input_str = span.get("input", "")
        input_data = self._parse_json_safe(input_str)

        output_str = span.get("output", "")

        if tool_name == "Read":
            facts.extend(self._parse_read_span(span_id, input_data, turn))
        elif tool_name == "Write":
            facts.extend(self._parse_write_span(span_id, input_data, turn))
        elif tool_name == "Bash":
            facts.extend(self._parse_bash_span(span_id, input_data, output_str, turn))
        elif tool_name == "Task":
            facts.extend(
                self._parse_task_span(span_id, metadata, input_data, turn, output_str)
            )

        return facts

    def _parse_read_span(
        self, span_id: str | None, input_data: dict[str, Any], turn: int
    ) -> list[SpanFact]:
        """Extract facts from Read tool span."""
        facts: list[SpanFact] = []
        file_path = input_data.get("file_path", "")

        if file_path:
            facts.append(
                SpanFact(
                    key="file_read",
                    value=file_path,
                    turn=turn,
                    span_id=span_id,
                    confidence=1.0,
                )
            )

        return facts

    def _parse_write_span(
        self, span_id: str | None, input_data: dict[str, Any], turn: int
    ) -> list[SpanFact]:
        """Extract facts from Write tool span."""
        facts: list[SpanFact] = []
        file_path = input_data.get("file_path", "")
        content = input_data.get("content", "")

        if file_path:
            facts.append(
                SpanFact(
                    key="file_written",
                    value=file_path,
                    turn=turn,
                    span_id=span_id,
                    confidence=1.0,
                )
            )

            # Count lines written as mutation_count
            if content:
                line_count = len(content.split("\n"))
                facts.append(
                    SpanFact(
                        key="mutation_count",
                        value=str(line_count),
                        turn=turn,
                        span_id=span_id,
                        confidence=1.0,
                        metadata={"file_path": file_path},
                    )
                )

        return facts

    def _parse_bash_span(
        self,
        span_id: str | None,
        input_data: dict[str, Any],
        output: str,
        turn: int,
    ) -> list[SpanFact]:
        """Extract facts from Bash tool span."""
        facts: list[SpanFact] = []
        command = input_data.get("command", "")

        # Check if this is a test command
        if self._is_test_command(command):
            test_result = self._extract_test_result(output)
            if test_result:
                facts.append(
                    SpanFact(
                        key="test_result",
                        value=test_result,
                        turn=turn,
                        span_id=span_id,
                        confidence=1.0,
                        metadata={"command": command},
                    )
                )

        # SEMANTIC: Extract bash output for context (errors, logs, etc.)
        # Only extract meaningful output (not just 'ok' or empty)
        if output and len(output) > 50:
            # Focus on interesting outputs: errors, git operations, builds
            interesting_commands = [
                "git",
                "npm",
                "pip",
                "docker",
                "make",
                "cargo",
                "error",
                "fail",
                "psql",
            ]
            is_interesting = any(kw in command.lower() for kw in interesting_commands)
            has_error = "error" in output.lower() or "failed" in output.lower()

            if is_interesting or has_error:
                facts.append(
                    SpanFact(
                        key="bash_output",
                        value=output[: self.MAX_CONTENT_LENGTH],
                        turn=turn,
                        span_id=span_id,
                        confidence=0.8,  # Lower - contextual info
                        metadata={"command": command[:200]},
                    )
                )

        return facts

    def _parse_task_span(
        self,
        span_id: str | None,
        metadata: dict[str, Any],
        input_data: dict[str, Any],
        turn: int,
        output_str: str = "",
    ) -> list[SpanFact]:
        """Extract facts from Task tool span."""
        facts: list[SpanFact] = []

        # Get agent type from metadata or default to "unknown"
        agent_type = metadata.get("agent_type", "unknown")

        facts.append(
            SpanFact(
                key="agent_spawned",
                value=agent_type,
                turn=turn,
                span_id=span_id,
                confidence=1.0,
                metadata={"prompt": input_data.get("prompt", "")[:100]},  # Truncate
            )
        )

        # SEMANTIC: Extract user message (the task prompt)
        prompt = input_data.get("prompt", "")
        if prompt and len(prompt) > 20:
            facts.append(
                SpanFact(
                    key="user_message",
                    value=prompt[: self.MAX_CONTENT_LENGTH],
                    turn=turn,
                    span_id=span_id,
                    confidence=1.0,
                    metadata={"agent_type": agent_type},
                )
            )

        # SEMANTIC: Extract agent output (summary/response)
        if output_str and len(output_str) > 20:
            facts.append(
                SpanFact(
                    key="agent_output",
                    value=output_str[: self.MAX_CONTENT_LENGTH],
                    turn=turn,
                    span_id=span_id,
                    confidence=0.9,
                    metadata={"agent_type": agent_type},
                )
            )

        return facts

    def _parse_llm_span(self, span: dict[str, Any], turn: int) -> list[SpanFact]:
        """Parse llm-type span for token counts AND semantic content."""
        facts: list[SpanFact] = []
        span_id = span.get("span_id")
        metrics = span.get("metrics", {}) or {}

        tokens = metrics.get("tokens")
        if tokens is not None:
            facts.append(
                SpanFact(
                    key="tokens_used",
                    value=str(tokens),
                    turn=turn,
                    span_id=span_id,
                    confidence=1.0,
                    metadata={
                        "prompt_tokens": metrics.get("prompt_tokens"),
                        "completion_tokens": metrics.get("completion_tokens"),
                    },
                )
            )

        # SEMANTIC: Extract LLM response content (Claude's reasoning)
        output = span.get("output")
        if output:
            content = self._extract_llm_content(output)
            if content and len(content) > 50:  # Only meaningful content
                facts.append(
                    SpanFact(
                        key="llm_response",
                        value=content[: self.MAX_CONTENT_LENGTH],
                        turn=turn,
                        span_id=span_id,
                        confidence=0.9,  # Slightly lower - truncated content
                        metadata={"full_length": len(content)},
                    )
                )

        return facts

    def _extract_llm_content(self, output: Any) -> str:
        """Extract text content from LLM output.

        Handles various output formats:
        - String (direct response)
        - Dict with 'content' key
        - List of content blocks (Claude format)
        """
        if isinstance(output, str):
            return output

        if isinstance(output, dict):
            # Try common keys
            for key in ["content", "text", "message", "response"]:
                if key in output:
                    return self._extract_llm_content(output[key])

        if isinstance(output, list):
            # Claude format: list of content blocks
            texts = []
            for block in output:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif "content" in block:
                        texts.append(str(block["content"]))
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)

        return ""

    def _parse_skill_activation(
        self, span: dict[str, Any], turn: int
    ) -> list[SpanFact]:
        """Extract skill activation from metadata."""
        facts: list[SpanFact] = []
        span_id = span.get("span_id")
        metadata = span.get("metadata", {}) or {}

        skill_name = metadata.get("skill_name")
        if skill_name:
            facts.append(
                SpanFact(
                    key="skill_activated",
                    value=skill_name,
                    turn=turn,
                    span_id=span_id,
                    confidence=1.0,
                )
            )

        return facts

    def _compute_content_hash(self, fact: SpanFact) -> str:
        """Compute hash for deduplication (excludes timestamp).

        Hash is based on key:value:turn which allows same facts
        to be deduplicated across multiple processing runs.
        """
        content = f"{fact.key}:{fact.value}:{fact.turn}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _parse_json_safe(self, json_str: str) -> dict[str, Any]:
        """Safely parse JSON, returning empty dict on failure."""
        if not json_str or not isinstance(json_str, str):
            return {}
        try:
            result = json.loads(json_str)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _is_test_command(self, command: str) -> bool:
        """Check if command is a test runner command."""
        test_indicators = ["pytest", "python -m pytest", "npm test", "cargo test"]
        return any(indicator in command.lower() for indicator in test_indicators)

    def _extract_test_result(self, output: str) -> str | None:
        """Extract test result summary from output."""
        if not output:
            return None

        # Try to match "X passed, Y failed" pattern
        match = self.PYTEST_PATTERN.search(output)
        if match:
            passed, failed = match.groups()
            return f"{passed} passed, {failed} failed"

        # Try pass-only pattern
        match = self.PYTEST_PASS_ONLY.search(output)
        if match:
            passed = match.group(1)
            return f"{passed} passed"

        # Try fail-only pattern
        match = self.PYTEST_FAIL_ONLY.search(output)
        if match:
            failed = match.group(1)
            return f"{failed} failed"

        return None
