---
name: model-configuration
description: Select and configure Claude models - Haiku, Sonnet, Opus, extended thinking, prompt caching
allowed-tools: [Read, Bash]
---

# Model Configuration Reference

Select and optimize Claude models for different tasks.

## When to Use

- "Which model should I use?"
- "Enable extended thinking"
- "Set up prompt caching"
- "Reduce costs"
- "Configure cloud models"

## Model Comparison

| Model | Best For | Cost | Speed |
|-------|----------|------|-------|
| **Haiku 4.5** | Speed, high-volume, simple tasks | $1/MTok in | Fastest |
| **Sonnet 4.5** | Balanced, coding, agents (DEFAULT) | $3/MTok in | Fast |
| **Opus 4.5** | Maximum intelligence, complex tasks | $5/MTok in | Slower |

## Selecting a Model

### Environment Variable
```bash
export ANTHROPIC_MODEL="claude-opus-4-5-20251101"
claude
```

### CLI Flag
```bash
claude --model claude-sonnet-4-5-20250929
claude --model sonnet  # Alias
claude --model opus    # Alias
```

### settings.json
```json
{
  "model": "claude-sonnet-4-5-20250929"
}
```

## Model Aliases

| Alias | Resolves To |
|-------|-------------|
| `sonnet` | Latest Sonnet 4.5 |
| `opus` | Latest Opus 4.5 |
| `haiku` | Latest Haiku 4.5 |

**Production:** Use specific versions (with date suffix)
**Experimentation:** Aliases are fine

## Extended Thinking

Enable for complex reasoning, math, debugging:

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # Control depth
    },
    messages=[{"role": "user", "content": "Debug this algorithm"}]
)

# Access thinking + answer
for block in response.content:
    if block.type == "thinking":
        print(f"Reasoning: {block.thinking}")
    elif block.type == "text":
        print(f"Answer: {block.text}")
```

**Budget tokens:** 1,024 - 32,000 (recommended: 5K-16K)

## Prompt Caching

Cache repeated content for 90% discount:

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    system=[
        {"type": "text", "text": "Legal analyzer"},
        {
            "type": "text",
            "text": "<50-page contract>",
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "Key terms?"}]
)
```

**Pricing:**
- Cache write: +25%
- Cache hit: -90%

**TTL options:** 5 minutes (default), 1 hour (beta)

## Cloud Providers

### AWS Bedrock
```bash
# Model ID format
anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Google Vertex AI
```bash
# Model ID format
claude-sonnet-4-5@20250929
```

## Decision Matrix

**Use Haiku when:**
- Real-time responses needed
- High-volume simple tasks
- Cost is primary concern

**Use Sonnet when:**
- Complex coding or analysis
- Multi-step reasoning
- Production agents (DEFAULT)

**Use Opus when:**
- Maximum intelligence required
- Specialized complex tasks
- Cost is secondary

## Cost Optimization

```bash
# Check current usage
claude /cost
```

**Tips:**
- Use Haiku for sub-tasks
- Enable caching for repeated context
- Use Batch API for non-real-time (50% off)
- Set appropriate max_tokens
- Use extended thinking only when needed

## Token Limits

| Model | Context | Max Output |
|-------|---------|------------|
| All current | 200K (1M beta) | 64K |

**1M context (Tier 4+ only):**
- First 200K: Standard pricing
- 200K-1M: 2x input, 1.5x output
