# Rigg SDK Architecture

A unified LLM client SDK with provider-agnostic message handling, streaming, and tool simulation.

## Overview

Rigg abstracts the differences between LLM providers behind a consistent interface. Messages use a universal format that is a superset of all provider capabilities, with adapters handling bidirectional transformation.

```
┌─────────────────────────────────────────────────────────────┐
│                      Application                            │
├─────────────────────────────────────────────────────────────┤
│                    Universal Message Format                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │  Text   │  │  Tools  │  │  Media  │  │ Structured Data │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Transform Pipeline                       │
│  ┌────────────────┐    ┌────────────────┐                   │
│  │ In Transformer │ ←→ │ Out Transformer│                   │
│  └────────────────┘    └────────────────┘                   │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────────┤
│Anthro│OpenAI│Google│Mistral│ Groq │LMStud│Ollama│  ...more  │
└──────┴──────┴──────┴──────┴──────┴──────┴──────┴───────────┘
```

---

## Transform Pipeline

The transform pipeline handles conversion between the universal message format and provider-specific formats.

### Architecture

```typescript
interface TransformPipeline {
  // Convert universal format to provider-specific request
  transformIn(message: Message, provider: ProviderConfig): ProviderRequest;

  // Convert provider-specific response to universal format
  transformOut(response: ProviderResponse, provider: ProviderConfig): Message;

  // Stream transformer for real-time responses
  transformStream(stream: AsyncIterable<ProviderChunk>): AsyncIterable<ContentChunk>;
}
```

### Pipeline Stages

1. **Normalization**: Validate and normalize input message
2. **Content Transformation**: Convert content blocks to provider format
3. **Metadata Injection**: Add provider-specific headers, parameters
4. **Response Parsing**: Extract content from provider response
5. **Metadata Extraction**: Capture tokens, timing, cost

---

## Message Format

The universal message format is a superset of all provider capabilities.

### Core Types

```typescript
interface Message {
  role: 'user' | 'assistant' | 'system';
  content: ContentBlock[];
  metadata: MessageMetadata;
}

interface MessageMetadata {
  model: string;
  provider: string;
  tokens: {
    input: number;
    output: number;
    cache_read?: number;   // Anthropic prompt caching
    cache_write?: number;
    thinking?: number;     // Extended thinking tokens
  };
  timing: {
    start: number;         // Unix timestamp ms
    end: number;
    first_token?: number;  // Time to first token
  };
  cost_usd: number;
  request_id?: string;     // Provider request ID for debugging
}
```

### Content Blocks

```typescript
type ContentBlock =
  | TextBlock
  | ToolUseBlock
  | ToolResultBlock
  | ImageBlock
  | AudioBlock
  | VideoBlock
  | PDFBlock
  | ThinkingBlock
  | StructuredDataBlock;

interface TextBlock {
  type: 'text';
  text: string;
}

interface ToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: ContentBlock[];    // Can contain text, images, etc.
  is_error?: boolean;
}

interface ImageBlock {
  type: 'image';
  source: {
    type: 'base64' | 'url';
    media_type: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp';
    data?: string;            // Base64 for type: 'base64'
    url?: string;             // URL for type: 'url'
  };
}

interface AudioBlock {
  type: 'audio';
  source: {
    type: 'base64' | 'url';
    media_type: 'audio/wav' | 'audio/mp3' | 'audio/ogg';
    data?: string;
    url?: string;
  };
}

interface VideoBlock {
  type: 'video';
  source: {
    type: 'base64' | 'url';
    media_type: 'video/mp4' | 'video/webm';
    data?: string;
    url?: string;
  };
}

interface PDFBlock {
  type: 'pdf';
  source: {
    type: 'base64' | 'url';
    data?: string;
    url?: string;
  };
  page_range?: { start: number; end: number };
}

interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
  signature?: string;         // Anthropic thinking signature
}

interface StructuredDataBlock {
  type: 'structured_data';
  schema: JSONSchema;         // Expected output schema
  data?: unknown;             // Parsed structured output
}
```

### Conversation Context

```typescript
interface Conversation {
  messages: Message[];
  system?: string | ContentBlock[];  // System prompt
  metadata: {
    total_tokens: { input: number; output: number };
    total_cost_usd: number;
    turns: number;
  };
}
```

