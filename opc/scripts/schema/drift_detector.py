#!/usr/bin/env python3
"""Detect schema drift between init-db.sql and running database."""

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Set


def parse_init_db_sql(path: str) -> Set[str]:
    """Parse table names from init-db.sql."""
    with open(path) as f:
        content = f.read()
    pattern = r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)'
    return set(re.findall(pattern, content, re.IGNORECASE))


def get_running_tables() -> Set[str]:
    """Get table names from running PostgreSQL database."""
    result = subprocess.run(
        ['docker', 'exec', 'continuous-claude-postgres',
         'psql', '-U', 'claude', '-d', 'continuous_claude',
         '-c', "\\dt"],
        capture_output=True, text=True
    )
    tables = set()
    for line in result.stdout.split('\n'):
        if line and not line.startswith('-') and not line.startswith('List'):
            parts = line.split('|')
            if len(parts) >= 1:
                table_name = parts[0].strip()
                if table_name and table_name != 'Schema':
                    tables.add(table_name)
    return tables


def main():
    # Determine paths relative to repo root
    repo_root = Path(__file__).parent.parent.parent
    init_db_sql = repo_root / "opc" / "init-db.sql"

    if not init_db_sql.exists():
        print(json.dumps({
            "status": "error",
            "message": f"init-db.sql not found at {init_db_sql}"
        }, indent=2))
        sys.exit(1)

    init_tables = parse_init_db_sql(str(init_db_sql))
    running_tables = get_running_tables()

    only_in_init = init_tables - running_tables
    only_in_running = running_tables - init_tables

    result = {
        "status": "sync" if not (only_in_init or only_in_running) else "drift",
        "init_db_sql_tables": sorted(init_tables),
        "running_db_tables": sorted(running_tables),
        "only_in_init_db_sql": sorted(only_in_init),
        "only_in_running_db": sorted(only_in_running),
    }

    print(json.dumps(result, indent=2))

    if result["status"] == "drift":
        print(f"\nSchema drift detected!")
        if only_in_init:
            print(f"  Tables in init-db.sql but NOT in DB: {', '.join(sorted(only_in_init))}")
        if only_in_running:
            print(f"  Tables in DB but NOT in init-db.sql: {', '.join(sorted(only_in_running))}")
        sys.exit(1)
    else:
        print("\nSchema is synchronized.")
        sys.exit(0)


if __name__ == "__main__":
    main()
