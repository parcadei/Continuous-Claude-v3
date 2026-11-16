# Module: Setup Wizard

## Overview

Interactive build script for opinionated setup. Configures Docker stack (PostgreSQL, Redis, Sandbox), backfills preferences from JSONL logs, and optionally installs math features with LMStudio.

---

## Setup Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLAUDE CONTINUITY KIT v3 - SETUP WIZARD                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  Welcome! This wizard will configure your Claude Continuity Kit.

  Step 1/6: Checking system requirements...
    ✓ Python 3.11+
    ✓ Docker & Docker Compose
    ✓ uv package manager
    ○ LMStudio (optional, for math verification)

  Step 2/6: Docker Stack
    [X] PostgreSQL with pgvector
    [X] Redis for caching
    [X] Sandbox runner (isolated code execution)

    Starting docker compose... done ✓

  Step 3/6: Database Initialization
    Creating tables... done ✓
    Running migrations... done ✓

  Step 4/6: Personalization
    Found 47 JSONL session logs in ~/.claude/logs/
    Backfilling preferences... done ✓
    - Detected preference: typescript (89% of file writes)
    - Detected preference: pytest (100% of test runs)
    - Detected preference: postgres (75% of DB references)

  Step 5/6: Math Features (Optional)
    [ ] Install math skills? (sympy, mpmath, lean4)
    [ ] Download Godel-Prover model for LMStudio?

    LMStudio URL [localhost:1234]: _______________

  Step 6/6: Finalizing
    Generating skill-rules.json... done ✓
    Registering hooks... done ✓
    Creating backup of existing config... done ✓

  ✓ Setup complete!

  Next steps:
    1. Start a Claude Code session: claude
    2. Monitor agents: uv run python scripts/agent_monitor_tui/main.py
    3. View docs: docs/getting-started.md
```

---

## Implementation

### Main Script

```python
#!/usr/bin/env python3
# scripts/setup_wizard.py

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.progress import Progress

console = Console()

async def main():
    console.print("[bold]CLAUDE CONTINUITY KIT v3 - SETUP WIZARD[/bold]\n")

    # Step 1: Check requirements
    await check_requirements()

    # Step 2: Docker stack
    if Confirm.ask("Start Docker stack (PostgreSQL, Redis, Sandbox)?", default=True):
        await start_docker_stack()

    # Step 3: Database
    await initialize_database()

    # Step 4: Personalization
    if Confirm.ask("Backfill preferences from existing JSONL logs?", default=True):
        await backfill_preferences()

    # Step 5: Math features
    if Confirm.ask("Install math features (sympy, Lean4, Godel-Prover)?", default=False):
        lmstudio_url = Prompt.ask("LMStudio URL", default="http://localhost:1234")
        await install_math_features(lmstudio_url)

    # Step 6: Finalize
    await finalize_setup()

    console.print("\n[bold green]✓ Setup complete![/bold green]")
```

### Docker Compose

```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: claude_continuity
      POSTGRES_USER: claude
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-claude_dev}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-coordination.sql:/docker-entrypoint-initdb.d/01-coordination.sql
      - ./init-temporal.sql:/docker-entrypoint-initdb.d/02-temporal.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U claude"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  sandbox:
    build:
      context: .
      dockerfile: Dockerfile.sandbox
    environment:
      - SANDBOX_MODE=isolated
    volumes:
      - sandbox_tmp:/tmp/sandbox
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

volumes:
  postgres_data:
  redis_data:
  sandbox_tmp:
```

---

## JSONL Backfill

### Pattern Mining

```python
# scripts/backfill_preferences.py