---

## Streaming

Streaming uses AsyncIterator with line buffering for SSE compatibility.

### Stream Types

```typescript
interface StreamConfig {
  onChunk?: (chunk: ContentChunk) => void;
  onToolUse?: (tool: ToolUseBlock) => void;
  onThinking?: (thinking: ThinkingBlock) => void;
  onMetadata?: (metadata: Partial<MessageMetadata>) => void;
  signal?: AbortSignal;
}

type ContentChunk =
  | { type: 'text_delta'; text: string }
  | { type: 'tool_use_start'; id: string; name: string }
  | { type: 'tool_use_delta'; id: string; partial_json: string }
  | { type: 'tool_use_end'; id: string }
  | { type: 'thinking_delta'; thinking: string }
  | { type: 'message_start'; metadata: Partial<MessageMetadata> }
  | { type: 'message_end'; metadata: MessageMetadata };
```

### Stream Processing

```typescript
async function* streamResponse(
  provider: ProviderAdapter,
  request: ProviderRequest,
  config: StreamConfig
): AsyncIterable<ContentChunk> {
  const rawStream = provider.stream(request);
  const lineBuffer = new LineBuffer();

  for await (const data of rawStream) {
    lineBuffer.append(data);

    for (const line of lineBuffer.flush()) {
      if (!line.startsWith('data: ')) continue;
      if (line === 'data: [DONE]') return;

      const chunk = provider.parseChunk(line.slice(6));
      const normalized = transformChunk(chunk, provider);

      // Invoke callbacks
      if (normalized.type === 'text_delta' && config.onChunk) {
        config.onChunk(normalized);
      }

      yield normalized;
    }
  }
}

class LineBuffer {
  private buffer = '';

  append(data: string): void {
    this.buffer += data;
  }

  flush(): string[] {
    const lines: string[] = [];
    let newlineIdx: number;

    while ((newlineIdx = this.buffer.indexOf('\n')) !== -1) {
      lines.push(this.buffer.slice(0, newlineIdx).trim());
      this.buffer = this.buffer.slice(newlineIdx + 1);
    }

    return lines;
  }
}
```

---

## Tool Simulation

Tools are supported across all providers using an adaptive approach.

### Capability Detection

```typescript
interface ToolCapabilities {
  native: boolean;              // Provider supports function calling
  structured_output: boolean;   // Provider supports JSON mode
  parallel_tools: boolean;      // Can call multiple tools at once
  streaming_tools: boolean;     // Can stream tool use
}

async function detectCapabilities(
  provider: ProviderAdapter,
  model: string
): Promise<ToolCapabilities> {
  // Query provider for model capabilities
  // Cache results for session
}
```

### Adaptive Strategy

The SDK uses a fallback chain based on model capabilities:

```typescript
type ToolStrategy = 'native' | 'structured_json' | 'react';

function selectStrategy(capabilities: ToolCapabilities): ToolStrategy {
  if (capabilities.native) return 'native';
  if (capabilities.structured_output) return 'structured_json';
  return 'react';
}
```

#### 1. Native Tool Use

For providers with built-in function calling (Anthropic, OpenAI, Google):

```typescript
// Tools passed directly to provider API
const response = await provider.complete({
  messages,
  tools: toolDefinitions,
  tool_choice: 'auto'
});
```

#### 2. Structured JSON Fallback

For providers with JSON mode but no native tools (some Mistral models):

```typescript
const toolPrompt = `
You have access to these tools:
${formatToolSchemas(tools)}

To use a tool, respond with JSON:
{"tool": "tool_name", "input": {...}}

To respond normally, use:
{"response": "your message"}
`;

const response = await provider.complete({
  messages: [{ role: 'system', content: toolPrompt }, ...messages],
  response_format: { type: 'json_object' }
});

// Parse and convert to ToolUseBlock
const parsed = JSON.parse(response.content[0].text);
if (parsed.tool) {
  return { type: 'tool_use', name: parsed.tool, input: parsed.input };
}
```

#### 3. ReAct Fallback

For models without structured output (older models, some local LLMs):

```typescript
const reactPrompt = `
You have access to these tools:
${formatToolDescriptions(tools)}

