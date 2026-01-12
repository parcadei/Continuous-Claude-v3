# Structured Logging System for Continuous-Claude-v3

Comprehensive JSON-structured logging with correlation IDs, log levels by severity, and Loki/Promtail integration.

## Quick Start

```python
from scripts.core.logging_config import get_logger, setup_logging

# Initialize logging
setup_logging(script_name="my_script")

# Get logger
logger = get_logger("my_module", "my_script")

# Log with correlation ID
logger.info("Operation completed", trace_id="abc123", duration_ms=150)
```

## Log Format

All logs are JSON with these required fields:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "script": "memory_daemon",
  "function": "daemon_loop",
  "message": "Poll cycle completed",
  "trace_id": "abc123",
  "duration_ms": 1250.5
}
```

## Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Detailed flow tracing, variable states | `logger.debug("Query prepared", sql="SELECT * FROM...")` |
| INFO | Key operations, state changes, milestones | `logger.info("Connected to database")` |
| WARNING | Degraded performance, retries, expected exceptions | `logger.warning("Cache miss, fetching from DB")` |
| ERROR | Failures that don't crash the system | `logger.error("Query failed", error=str(e))` |
| CRITICAL | System-level failures, unrecoverable errors | `logger.critical("Database connection lost")` |

## Correlation IDs

Trace requests across the system:

```python
from scripts.core.logging_config import get_correlation_logger

# Create context manager with correlation ID
with get_correlation_logger("memory_daemon", trace_id) as logger:
    logger.info("Processing started")
    # All logs in this block have the same trace_id
    await process_request()
    logger.info("Processing completed")
```

## Per-Script Logging Examples

### memory_daemon.py

```python
from scripts.core.logging_config import get_logger, generate_correlation_id

logger = get_logger("memory_daemon", "memory_daemon")

# PID acquisition
def log_pid_acquisition(daemon_pid: int):
    logger.info("Acquired PID file", daemon_pid=daemon_pid)

# Poll cycle metrics
def log_poll_cycle():
    with logger.measure_time("poll_cycle") as timer:
        stale = find_stale_sessions()
    logger.info("Poll completed", stale_count=len(stale), duration_ms=timer.duration_ms)

# Extraction spawns
def spawn_extraction(session_id: str):
    logger.info("Spawning extraction", session_id=session_id, operation="extraction_spawn")
```

### recall_learnings.py

```python
from scripts.core.logging_config import get_logger, generate_correlation_id

logger = get_logger("recall_learnings", "recall_learnings")

# Query execution
def log_query_received(query: str, k: int):
    correlation_id = generate_correlation_id()
    logger.info("Query received", query_preview=query[:100], k=k)
    return correlation_id

# Cache behavior
def log_cache_hit(query_hash: str):
    logger.debug("Cache hit", query_hash=query_hash)

# Fallback detection
def log_backend_fallback(from_backend: str, to_backend: str, reason: str):
    logger.warning("Backend fallback", from_backend=from_backend, to_backend=to_backend, reason=reason)
```

### store_learning.py

```python
from scripts.core.logging_config import get_logger, generate_correlation_id

logger = get_logger("store_learning", "store_learning")

# Storage operations
def log_storage_start(session_id: str, learning_type: str):
    logger.info("Storage started", session_id=session_id, learning_type=learning_type)

# Deduplication
def log_deduplication(is_duplicate: bool, similarity: float):
    if is_duplicate:
        logger.info("Skipped - duplicate", similarity=similarity)
    else:
        logger.debug("Deduplication passed")
```

### stream_monitor.py

```python
from scripts.core.logging_config import get_logger, generate_correlation_id

logger = get_logger("stream_monitor", "stream_monitor")

# Event processing
def log_event_received(event_type: str, turn: int):
    logger.debug("Event received", event_type=event_type, turn_number=turn)

# Stuck detection
def log_stuck_detected(reason: str, tool: str | None = None):
    logger.warning("Agent stuck", reason=reason, consecutive_tool=tool)

# State transitions
def log_state_change(old_state: str, new_state: str):
    logger.info("State change", from_state=old_state, to_state=new_state)
```

### mcp_client.py

```python
from scripts.core.logging_config import get_logger, generate_correlation_id

logger = get_logger("mcp_client", "mcp_client")

# State transitions
def log_state_change(old: str, new: str):
    logger.info("State change", from_state=old, to_state=new)

# Tool calls
def log_tool_call(tool_name: str, call_id: str):
    logger.debug("Tool call", tool_name=tool_name, call_id=call_id)

# Reconnections
def log_reconnect(attempt: int, delay: int):
    logger.info("Reconnecting", attempt=attempt, delay_seconds=delay)
