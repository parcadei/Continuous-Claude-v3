# 15. Security

> **Architecture Reference**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative decisions (113+ decisions from Round 3 interviews).

## Security Model

### Threat Model

**What we protect against:**
- Malicious MCP servers (filesystem access, code execution)
- Compromised dependencies (supply chain attacks)
- Accidental credential exposure (API keys in commits)
- Unauthorized data access (ledgers, temporal memory)

**What we assume trusted:**
- Claude Code binary itself
- User's local machine
- User's filesystem permissions
- Git remote repositories (after auth)

### Defense Layers

**Layer 1: Sandboxing**
- MCP servers run in isolated processes
- No direct filesystem access outside workspace
- Network calls require explicit permission
- See [14-sandbox.md](./14-sandbox.md) for details

**Layer 2: Resource Limits**
- CPU limits per MCP server (via cgroups)
- Memory limits (kills server on OOM)
- Timeout limits (30s default, configurable)
- Network bandwidth throttling

**Layer 3: Audit Logging**
- All tool calls logged to `.claude/cache/audit.log`
- Includes: timestamp, tool name, arguments, result
- Tamper-proof (append-only, checksummed)

**Layer 4: Secrets Management**
- API keys in `.env` (gitignored)
- Never log sensitive params
- Encrypted storage for credentials (optional)

### Claude Code Isolation

**Per-project configuration isolation:**

Claude Code supports per-project settings via `.claude/settings.local.json`:
```json
{
  "hooks": {
    "PreToolUse": [{"hooks": [{"type": "command", "command": "..."}]}]
  },
  "skills": ["./custom-skills"]
}
```

**Environment isolation:**
```bash
# Point Claude Code to project-specific config directory
export CLAUDE_CONFIG_DIR="$HOME/.config/claude-project-a"
claude --project /path/to/project-a

# Separate config for different projects
export CLAUDE_CONFIG_DIR="$HOME/.config/claude-project-b"
claude --project /path/to/project-b
```

**Benefits:**
- Hooks don't leak across projects
- Skills scoped to specific codebases
- Temporal memory isolated per project
- No cross-contamination of ledgers

**Use case:**
- Work repo uses production hooks
- Personal repo uses experimental hooks
- No interference between projects

See [12-error-recovery.md](./12-error-recovery.md) for environment setup details.

### MCP Server Security

**Server capabilities declaration:**
```json
{
  "mcpServers": {
    "untrusted-server": {
      "command": "npx",
      "args": ["-y", "some-mcp-server"],
      "sandbox": {
        "filesystem": "read-only",
        "network": "deny",
        "processes": "deny"
      }
    }
  }
}
```

**Capability enforcement:**
- Filesystem: `none` | `read-only` | `read-write` | `workspace-only`
- Network: `deny` | `allow` | `allow-domains=["example.com"]`
- Processes: `deny` | `allow-spawn` | `allow-exec`

**Runtime checks:**
- Tool calls validated against declared capabilities
- Blocked calls logged to audit log
- Server killed on repeated violations

### Secrets Management

**Environment variables (.env):**
```bash
# API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database credentials
POSTGRES_PASSWORD=...

# Never committed to git (in .gitignore)
```

**Encrypted storage (optional):**
```bash
# Use OS keychain for sensitive values
npm run secrets:set OPENAI_API_KEY
# Prompts for value, stores in macOS Keychain / Linux Secret Service

# Scripts read from keychain
OPENAI_API_KEY=$(npm run secrets:get OPENAI_API_KEY)
```

**Secrets in hook/skill code:**
```typescript
// NEVER hardcode secrets
const apiKey = "sk-...";  // ❌ WRONG

// Read from environment
const apiKey = process.env.OPENAI_API_KEY;  // ✅ CORRECT

// Validate presence
if (!apiKey) {
  throw new Error("OPENAI_API_KEY not set - see .env.example");
}
```

### Audit Logging

**Audit log format:**
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "event": "tool_call",
  "tool": "morph__warpgrep_codebase_search",
  "arguments": {
    "query": "authentication",
    "case_sensitive": false
  },
  "result": "success",
  "checksum": "sha256:..."
}
```

**Sensitive param redaction:**
```typescript
// Auto-redact common sensitive params
const SENSITIVE_PARAMS = ['api_key', 'password', 'token', 'secret'];

function redactSensitive(params: Record<string, any>): Record<string, any> {
  const redacted = { ...params };
  for (const key of Object.keys(redacted)) {
    if (SENSITIVE_PARAMS.some(s => key.toLowerCase().includes(s))) {
      redacted[key] = '[REDACTED]';
    }
  }
  return redacted;
}
```

**Audit log queries:**
```bash
# Find all tool calls in last hour
cat .claude/cache/audit.log | jq 'select(.timestamp > "2024-01-01T11:00:00Z")'

# Find failed tool calls
cat .claude/cache/audit.log | jq 'select(.result == "failure")'

# Verify log integrity (checksums)
npm run audit:verify
```

### Supply Chain Security

**Dependency scanning:**
```bash
# Scan for known vulnerabilities
npm audit