Use this format:
Thought: I need to...
Action: tool_name
Action Input: {"param": "value"}

Or to respond:
Thought: I have the answer
Final Answer: your response
`;

// Parse ReAct format from plain text response
function parseReactResponse(text: string): ToolUseBlock | TextBlock {
  const actionMatch = text.match(/Action:\s*(\w+)\s*\nAction Input:\s*(.+)/s);
  if (actionMatch) {
    return {
      type: 'tool_use',
      id: generateId(),
      name: actionMatch[1],
      input: JSON.parse(actionMatch[2])
    };
  }

  const answerMatch = text.match(/Final Answer:\s*(.+)/s);
  return { type: 'text', text: answerMatch?.[1] ?? text };
}
```

### Role Prompts

Tool instructions use simple, direct role prompts:

```typescript
// DO: Simple and direct
const systemPrompt = `You are a helpful assistant with access to tools.`;

// DON'T: Elaborate personas
const systemPrompt = `You are ARIA, an Advanced Reasoning Intelligence Assistant
with deep expertise in tool orchestration and multi-step reasoning...`;
```

---

## Error Handling

Errors are normalized across providers with recovery hints.

### Error Types

```typescript
type RiggErrorCode =
  | 'RATE_LIMIT'          // 429 responses
  | 'CONTEXT_LENGTH'      // Input too long
  | 'CONTENT_FILTER'      // Safety filter triggered
  | 'INVALID_REQUEST'     // Malformed request
  | 'AUTHENTICATION'      // API key issues
  | 'SERVER_ERROR'        // 5xx responses
  | 'NETWORK'             // Connection issues
  | 'TIMEOUT'             // Request timeout
  | 'MODEL_UNAVAILABLE'   // Model not available
  | 'QUOTA_EXCEEDED';     // Billing limit reached

interface RiggError extends Error {
  code: RiggErrorCode;
  provider: string;
  model: string;
  recoverable: boolean;
  retryAfter?: number;      // Seconds until retry
  hint: string;             // Human-readable recovery suggestion
  raw?: unknown;            // Original provider error
}
```

### Error Mapping

```typescript
function normalizeError(error: unknown, provider: string): RiggError {
  // Anthropic
  if (error.status === 429) {
    return {
      code: 'RATE_LIMIT',
      provider,
      recoverable: true,
      retryAfter: parseRetryAfter(error.headers),
      hint: 'Rate limited. Retry after delay or use a different API key.'
    };
  }

  // OpenAI context length
  if (error.code === 'context_length_exceeded') {
    return {
      code: 'CONTEXT_LENGTH',
      provider,
      recoverable: true,
      hint: 'Message too long. Truncate history or use a model with larger context.'
    };
  }

  // ... map other provider-specific errors
}
```

### Retry with Exponential Backoff

```typescript
interface RetryConfig {
  maxRetries: number;
  baseDelay: number;        // Initial delay in ms
  maxDelay: number;         // Maximum delay in ms
  jitter: boolean;          // Add randomness to prevent thundering herd
  retryOn: RiggErrorCode[]; // Which errors to retry
}

const DEFAULT_RETRY: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  jitter: true,
  retryOn: ['RATE_LIMIT', 'SERVER_ERROR', 'NETWORK', 'TIMEOUT']
};

async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = DEFAULT_RETRY
): Promise<T> {
  let lastError: RiggError;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = normalizeError(error);

      if (!lastError.recoverable || !config.retryOn.includes(lastError.code)) {
        throw lastError;
      }

      if (attempt === config.maxRetries) break;

      const delay = calculateDelay(attempt, lastError, config);
      await sleep(delay);
    }
  }

  throw lastError;
}

function calculateDelay(
  attempt: number,
  error: RiggError,
  config: RetryConfig
): number {
  // Use server's retry-after if available
  if (error.retryAfter) {
    return Math.min(error.retryAfter * 1000, config.maxDelay);
  }

  // Exponential backoff: 1s, 2s, 4s, 8s...
  let delay = config.baseDelay * Math.pow(2, attempt);
  delay = Math.min(delay, config.maxDelay);

  // Add jitter: +/- 25%
  if (config.jitter) {
    delay *= 0.75 + Math.random() * 0.5;
  }

  return delay;
}
```

### Provider Failover

