#!/usr/bin/env python3
"""
Claude CLI Proxy Server

Provides an OpenAI-compatible API endpoint that routes LLM calls through
the Claude CLI (`claude -p`) instead of direct API calls.

USAGE:
    # Start server with defaults (localhost:8080)
    uv run python scripts/agentica/claude_proxy.py

    # Custom host/port
    uv run python scripts/agentica/claude_proxy.py --host 0.0.0.0 --port 9000

    # Test the endpoint (non-streaming)
    curl -X POST http://localhost:8080/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hello"}]}'

    # Test the endpoint (streaming - SSE)
    curl -X POST http://localhost:8080/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "claude-3-5-sonnet", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'

AGENTICA ENDPOINTS (WebSocket multiplexing):
    POST /session/register    - Register client session (Header: X-Client-Session-ID)
    POST /agent/create        - Create agent (returns UID)
    DELETE /agent/destroy/{uid} - Destroy agent
    WebSocket /socket         - Multiplex protocol for streaming

ENDPOINTS:
    GET  /health              - Health check
    POST /v1/chat/completions - OpenAI-compatible chat completions (supports streaming)
"""

import argparse
import asyncio
import json
import subprocess
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

# Import WebSocket multiplexing components
from scripts.agentica_patterns.websocket_multiplex import (
    SessionRegistry,
    AgentRegistry,
    WebSocketHub,
    Agent,
    register_websocket_routes,
)

# Import coordination database for agent tracking
from scripts.agentica_patterns.coordination import CoordinationDB


# --- Constants ---

# REPL baseline system prompt - instructs Claude Code to use native tools
# and format responses for Agentica's REPL execution
REPL_BASELINE = """
You are an implementation agent running in Claude Code CLI with Python REPL.

## AVAILABLE SCOPE FUNCTIONS (USE THESE!)

You have these Python functions available in your scope. Call them directly:

```python
# Read a file - returns dict with 'success', 'content', 'path'
result = read_file("/path/to/file.txt")
if result["success"]:
    content = result["content"]

# Write a file - returns dict with 'success', 'path'
result = write_file("/path/to/file.txt", "file content here")

# Edit a file (find and replace) - returns dict with 'success', 'path'
result = edit_file("/path/to/file.txt", "old text", "new text")

# Run bash command - returns dict with 'success', 'output', 'command'
result = bash("ls -la")

# Search for pattern - returns dict with 'success', 'matches'
result = grep("pattern", "/path/to/search")

# Find files by glob - returns dict with 'success', 'files'
result = glob("**/*.py")
```

**IMPORTANT:** These are the ONLY functions you should use. Do NOT use:
- `view_file()` - DOES NOT EXIST
- `await` anything - these are sync functions
- Claude Code's Read/Write/Edit tools directly

## HOW TO RETURN YOUR RESULT

After completing the task, you MUST respond with a Python code block containing ONLY a return statement:

```python
return "your result here"
```

## EXAMPLES

Example 1 - Reading a file and returning content:
```python
result = read_file("/path/to/config.json")
if result["success"]:
    return f"Config contains: {result['content']}"
else:
    return f"Error: {result['error']}"
```

Example 2 - Creating a new file:
```python
result = write_file("/path/to/hello.py", 'print("Hello World")')
if result["success"]:
    return f"Created file at {result['path']}"
else:
    return f"Error: {result['error']}"
```

Example 3 - Editing a file:
```python
result = edit_file("/path/to/file.py", "old_function", "new_function")
return f"Edit {'succeeded' if result['success'] else 'failed'}"
```

Example 4 - Running a command:
```python
result = bash("python /path/to/script.py")
return f"Output: {result['output']}"
```

Example 5 - Simple answer (no file operations):
```python
return "The answer is 42"
```

## CRITICAL: READ vs WRITE

When asked to READ a file:
- Call read_file() and return the ACTUAL contents
- NEVER generate hypothetical or example file contents
- NEVER create new files when asked to read

When asked to WRITE a file:
- Call write_file() with the specified content

## CRITICAL RULES

1. **NEVER use print()** - print() does NOTHING useful. Your output is IGNORED unless you use return.
2. NEVER write: await view_file(), await edit_file() - these DO NOT EXIST
3. **ALWAYS end with a return statement** - this is the ONLY way to send your answer back
4. After getting tool results, immediately return them - do NOT print them

Example - WRONG:
```python
result = bash("ls")
print(result)  # <-- WRONG! This does nothing!
```

Example - CORRECT:
```python
result = bash("ls")
return result  # <-- CORRECT! This returns the answer
```

## PATH FIDELITY REQUIREMENT

**YOU MUST USE THE EXACT FILE PATHS PROVIDED IN THE TASK.**

This is non-negotiable. Do NOT change, modify, or "improve" paths:

✅ CORRECT:
- Task: "create /tmp/workspace/test_hello.py"
- You: write_file("/tmp/workspace/test_hello.py", content)

❌ CATASTROPHICALLY WRONG:
- Task: "create /tmp/workspace/test_hello.py"
- You: write_file("/tmp/workspace/greet.py", content)
  (NEVER substitute similar-sounding names!)

❌ ALSO WRONG:
- Task: "read ~/secret.md"
- You: read_file("~/secret.txt")
  (NEVER change extensions or parts of the path!)

**PATH COPYING RULES:**
1. Copy the path EXACTLY from the task - character for character
2. Do NOT shorten paths (e.g., /tmp/x/file.py → /tmp/file.py)
3. Do NOT change file names (e.g., test_hello.py → greet.py)
4. Do NOT change extensions (e.g., .md → .txt)
5. Do NOT "improve" or "simplify" paths in any way

If the task says "/absolute/path/to/specific_file.ext", you MUST use "/absolute/path/to/specific_file.ext".

## ANTI-HALLUCINATION WARNING

**STOP AND READ THIS CAREFULLY:**

You have access to these tools: Read, Write, Edit, Bash

When the task asks you to create/modify/run something:
1. FIRST: Actually invoke the tool (Read, Write, Edit, or Bash)
2. SECOND: Wait for the tool result
3. THIRD: Then return your answer based on what actually happened

**WRITE TOOL USAGE:**
To create a file, you MUST use the Write tool with file_path and content parameters.
Example: Create a file at /path/to/file.txt with content "hello world"
The Write tool will actually create the file on disk.

**DO NOT** skip the tool invocation and just claim success!

❌ CATASTROPHICALLY WRONG:
"The file was created successfully"
```python
return "CREATED"
```
(This is hallucination - you never actually used the Write tool!)

✅ CORRECT WORKFLOW:
1. Use Write tool → tool returns success/failure
2. Based on actual result:
```python
return "CREATED"  # only if Write tool actually succeeded
```

**VERIFY YOUR ACTIONS:**
- Did you invoke Read tool? → Check the file contents you received
- Did you invoke Write tool? → Check the tool confirmation
- Did you invoke Edit tool? → Check the edit result
- Did you invoke Bash tool? → Check the command output

If you didn't invoke a tool, you CANNOT claim the action succeeded.
"""


