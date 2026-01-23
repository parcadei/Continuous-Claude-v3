# Continuous Claude - Teammate Setup Guide

Get up and running with Continuous Claude in 5 minutes.

## Prerequisites

Install these before starting:

- **Docker Desktop** - Required for PostgreSQL database
- **Node.js 18+** - For CLI and tools
- **Python 3.11+** with `uv` - For memory extraction daemon
- **Claude Code CLI** - The AI assistant runtime

Verify installations:
```bash
docker --version
node --version
python --version
uv --version
```

---

## Quick Start (5 Steps)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd continuous-claude
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env if needed (default values work for most users)
```

**Key variables:**
- `POSTGRES_PORT=5432` - Change if port conflicts
- `DATABASE_URL` - Auto-generated, no changes needed
- `CLAUDE_OPC_DIR` - Points to `opc/` directory

### 3. Start Docker Services

```bash
docker compose up -d
```

Verify database is running:
```bash
docker ps | grep continuous-claude-postgres
```

### 4. Run Setup Wizard

```bash
npm install
npm run setup
```

The wizard will:
- Check Docker connectivity
- Create database tables
- Install Python dependencies
- Verify daemon configuration

### 5. Verify Installation

```bash
# Check session status
npm run status

# Check daemon
npm run daemon:status
```

You should see:
- Active sessions (if any Claude instances running)
- Daemon status (running/stopped)
- Last memory extraction time

---

## Windows-Specific Notes

### Path Handling

Windows uses backslashes (`\`) but the codebase expects forward slashes (`/`) in most places:

- **Environment variables**: Use forward slashes in `.env` paths
  ```bash
  CLAUDE_OPC_DIR=C:/Users/david.hayes/continuous-claude/opc
  ```
- **Docker paths**: Always use forward slashes
- **Node scripts**: Auto-converts paths (no action needed)

### Docker Desktop

- **Required**: WSL 2 backend (Settings → General → Use WSL 2)
- **Port conflicts**: If 5432 is taken, change `POSTGRES_PORT` in `.env`
- **Startup time**: First `docker compose up` may take 1-2 minutes

### Shell Considerations

**PowerShell** (recommended):
```powershell
npm run setup
npm run daemon:start
```

**Git Bash**:
```bash
npm run setup
npm run daemon:start
```

**CMD** (works but limited):
```cmd
npm run setup
npm run daemon:start
```

---

## Key Features

### Session Tracking

Every Claude instance registers a session on startup:
- **Heartbeat**: Updates every 2 minutes
- **Visibility**: See other active sessions via status command
- **Cleanup**: Auto-expires after 10 minutes of inactivity

### Memory Extraction Daemon

Background process that extracts learnings from conversations:
- **Polling**: Checks for new messages every 30 seconds
- **Extraction**: Uses Claude to identify key insights
- **Storage**: Saves to PostgreSQL with embeddings for semantic search

Start daemon:
```bash
npm run daemon:start
```

Stop daemon:
```bash
npm run daemon:stop
```

Check logs:
```bash
npm run daemon:logs
```

### Session Resurrection (NEW!)

When resuming a session after timeout:
1. Old session marked as ended
2. New session created with same conversation ID
3. New work captured as separate session entry
4. Memory extraction continues seamlessly

**Example flow:**
```
Session A: 10:00-10:15 (timeout)
Resume:    10:30 → Creates Session B
           Same conversation, new tracking
           Memories extracted for both sessions
```

### Cross-Terminal Awareness

When multiple Claude instances run:
- Each sees the others in status output
- File conflict warnings if editing same files
- Shared memory pool via PostgreSQL

---

## Troubleshooting

### Port Conflicts

**Symptom**: `docker compose up` fails with "port already allocated"

**Fix**:
1. Edit `.env` and change `POSTGRES_PORT` (e.g., `5433`)
2. Update `DATABASE_URL` to match:
   ```
   DATABASE_URL=postgresql://claude:claude_dev@localhost:5433/continuous_claude
   ```
3. Restart Docker: `docker compose down && docker compose up -d`

### Database Connection Issues

**Symptom**: "Connection refused" or "could not connect to server"

**Fix**:
```bash
# Check Docker is running
docker ps

# Restart database
docker compose restart postgres

# Verify connection
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT 1;"
```

### Daemon Not Starting

**Symptom**: `npm run daemon:start` fails or daemon stops immediately

**Fix**:
```bash
# Check logs for errors
npm run daemon:logs

# Common issues:
# 1. Missing Python dependencies
uv pip install -r opc/requirements.txt

# 2. Database not accessible
# Verify DATABASE_URL in .env matches Docker port

# 3. Environment not loaded
# Make sure .env exists and has correct values
```

### TypeScript Hooks Not Working

**Symptom**: Hooks in `.claude/hooks/` fail to execute

**Fix**:
```bash
# Build TypeScript hooks
cd .claude/hooks
npm install
npm run build

# Verify dist/ folder exists
ls dist/
```

### Memory Recall Returns No Results

**Symptom**: `recall_learnings.py` shows no memories

**Possible causes**:
1. Daemon hasn't run yet (no memories extracted)
2. Database empty (run daemon for a few minutes)
3. Query too specific (try broader terms)

**Verify**:
```bash
# Check if memories exist
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT COUNT(*) FROM archival_memory;"

# Should show > 0 if daemon has extracted learnings
```

---

## Next Steps

Once setup is complete:

1. **Run Claude** - Your sessions will auto-register
2. **Start daemon** - Begins memory extraction
3. **Check status** - Verify tracking works
4. **Recall memories** - Test semantic search

```bash
# Example: Start working
cd your-project
claude

# In another terminal: Monitor system
cd continuous-claude
npm run status
npm run daemon:logs
```

For advanced features, see:
- `ARCHITECTURE.md` - System design details
- `opc/README.md` - OPC framework overview
- `.claude/skills/` - Available skills and workflows