```typescript
interface FailoverConfig {
  providers: ProviderConfig[];  // Ordered by preference
  failoverOn: RiggErrorCode[];  // Errors that trigger failover
}

async function withFailover<T>(
  fn: (provider: ProviderConfig) => Promise<T>,
  config: FailoverConfig
): Promise<T> {
  const errors: RiggError[] = [];

  for (const provider of config.providers) {
    try {
      return await fn(provider);
    } catch (error) {
      const normalized = normalizeError(error, provider.name);
      errors.push(normalized);

      if (!config.failoverOn.includes(normalized.code)) {
        throw normalized;
      }

      // Continue to next provider
    }
  }

  throw new AggregateError(errors, 'All providers failed');
}
```

---

## Thinking/Reasoning

Extended thinking tokens can be included or stripped per request.

### Configuration

```typescript
interface ThinkingConfig {
  enabled: boolean;             // Request thinking from model
  include_in_response: boolean; // Include thinking block in output
  budget_tokens?: number;       // Max thinking tokens (Anthropic)
}

interface RequestConfig {
  thinking?: ThinkingConfig;
  // ... other config
}
```

### Usage

```typescript
// Request thinking, include in response
const response = await client.complete({
  messages,
  thinking: {
    enabled: true,
    include_in_response: true,
    budget_tokens: 10000
  }
});

// Response includes ThinkingBlock
// [{ type: 'thinking', thinking: '...' }, { type: 'text', text: '...' }]

// Request thinking, strip from response
const response = await client.complete({
  messages,
  thinking: {
    enabled: true,
    include_in_response: false
  }
});

// Response only includes text
// [{ type: 'text', text: '...' }]
// (tokens still billed for thinking)
```

### Provider Handling

```typescript
function handleThinking(
  response: ProviderResponse,
  config: ThinkingConfig,
  provider: string
): ContentBlock[] {
  const blocks: ContentBlock[] = [];

  for (const block of response.content) {
    if (block.type === 'thinking') {
      if (config.include_in_response) {
        blocks.push({
          type: 'thinking',
          thinking: block.thinking,
          signature: block.signature  // Anthropic-specific
        });
      }
      // Track tokens even if not included
      continue;
    }

    blocks.push(transformBlock(block, provider));
  }

  return blocks;
}
```

---

## Provider Adapters

Each provider implements a protocol-based interface.

### Adapter Interface

```typescript
interface ProviderAdapter {
  readonly name: string;
  readonly models: ModelInfo[];

  // Capability detection
  getCapabilities(model: string): Promise<ToolCapabilities>;

  // Transform pipeline
  transformIn(message: Message): ProviderRequest;
  transformOut(response: ProviderResponse): Message;

  // Execution
  complete(request: ProviderRequest): Promise<ProviderResponse>;
  stream(request: ProviderRequest): AsyncIterable<ProviderChunk>;

  // Error handling
  normalizeError(error: unknown): RiggError;

  // Metadata
  calculateCost(usage: TokenUsage, model: string): number;
}

interface ModelInfo {
  id: string;
  name: string;
  context_length: number;
  output_limit: number;
  capabilities: ToolCapabilities;
  pricing: {
    input_per_million: number;
    output_per_million: number;
    cache_read_per_million?: number;
    cache_write_per_million?: number;
  };
}
```

### Supported Providers

| Provider | Models | Native Tools | Streaming | Vision | Audio |
|----------|--------|--------------|-----------|--------|-------|
| Anthropic | Claude 3.5/4 | Yes | Yes | Yes | No |
| OpenAI | GPT-4, o1, o3 | Yes | Yes | Yes | Yes |
| Google | Gemini 1.5/2 | Yes | Yes | Yes | Yes |
| Mistral | Mistral/Mixtral | Partial | Yes | Yes | No |
| Groq | Llama, Mixtral | Yes | Yes | No | No |
| LMStudio | Local models | Via simulation | Yes | Varies | No |
| Ollama | Local models | Via simulation | Yes | Varies | No |

### Example: Anthropic Adapter