async def backfill_preferences():
    """Extract patterns from JSONL session logs."""

    jsonl_dir = Path.home() / '.claude' / 'logs'
    patterns = defaultdict(Counter)

    for jsonl_file in jsonl_dir.glob('*.jsonl'):
        async for event in read_jsonl(jsonl_file):
            # File extension preferences
            if event.get('type') == 'tool_use' and event.get('tool_name') == 'Write':
                path = event.get('parameters', {}).get('path', '')
                ext = Path(path).suffix
                if ext:
                    patterns['file_extension'][ext] += 1

            # Test framework preferences
            if event.get('type') == 'tool_use' and event.get('tool_name') == 'Bash':
                cmd = event.get('parameters', {}).get('command', '')
                if 'pytest' in cmd:
                    patterns['test_framework']['pytest'] += 1
                elif 'jest' in cmd:
                    patterns['test_framework']['jest'] += 1
                elif 'vitest' in cmd:
                    patterns['test_framework']['vitest'] += 1

            # Database preferences
            if 'postgres' in str(event).lower():
                patterns['database']['postgres'] += 1
            if 'sqlite' in str(event).lower():
                patterns['database']['sqlite'] += 1

    # Save to preferences table
    for category, choices in patterns.items():
        top_choice = choices.most_common(1)[0]
        await save_preference(category, top_choice[0], top_choice[1])

    return patterns
```

---

## Math Features Installation

```python
async def install_math_features(lmstudio_url: str):
    """Install math skills and configure LMStudio."""

    # Install Python math libraries
    await run_command("uv pip install sympy mpmath scipy numpy")

    # Clone math skills
    math_skills_dir = Path('.claude/skills/math')
    if not math_skills_dir.exists():
        await run_command("cp -r .claude/skills/_math_template .claude/skills/math")

    # Configure LMStudio URL
    config = load_config()
    config['math'] = {
        'enabled': True,
        'lmstudio_url': lmstudio_url,
        'prover_model': 'Goedel-Prover-V2-8B',
    }
    save_config(config)

    # Test LMStudio connection
    try:
        response = await httpx.get(f"{lmstudio_url}/v1/models")
        if response.status_code == 200:
            console.print(f"  [green]✓ LMStudio connected[/green]")
        else:
            console.print(f"  [yellow]○ LMStudio not responding (will work when started)[/yellow]")
    except:
        console.print(f"  [yellow]○ LMStudio not available (start it later)[/yellow]")
```

---

## Backup & Upgrade Detection

```python
async def detect_existing_installation():
    """Detect v2 installation and prepare upgrade."""

    v2_indicators = [
        Path('.claude/settings.json'),
        Path('thoughts/ledgers'),
        Path('.claude/skills'),
    ]

    v2_present = any(p.exists() for p in v2_indicators)

    if v2_present:
        console.print("  [yellow]Existing v2 installation detected[/yellow]")

        # Backup
        backup_dir = Path('.claude/backup') / datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir.mkdir(parents=True)

        for indicator in v2_indicators:
            if indicator.exists():
                shutil.copytree(indicator, backup_dir / indicator.name)

        console.print(f"  [green]✓ Backup created: {backup_dir}[/green]")

    return v2_present
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/setup_wizard.py` | Main setup script |
| `scripts/backfill_preferences.py` | JSONL pattern mining |
| `docker/docker-compose.yml` | Docker stack |
| `docker/Dockerfile.sandbox` | Sandbox container |
| `docker/init-coordination.sql` | Coordination schema |
| `docker/init-temporal.sql` | Temporal memory schema |

## Dependencies

```toml
[project.optional-dependencies]
setup = [
    "rich>=13.0.0",
    "httpx>=0.25.0",
]
```

---

## Opinionated Setup

v3 requires full Docker stack - no lite mode:
- Wizard detects OS (Windows/Mac/Linux)
- Downloads Docker if not present
- Pulls required images
- Configures PostgreSQL, Redis, PgBouncer, gVisor sandbox

```python
async def setup_wizard():
    """Interactive setup wizard."""
    console.print("[bold]Claude Continuity Kit v3 Setup[/bold]")

    # Check Docker
    if not await check_docker_installed():
        console.print("Docker not found. Installing...")
        await install_docker_for_os()

    # Pull images
    images = [
        "postgres:16-alpine",
        "redis:7-alpine",
        "edoburu/pgbouncer:latest",
        "gcr.io/gvisor/runsc:latest"
    ]
    for image in images:
        await pull_docker_image(image)

    # Initialize stack
    await run_docker_compose_up()

    # Run migrations
    await run_postgres_migrations()

    console.print("[green]Setup complete![/green]")
```
