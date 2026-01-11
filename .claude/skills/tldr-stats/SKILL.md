---
description: Show TLDR token savings, hook activity, and performance metrics for the current session
---

# TLDR Stats Skill

Show TLDR token savings, hook activity, and performance metrics for the current session.

## When to Use
- After working for a while to see how much you've saved
- Before/after comparisons of TLDR effectiveness
- Debugging whether TLDR/hooks are being used
- Showing value of Continuous Claude infrastructure
- Seeing which hooks are active and their metrics

## Instructions

Query the TLDR daemon for current session stats and display them in a formatted view.

### Steps

1. **Get daemon status with session stats and hook stats**:
```bash
cd $CLAUDE_PROJECT_DIR/opc/packages/tldr-code && source .venv/bin/activate && python3 -c "
import socket
import json
import hashlib
import os

project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
session_id = os.environ.get('CLAUDE_SESSION_ID', 'unknown')

# Get socket path
hash_val = hashlib.md5(project_dir.encode()).hexdigest()[:8]
sock_path = f'/tmp/tldr-{hash_val}.sock'

try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)
    sock.sendall(json.dumps({'cmd': 'status', 'session': session_id}).encode() + b'\n')
    data = sock.recv(65536)
    sock.close()
    result = json.loads(data)

    uptime_sec = result.get('uptime', 0)
    uptime_min = int(uptime_sec // 60)
    uptime_hr = int(uptime_min // 60)
    uptime_str = f'{uptime_hr}h {uptime_min % 60}m' if uptime_hr > 0 else f'{uptime_min}m'

    # All sessions stats
    all_stats = result.get('all_sessions', {})
    total_raw = all_stats.get('total_raw_tokens', 0)
    total_tldr = all_stats.get('total_tldr_tokens', 0)
    total_saved = total_raw - total_tldr
    savings_pct = (total_saved / total_raw * 100) if total_raw > 0 else 0

    print('=' * 60)
    print('TLDR Token Savings & Hook Activity')
    print('=' * 60)
    print(f'Daemon Uptime:     {uptime_str}')
    print(f'Active Sessions:   {all_stats.get(\"active_sessions\", 0)}')
    print()
    print('Token Usage:')
    print(f'  Raw tokens:      {total_raw:,}')
    print(f'  TLDR tokens:     {total_tldr:,}')
    print(f'  Saved:           {total_saved:,} ({savings_pct:.1f}%)')
    print()
    print('Cache:')
    salsa = result.get('salsa_stats', {})
    hits = salsa.get('cache_hits', 0)
    misses = salsa.get('cache_misses', 0)
    hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0
    print(f'  Cache hits:      {hits}')
    print(f'  Cache misses:    {misses}')
    print(f'  Hit rate:        {hit_rate:.1f}%')

    # Hook stats (P8)
    hook_stats = result.get('hook_stats', {})
    if hook_stats:
        print()
        print('Hook Activity:')
        for name, stats in sorted(hook_stats.items()):
            invocations = stats.get('invocations', 0)
            success_rate = stats.get('success_rate', 100)
            metrics = stats.get('metrics', {})

            # Format metrics inline
            metrics_str = ''
            if metrics:
                metric_parts = []
                for k, v in metrics.items():
                    if isinstance(v, float):
                        metric_parts.append(f'{k}={v:.1f}')
                    else:
                        metric_parts.append(f'{k}={v}')
                metrics_str = f' [{', '.join(metric_parts)}]'

            print(f'  {name}: {invocations} calls ({success_rate:.0f}% success){metrics_str}')
    else:
        print()
        print('Hook Activity:')
        print('  No hook activity recorded yet')

    print('=' * 60)

except FileNotFoundError:
    print('TLDR daemon not running.')
    print('Start with: tldr daemon start --project \$CLAUDE_PROJECT_DIR')
except Exception as e:
    print(f'Error: {e}')
"
```

2. **Show historical stats from JSONL** (if available):
```bash
STATS_FILE="$HOME/.cache/tldr/session_stats.jsonl"
if [ -f "$STATS_FILE" ]; then
    echo ""
    echo "Historical Stats (last 5 sessions):"
    tail -5 "$STATS_FILE" | python3 -c "
import sys
import json

for line in sys.stdin:
    try:
        r = json.loads(line.strip())
        raw = r.get('raw_tokens', 0)
        tldr = r.get('tldr_tokens', 0)
        pct = r.get('savings_percent', 0)
        ts = r.get('timestamp', 'unknown')[:16]
        print(f'  {ts}: {raw:,} raw -> {tldr:,} tldr ({pct:.1f}% saved)')
    except:
        pass
"
fi
```

### Output Format

```
============================================================
TLDR Token Savings & Hook Activity
============================================================
Daemon Uptime:     2h 34m
Active Sessions:   3

Token Usage:
  Raw tokens:      234,521
  TLDR tokens:     12,847
  Saved:           221,674 (94.5%)

Cache:
  Cache hits:      847
  Cache misses:    23
  Hit rate:        97.4%

Hook Activity:
  impact-refactor: 5 calls (100% success) [analyses_run=5, results_found=3]
  post-edit-diagnostics: 42 calls (100% success) [edits_analyzed=42, type_errors=8, lint_issues=15]
  smart-search-router: 23 calls (100% success) [queries_routed=23, literal_queries=12, structural_queries=8, semantic_queries=3]
  tldr-read-enforcer: 156 calls (100% success) [reads_intercepted=156, layers_returned=312]
============================================================

Historical Stats (last 5 sessions):
  2026-01-11T10:30: 13,421 raw -> 2,052 tldr (84.7% saved)
  2026-01-11T09:15: 45,230 raw -> 5,421 tldr (88.0% saved)
```

## Arguments
None required. Uses environment variables:
- `CLAUDE_PROJECT_DIR`: Project path for daemon connection
- `CLAUDE_SESSION_ID`: Current session ID for session-specific stats

## Hook Metrics Explained

| Hook | Metrics |
|------|---------|
| `tldr-read-enforcer` | reads_intercepted, layers_returned |
| `post-edit-diagnostics` | edits_analyzed, type_errors, lint_issues |
| `smart-search-router` | queries_routed, literal/structural/semantic_queries |
| `impact-refactor` | analyses_run, results_found |