# Auto-fix non-breaking issues
npm audit fix

# Block high-severity vulnerabilities
npm audit --audit-level=high
```

**MCP server vetting:**
```bash
# Before adding a new MCP server:
# 1. Review source code (if available)
# 2. Check npm package popularity / maintainers
# 3. Run in sandbox first
# 4. Monitor audit logs for unexpected behavior

# Example: Add server with minimal permissions
{
  "new-server": {
    "sandbox": {
      "filesystem": "none",
      "network": "deny",
      "processes": "deny"
    }
  }
}

# Gradually increase permissions only if needed
```

**Lock file integrity:**
```bash
# Verify package-lock.json integrity
npm ci  # Fails if lock file is inconsistent

# Use npm shrinkwrap for production
npm shrinkwrap
```

### Credential Exposure Prevention

**Pre-commit hooks:**
```bash
# .git/hooks/pre-commit
#!/bin/bash

# Scan for accidentally committed secrets
if git diff --cached --name-only | xargs grep -E "sk-[a-zA-Z0-9]{32,}" ; then
  echo "❌ Detected API key in commit - aborting"
  echo "Remove sensitive data and try again"
  exit 1
fi

# Verify .env not staged
if git diff --cached --name-only | grep "^\.env$" ; then
  echo "❌ .env file should not be committed"
  exit 1
fi
```

**Secret scanning tools:**
```bash
# Install truffleHog or gitleaks
npm install -g gitleaks

# Scan repository history for secrets
gitleaks detect --source . --verbose

# Scan before push
git config --global alias.safe-push '!gitleaks detect && git push'
```

**GitHub Actions secret scanning:**
```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for secret scanning

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Access Control

**File permissions:**
```bash
# Ledgers and temporal memory should be user-only
chmod 700 thoughts/ledgers
chmod 600 thoughts/ledgers/*.md
chmod 600 .claude/cache/temporal.db

# Hooks should not be world-writable
chmod 755 .claude/hooks/*.sh
chmod 644 .claude/hooks/*.ts
```

**Database encryption (optional):**
```bash
# Encrypt SQLite databases at rest
npm run db:encrypt --database .claude/cache/temporal.db --password "$DB_PASSWORD"

# Decrypt on read (transparent)
# Uses SQLCipher extension
```

**Multi-user systems:**
```bash
# On shared systems, isolate user data
export CLAUDE_HOME="$HOME/.claude-$(whoami)"

# Prevents other users from reading ledgers/memory
umask 077
```

### Network Security

**HTTPS enforcement:**
```typescript
// MCP servers over HTTP must use HTTPS
if (serverConfig.url.startsWith('http://')) {
  throw new Error('Insecure HTTP connection - use HTTPS');
}

// Exception for localhost
if (serverConfig.url.startsWith('http://localhost') ||
    serverConfig.url.startsWith('http://127.0.0.1')) {
  // Allow for local development
}
```

**TLS certificate validation:**
```typescript
// Don't disable certificate validation (common mistake)
const client = new McpClient({
  url: serverUrl,
  rejectUnauthorized: true  // ✅ CORRECT (default)
});

// NEVER do this in production:
const client = new McpClient({
  url: serverUrl,
  rejectUnauthorized: false  // ❌ WRONG
});
```

**Network policy:**
```json
// Restrict MCP server network access
{
  "mcpServers": {
    "external-api": {
      "sandbox": {
        "network": "allow-domains",
        "allowedDomains": [
          "api.example.com",
          "cdn.example.com"
        ]
      }
    }
  }
}
```

### Security Updates

**Dependency updates:**
```bash
# Check for security updates weekly
npm outdated

# Update to latest secure versions
npm update

# Major version updates (manual review)
npm install package@latest
```

**Disclosure policy:**
```markdown
# SECURITY.md

## Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email: security@opc.dev

Include:
- Description of vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

We will respond within 48 hours.
```

### Security Checklist

**Before deployment:**
- [ ] All API keys in `.env` (not hardcoded)
- [ ] `.env` in `.gitignore`
- [ ] Pre-commit hooks installed (`npm run setup:hooks`)
- [ ] Audit log enabled (`.claude/cache/audit.log`)
- [ ] MCP servers sandboxed (minimal permissions)
- [ ] Dependencies scanned (`npm audit`)
- [ ] Secrets not in git history (`gitleaks detect`)
- [ ] File permissions set (`chmod 600 .env`)
- [ ] HTTPS enforced for remote MCP servers
- [ ] Database backups encrypted

**Ongoing maintenance:**
- Weekly: `npm audit` + `npm outdated`
- Monthly: Review audit logs for anomalies
- Quarterly: Rotate API keys
- Yearly: Security audit by external party

---

## Summary

- Layered defense: sandboxing, resource limits, audit logging
- Claude Code isolation via per-project config and CLAUDE_CONFIG_DIR
- MCP servers run with minimal required permissions
- Secrets never committed (pre-commit hooks enforce)
- Audit logs for forensics
- Supply chain security via npm audit + lock files
- Network security via HTTPS + certificate validation
- Regular security updates