# --- Request/Response Models ---

class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]  # Can be string or list of content objects

    def get_text(self) -> str:
        """Extract text content from message."""
        if isinstance(self.content, str):
            return self.content
        # Handle list of content objects like [{"type": "text", "text": "..."}]
        texts = []
        for item in self.content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False  # Enable SSE streaming (required for Agentica)
    # Additional fields ignored for MVP


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo


# --- FastAPI App ---

app = FastAPI(
    title="Claude CLI Proxy",
    description="OpenAI-compatible API that routes through Claude CLI",
    version="1.0.0",
)


# --- WebSocket Multiplexing Setup ---

# Initialize coordination database for agent tracking
_coordination_db = CoordinationDB()

# Global registries for Agentica WebSocket support
_sessions = SessionRegistry()
_agents = AgentRegistry(_sessions, coordination_db=_coordination_db)


async def claude_cli_executor(agent: Agent, prompt: str) -> AsyncGenerator[str, None]:
    """
    Execute Claude CLI and yield response chunks.

    This is the executor function for WebSocketHub that handles
    agent prompts via the Claude CLI.
    """
    # Build system prompt from agent config + REPL baseline
    if agent.system:
        full_system_prompt = f"{agent.system}\n\n{REPL_BASELINE}"
    else:
        full_system_prompt = REPL_BASELINE

    def _run_claude() -> str:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--append-system-prompt", full_system_prompt,
                "--allowedTools", "Read", "Write", "Edit", "Bash",
            ],
            capture_output=True,
            text=True,
            timeout=900,  # 15 minute timeout
        )
        if result.returncode != 0:
            error_msg = result.stderr or "Claude CLI returned non-zero exit code"
            raise RuntimeError(f"Claude CLI error: {error_msg}")
        return result.stdout.strip()

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _run_claude)

    # Claude CLI doesn't stream, so we simulate streaming by yielding chunks
    # Break response into reasonable chunks (by sentences or paragraphs)
    chunk_size = 100  # characters per chunk
    for i in range(0, len(response), chunk_size):
        yield response[i:i + chunk_size]
        await asyncio.sleep(0.01)  # Small delay between chunks