```typescript
class AnthropicAdapter implements ProviderAdapter {
  readonly name = 'anthropic';

  transformIn(message: Message): AnthropicRequest {
    return {
      model: message.metadata.model,
      messages: message.content.map(block => {
        switch (block.type) {
          case 'text':
            return { type: 'text', text: block.text };
          case 'image':
            return {
              type: 'image',
              source: {
                type: block.source.type,
                media_type: block.source.media_type,
                data: block.source.data
              }
            };
          case 'tool_use':
            return {
              type: 'tool_use',
              id: block.id,
              name: block.name,
              input: block.input
            };
          // ... other block types
        }
      }),
      max_tokens: 4096,
      // ... other Anthropic-specific params
    };
  }

  transformOut(response: AnthropicResponse): Message {
    return {
      role: 'assistant',
      content: response.content.map(block => transformBlock(block)),
      metadata: {
        model: response.model,
        provider: 'anthropic',
        tokens: {
          input: response.usage.input_tokens,
          output: response.usage.output_tokens,
          cache_read: response.usage.cache_read_input_tokens,
          cache_write: response.usage.cache_creation_input_tokens
        },
        timing: { start: this.requestStart, end: Date.now() },
        cost_usd: this.calculateCost(response.usage, response.model),
        request_id: response.id
      }
    };
  }

  normalizeError(error: unknown): RiggError {
    if (error.status === 529) {
      return {
        code: 'SERVER_ERROR',
        provider: 'anthropic',
        model: error.model,
        recoverable: true,
        hint: 'Anthropic overloaded. Retry with backoff or failover to another provider.'
      };
    }
    // ... other error mappings
  }
}
```

### Example: Local LLM Adapter (LMStudio/Ollama)

```typescript
class LMStudioAdapter implements ProviderAdapter {
  readonly name = 'lmstudio';

  async getCapabilities(model: string): Promise<ToolCapabilities> {
    // Local models typically don't have native tool support
    return {
      native: false,
      structured_output: true,  // Most support JSON mode
      parallel_tools: false,
      streaming_tools: false
    };
  }

  transformIn(message: Message): OpenAICompatibleRequest {
    // LMStudio uses OpenAI-compatible API
    const strategy = selectStrategy(await this.getCapabilities(message.metadata.model));

    if (strategy === 'structured_json') {
      // Inject tool schema into system prompt
      return this.transformWithJsonMode(message);
    }

    // Fall back to ReAct
    return this.transformWithReact(message);
  }

  // Cost is zero for local models
  calculateCost(): number {
    return 0;
  }
}
```

---

## Client Usage

### Basic Example

```typescript
import { RiggClient } from 'rigg';

const client = new RiggClient({
  providers: {
    anthropic: { apiKey: process.env.ANTHROPIC_API_KEY },
    openai: { apiKey: process.env.OPENAI_API_KEY }
  },
  defaults: {
    provider: 'anthropic',
    model: 'claude-sonnet-4-20250514'
  }
});

// Simple completion
const response = await client.complete({
  messages: [{ role: 'user', content: [{ type: 'text', text: 'Hello!' }] }]
});

// With tools
const response = await client.complete({
  messages,
  tools: [
    {
      name: 'get_weather',
      description: 'Get current weather for a location',
      input_schema: {
        type: 'object',
        properties: {
          location: { type: 'string' }
        },
        required: ['location']
      }
    }
  ]
});

// Streaming
for await (const chunk of client.stream({ messages })) {
  if (chunk.type === 'text_delta') {
    process.stdout.write(chunk.text);
  }
}
```

### With Failover

```typescript
const response = await client.complete({
  messages,
  failover: {
    providers: ['anthropic', 'openai', 'groq'],
    failoverOn: ['RATE_LIMIT', 'SERVER_ERROR']
  }
});
```

---

## Design Principles

1. **Universal Superset**: The message format supports all provider features. Providers that lack certain features (e.g., vision) reject those content blocks cleanly.

2. **Adapter Isolation**: Each provider adapter handles its own quirks. The core SDK never has provider-specific logic.

3. **Streaming First**: All completions can stream. Non-streaming is sugar over collecting stream chunks.

4. **Explicit Over Magic**: No hidden retries or fallbacks unless explicitly configured.

5. **Cost Awareness**: Every response includes cost data. Token counts are always accurate.

6. **Simple Prompts**: Tool simulation uses minimal, functional prompts. No elaborate personas or roleplay.