```

## Configuration

### Environment Variables

```bash
# Log level (default: INFO)
export LOG_LEVEL=DEBUG

# Log directory (default: ~/.claude/logs)
export LOG_DIR=/var/log/continuous-claude

# Enable/disable outputs
export LOG_TO_CONSOLE=true
export LOG_TO_FILE=true
export LOG_TO_LOKI=false

# Loki configuration
export LOKI_URL=http://localhost:3100/loki/api/v1/push
export LOKI_TIMEOUT=5.0

# Rotation settings
export LOG_RETENTION_DAYS=7
export LOG_MAX_SIZE_MB=10
export LOG_BACKUP_COUNT=3
```

### Programmatic Configuration

```python
from scripts.core.logging_config import setup_logging

setup_logging(
    log_level="DEBUG",
    log_dir="/var/log/continuous-claude",
    log_to_console=True,
    log_to_file=True,
    log_to_loki=True,
    loki_url="http://loki:3100/loki/api/v1/push",
    pretty_json=False,  # Set True for development
    script_name="my_script",
)
```

## Loki/Promtail Integration

### 1. Start Promtail

```yaml
# promtail-config.yaml
scrape_configs:
  - job_name: continuous-claude
    static_configs:
      - targets:
          - localhost
        labels:
          script: continuous-claude
          __path__: /home/user/.claude/logs/*.log
```

```bash
promtail --config.file=promtail-config.yaml
```

### 2. Grafana Query

```promql
{script="memory_daemon"} | json | level="ERROR"
```

### 3. Dashboard Panels

- **Log Volume**: `count_over_time({script="memory_daemon"} | json [5m])`
- **Error Rate**: `rate({script="memory_daemon"} | json | level="ERROR" [5m])`
- **Operation Duration**: `avg_over_time(duration_ms [5m])`

## Log Rotation

### Manual Rotation

```bash
uv run python scripts/core/log_rotation.py rotate --log-dir ~/.claude/logs
```

### As Daemon

```bash
uv run python scripts/core/log_rotation.py daemon --interval 3600 --retention-days 7
```

### Status

```bash
uv run python scripts/core/log_rotation.py status --log-dir ~/.claude/logs --json
```

## Error Context Capture

```python
from scripts.core.logging_config import capture_error_context

try:
    risky_operation()
except Exception as e:
    context = capture_error_context(
        logger,
        trace_id=correlation_id,
        additional_context={"user_id": "123"},
    )
    # context includes:
    # - timestamp
    # - trace_id
    # - system info (Python version, platform)
    # - memory usage
    # - recent logs
    # - exception details
```

## Decorators

### Log Function Calls

```python
from scripts.core.logging_config import log_function_call, get_logger

logger = get_logger("my_module", "my_script")

@log_function_call(logger, log_args=True, log_result=False)
async def process_data(data: dict) -> dict:
    return {"processed": True}
```

### Script Main Decorator

```python
from scripts.core.logging_config import script_main

@script_main("my_script", log_level="INFO")
async def main():
    # Logs: "Script my_script started"
    await do_work()
    # Logs: "Script my_script completed"
```

## File Structure

```
opc/scripts/core/
├── logging_config.py           # Core logging system
├── memory_daemon_logged.py     # Example integration
├── recall_learnings_logged.py  # Example integration
├── store_learning_logged.py    # Example integration
├── stream_monitor_logged.py    # Example integration
├── mcp_client_logged.py        # Example integration
├── log_rotation.py             # Rotation utility
└── LOGGING.md                  # This documentation
```

## Migration Guide

### From print() Statements

**Before:**
```python
print(f"[{timestamp}] Processing {session_id}")
```

**After:**
```python
logger.info("Processing session", session_id=session_id)
```

### From Simple Logging

**Before:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Processing")
```

**After:**
```python
from scripts.core.logging_config import get_logger, setup_logging
setup_logging(script_name="my_script")
logger = get_logger(__name__, "my_script")
logger.info("Processing")
```

## Troubleshooting

### Logs Not Appearing

1. Check log level: `export LOG_LEVEL=DEBUG`
2. Verify log directory exists: `ls ~/.claude/logs/`
3. Check file permissions: `chmod -R u+w ~/.claude/logs/`

### Loki Connection Issues

1. Verify Loki is running: `curl http://localhost:3100/ready`
2. Check network connectivity
3. Increase timeout: `export LOKI_TIMEOUT=10`

### High Log Volume

1. Set level to WARNING in production
2. Enable log rotation
3. Reduce backup count: `export LOG_BACKUP_COUNT=1`