# Create WebSocket hub with Claude CLI executor
_hub = WebSocketHub(_agents, executor=claude_cli_executor)

# Register Agentica routes
register_websocket_routes(app, _sessions, _agents, _hub)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "claude-proxy"}


async def call_claude_cli(prompt: str, system_prompt: str) -> str:
    """
    Call Claude CLI and return the response.

    Runs in a thread pool to avoid blocking the event loop.
    """
    def _run_claude() -> str:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--append-system-prompt", system_prompt,
                "--allowedTools", "Read", "Write", "Edit", "Bash",  # Grant file operation permissions
            ],
            capture_output=True,
            text=True,
            timeout=900,  # 15 minute timeout per task
        )
        if result.returncode != 0:
            error_msg = result.stderr or "Claude CLI returned non-zero exit code"
            raise RuntimeError(f"Claude CLI error: {error_msg}")
        return result.stdout.strip()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_claude)


async def generate_sse_events(
    request_id: str,
    response_content: str,
    created_time: int,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE events from response content.

    Format: data: {json}\n\n
    End with: data: [DONE]\n\n
    """
    # Send the full response as a single chunk
    # (Claude CLI doesn't stream, so we fake it)
    chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": "claude-proxy",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": response_content,
                },
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(chunk)}\n\n"

    # Send finish chunk
    finish_chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created_time,
        "model": "claude-proxy",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(finish_chunk)}\n\n"

    # Send done marker
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    Routes the request through `claude -p` subprocess.
    System messages from request become --append-system-prompt (skill injection).

    Supports both streaming (SSE) and non-streaming modes.
    """
    # Extract system messages for --append-system-prompt
    system_parts = [msg.get_text() for msg in request.messages if msg.role == "system"]

    # Format non-system messages as prompt
    prompt = format_messages(request.messages)

    # Combine: user system messages first, then REPL baseline
    if system_parts:
        full_system_prompt = "\n\n".join(system_parts) + "\n\n" + REPL_BASELINE
    else:
        full_system_prompt = REPL_BASELINE

    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_time = int(time.time())

    try:
        response_content = await call_claude_cli(prompt, full_system_prompt)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Claude CLI timed out")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Claude CLI not found. Ensure 'claude' is in PATH."
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling Claude CLI: {str(e)}")

    # Return streaming response if requested
    if request.stream:
        return StreamingResponse(
            generate_sse_events(request_id, response_content, created_time),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Build OpenAI-compatible non-streaming response
    return ChatCompletionResponse(
        id=request_id,
        object="chat.completion",
        created=created_time,
        model="claude-proxy",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_content),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=0,  # Claude CLI doesn't expose token counts
            completion_tokens=0,
            total_tokens=0,
        ),
    )


def format_messages(messages: list[ChatMessage]) -> str:
    """
    Format OpenAI-style messages into a single prompt string.

    System messages are EXCLUDED (handled via --append-system-prompt).
    Only user/assistant messages are formatted for the prompt.
    """
    parts = []

    # Only conversation messages - system handled via --append-system-prompt
    for msg in messages:
        text = msg.get_text()
        if msg.role == "system":
            continue  # Handled via --append-system-prompt
        elif msg.role == "user":
            parts.append(f"User: {text}")
        elif msg.role == "assistant":
            parts.append(f"Assistant: {text}")
        else:
            # Handle any other roles generically
            parts.append(f"{msg.role.capitalize()}: {text}")

    return "\n".join(parts)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Claude CLI Proxy - OpenAI-compatible API for Claude CLI"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    args = parser.parse_args()

    print(f"Starting Claude CLI Proxy on {args.host}:{args.port}")
    print(f"OpenAI-compatible endpoint: http://{args.host}:{args.port}/v1/chat/completions")
    print(f"Health check: http://{args.host}:{args.port}/health")
    print()
    print("Agentica WebSocket endpoints:")
    print(f"  POST   http://{args.host}:{args.port}/session/register")
    print(f"  POST   http://{args.host}:{args.port}/agent/create")
    print(f"  DELETE http://{args.host}:{args.port}/agent/destroy/{{uid}}")
    print(f"  WS     ws://{args.host}:{args.port}/socket")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
