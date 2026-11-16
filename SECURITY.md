# Security

This document describes the security model for the Claude Continuity Kit.

## Threat Model

This toolkit is designed for **local development use** by a single developer on their own machine. It is NOT designed for:

- Multi-tenant environments
- Production deployments
- Network-exposed services
- Processing untrusted repositories

### Trust Assumptions

1. **Trusted User**: The developer running Claude Code is trusted
2. **Trusted Repository**: The repository being operated on is under the developer's control
3. **Local Execution**: All code executes locally on the developer's machine
4. **No Network Exposure**: Services are bound to localhost only

## What IS Protected

### Path Traversal Prevention

All file operations canonicalize paths before access. Path validation is implemented in Python
(`scripts/agentica/claude_scope.py`) via the `_canonicalize_path()` function:

```python
# Path validation in claude_scope.py
def _canonicalize_path(path: str, project_dir: str | None = None) -> str:
    # Expand ~ and resolve symlinks/..
    resolved = os.path.realpath(os.path.expanduser(path))

    if project_dir:
        allowed = os.path.realpath(os.path.expanduser(project_dir))

        # Ensure resolved path starts with allowed directory
        if not resolved.startswith(allowed + os.sep) and resolved != allowed:
            raise ValueError(
                f"Path '{path}' resolves to '{resolved}' which escapes "
                f"project directory '{allowed}'"
            )

    return resolved
```

Key protections:
- Symlink resolution before access (`os.path.realpath()`)
- Tilde expansion (`os.path.expanduser()`)
- Absolute path normalization
- Project boundary enforcement
- No `..` escape sequences honored
- macOS case-insensitive comparison handled

### Tool Allowlists

Hooks can restrict which tools are available to agents:

```json
{
  "allowed-tools": ["Read", "Glob", "Grep"]
}
```

This prevents agents from executing arbitrary bash commands when restricted.

### Broadcast Isolation

When using multi-agent patterns:
- Agents cannot see each other's full context
- Broadcast messages are one-way (coordinator -> agents)
- Agents cannot impersonate the coordinator
- Session IDs are validated before message routing

### Memory Isolation

- Each session has its own memory namespace
- Cross-session memory access requires explicit session ID
- Memory backend validates session ownership

## What is NOT Protected

### Partial Bash Injection Protection

While some input validation exists, **bash command injection is NOT fully protected**:

```bash
# A malicious repo could contain filenames like:
# "file; rm -rf /"
# which might be interpolated into commands
```

**Limitation**: Do not run this toolkit on untrusted repositories.

### No Authentication

- No user authentication
- No API key protection beyond `.env` file
- No session authentication

### No Rate Limiting

- No limits on API calls
- No limits on file operations
- No limits on memory writes

### No Audit Logging

- Security events are not logged
- No tamper-evident logs
- No forensic trail

### No Encryption at Rest

- Memory stores data unencrypted
- Session state is plaintext
- Credentials in `.env` are not encrypted

## Red Lines - What You Should Never Do

These are absolute prohibitions. Violating these creates serious security risks.

### NEVER Expose Over Network

```bash
# NEVER do this:
python -m http.server 8000  # serving project files
ngrok http 3000             # tunneling local services

# Services MUST bind to localhost only
```

### NEVER Run on Untrusted Repositories

```bash
# NEVER do this:
git clone https://untrusted-source/repo
cd repo
claude  # running Claude Code on untrusted code
```

Untrusted repos can contain:
- Malicious filenames with shell metacharacters
- Symlinks to sensitive system files
- Hook scripts that execute on clone

### NEVER Store Secrets in Memory

```python
# NEVER do this:
await memory.store("api_key", os.environ["API_KEY"])
await memory.store("password", user_password)
```

Memory is not encrypted and may be logged.

### NEVER Disable Path Validation

```python
# NEVER bypass path checks:
# unsafe_path = user_input  # NO - not validated
safe_path = _canonicalize_path(user_input, project_root)  # YES
```

Path validation is implemented in `scripts/agentica/claude_scope.py` and must be used
for all file operations that accept user-provided paths.

### NEVER Trust Agent Output Blindly

```python
# NEVER do this:
result = await agent.run(task)
exec(result)  # Executing agent output as code

# ALWAYS validate and sandbox
```

## Security Best Practices

### Environment Variables

```bash
# Use .env for secrets
cp .env.example .env
chmod 600 .env  # Restrict permissions
```

Never commit `.env` to version control.

### File Permissions

```bash
# Hooks should be executable but not world-writable
chmod 755 .claude/hooks/*.sh
chmod 644 .claude/settings.json
```

### Dependency Management

```bash
# Pin dependencies
uv lock
# Audit dependencies
uv pip audit
```

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. Allow 90 days for a fix before public disclosure

## Security Checklist for Contributors

Before submitting code:

- [ ] No hardcoded secrets or credentials
- [ ] All file paths are canonicalized via `_canonicalize_path()`
- [ ] User input is validated before shell interpolation
- [ ] New hooks respect tool allowlists
- [ ] Tests cover security-relevant edge cases
- [ ] Dependencies are from trusted sources
