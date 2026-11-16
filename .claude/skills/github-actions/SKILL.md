---
name: github-actions
description: Claude Code GitHub Actions integration - automated PR review, issue implementation, CI/CD
allowed-tools: [Read, Bash]
---

# GitHub Actions Integration

Integrate Claude Code with GitHub for automated code review and implementation.

## When to Use

- "Set up Claude in GitHub Actions"
- "Automate PR reviews"
- "Claude not responding to @claude"
- "GitHub Actions authentication"
- "CI/CD with Claude"

## Quick Setup

```bash
claude /install-github-app
```

This guides you through:
1. Installing Claude GitHub App
2. Configuring repository secrets
3. Setting up workflow files

## Manual Setup

1. **Install GitHub App:** https://github.com/apps/claude
2. **Add secret:** Settings → Secrets → `ANTHROPIC_API_KEY`
3. **Create workflow:** `.github/workflows/claude.yml`

## Basic Workflow

```yaml
name: Claude Code Action
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

**Usage in GitHub:**
```
@claude implement this feature
@claude fix the TypeError in dashboard
@claude review this code for security issues
```

## PR Review Workflow

```yaml
name: Automated Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/review"
          claude_args: "--max-turns 5"
```

## Issue-to-PR Automation

```yaml
name: Issue Implementation
on:
  issues:
    types: [labeled]

jobs:
  implement:
    if: github.event.label.name == 'claude-implement'
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "Implement the feature in this issue. Create a PR."
          claude_args: "--max-turns 15"
```

## Authentication Options

### Direct API Key (Simplest)
```yaml
anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### AWS Bedrock
```yaml
permissions:
  id-token: write

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
      aws-region: us-west-2

  - uses: anthropics/claude-code-action@v1
    with:
      use_bedrock: "true"
```

### Google Vertex AI
```yaml
permissions:
  id-token: write

steps:
  - uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
      service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

  - uses: anthropics/claude-code-action@v1
    with:
      use_vertex: "true"
```

## Best Practices

### Create CLAUDE.md
```markdown
# Project Standards

## Code Style
- TypeScript for frontend
- Follow PEP 8 for Python

## Review Checklist
- No hardcoded secrets
- Error handling for async
- Unit tests required
```

### Performance Optimization
```yaml
claude_args: "--max-turns 5"      # Quick reviews
claude_args: "--max-turns 15"     # Complex features
claude_args: "--model sonnet"     # Balanced cost/speed
```

### Set Timeouts
```yaml
jobs:
  claude:
    timeout-minutes: 30
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Claude not responding | Check GitHub App installed |
| Auth errors | Verify secret name matches workflow |
| CI not running on Claude's commits | Use GitHub App token |
| Slow responses | Reduce `--max-turns` |

## Advanced Configuration

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    trigger_phrase: "@assistant"  # Custom trigger
    claude_args: |
      --max-turns 10
      --model claude-opus-4-5-20251101
      --allowed-tools Bash,Read,Edit
```
