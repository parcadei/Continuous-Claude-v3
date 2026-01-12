# Continuous-Claude-v3 Monitoring API Reference

## Table of Contents

1. [Health Check Endpoints](#health-check-endpoints)
2. [Metrics Exposed](#metrics-exposed)
3. [Alert Rules Reference](#alert-rules-reference)
4. [CLI Commands](#cli-commands)
5. [Prometheus Queries](#prometheus-queries)

---

## Health Check Endpoints

### HTTP Endpoints

All health check endpoints return JSON responses and support Kubernetes probe compatibility.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Full health report |
| `/health/live` | GET | Liveness probe (is alive?) |
| `/health/ready` | GET | Readiness probe (can accept traffic?) |
| `/health/startup` | GET | Startup probe (schema initialized?) |
| `/metrics` | GET | Prometheus metrics |

### Response Format

```json
{
  "overall_status": "healthy|degraded|unhealthy|unknown",
  "level": "liveness|readiness|startup",
  "checks": [
    {
      "name": "pid_file",
      "status": "healthy",
      "level": "liveness",
      "message": "Process 12345 is alive",
      "details": {"pid": 12345},
      "timestamp": "2026-01-11T10:00:00Z",
      "recovery_action": null
    }
  ],
  "timestamp": "2026-01-11T10:00:00Z",
  "uptime_seconds": 3600.5
}
```

### Status Values

| Status | HTTP Code | Meaning |
|--------|-----------|---------|
| `healthy` | 200 | All checks passing |
| `degraded` | 200 | Some checks warning |
| `unhealthy` | 503 | Critical checks failing |
| `unknown` | 503 | Unable to determine status |

### Health Check Providers

| Check Name | Level | What It Validates |
|------------|-------|-------------------|
| `pid_file` | liveness | PID file exists and process running |
| `process_liveness` | liveness | Process not zombie, responsive |
| `database_connection` | readiness | PostgreSQL/SQLite connectivity |
| `redis_connection` | readiness | Redis connectivity (optional) |
| `queue_depth` | readiness | Extraction queue < 100 |
| `backlog` | readiness | Stale sessions < 50 |
| `disk_space` | readiness | Disk free > 1GB |
| `memory_pressure` | readiness | Memory usage < 90% |
| `log_file` | readiness | Log file writable |
| `database_schema` | startup | Required tables/columns exist |

### Example Usage

```bash
# Kubernetes liveness probe
curl -f http://localhost:8080/health/live

# Kubernetes readiness probe
curl -f http://localhost:8080/health/ready

# Full health report
curl http://localhost:8080/health | jq

# Prometheus metrics
curl http://localhost:8080/metrics
```

---

## Metrics Exposed

### Memory Daemon Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `memory_daemon_cycles_total` | Counter | - | Total daemon poll cycles |
| `memory_daemon_extractions_total` | Counter | session_id, project | Extraction attempts |
| `memory_daemon_extraction_duration_seconds` | Histogram | status | Extraction time |
| `memory_daemon_queue_depth` | Gauge | - | Pending extractions |
| `memory_daemon_active_extractions` | Gauge | - | Running extractions |
| `memory_daemon_restarts_total` | Counter | reason | Daemon restarts |
| `memory_daemon_stale_sessions_found` | Histogram | - | Stale sessions per cycle |

### Recall Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `recall_queries_total` | Counter | backend, search_type | Recall query count |
| `recall_query_latency_seconds` | Histogram | backend, search_type | Query latency |
| `recall_cache_hits_total` | Counter | cache_type | Cache hits |
| `recall_cache_misses_total` | Counter | cache_type | Cache misses |
| `recall_embedding_latency_seconds` | Histogram | provider | Embedding time |

### Store Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `store_operations_total` | Counter | backend, status | Store operation count |
| `store_latency_seconds` | Histogram | backend, phase | Store latency |
| `store_deduplication_skipped_total` | Counter | backend, reason | Deduplication skips |
| `store_embedding_time_seconds` | Histogram | provider | Embedding time |
| `store_learning_types_total` | Counter | type | Learning type distribution |
| `store_confidence_levels_total` | Counter | level | Confidence distribution |

### Stream Monitor Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `stream_events_processed_total` | Counter | agent_id, event_type | Events processed |
| `stream_stuck_detections_total` | Counter | agent_id, reason | Stuck detections |
| `stream_lag_seconds` | Histogram | agent_id | Event lag time |
| `stream_turn_count` | Gauge | agent_id | Current turn |
| `stream_event_queue_depth` | Gauge | agent_id | Event queue size |
| `stream_redis_publishes_total` | Counter | agent_id, status | Redis publishes |
| `stream_active_monitors` | Gauge | - | Active monitors |

### MCP Client Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_connection_state` | Gauge | server_name, transport | Connection state (0/1) |
| `mcp_tool_calls_total` | Counter | server_name, tool_name, status | Tool call count |
| `mcp_tool_latency_seconds` | Histogram | server_name, tool_name | Tool call latency |
| `mcp_connection_latency_seconds` | Histogram | server_name, transport | Connection time |
| `mcp_cache_hits_total` | Counter | server_name | Cache hits |
| `mcp_cache_misses_total` | Counter | server_name | Cache misses |
| `mcp_retries_total` | Counter | server_name, tool_name | Retry count |
| `mcp_servers_connected` | Gauge | - | Connected servers |
| `mcp_tools_available` | Gauge | server_name | Tools per server |

### System Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `postgres_pool_size` | Gauge | state | Connection pool size |
| `postgres_pool_waiters` | Gauge | - | Threads waiting for conn |
| `postgres_pool_acquire_time_seconds` | Histogram | - | Connection acquire time |
| `postgres_queries_total` | Counter | query_type | Query count |
| `postgres_query_latency_seconds` | Histogram | query_type | Query latency |
| `redis_memory_bytes` | Gauge | - | Redis memory usage |
| `redis_operations_total` | Counter | operation | Redis operation count |
| `redis_connected_clients` | Gauge | - | Connected clients |
| `process_memory_bytes` | Gauge | type | Process memory (rss/vms) |
| `process_cpu_percent` | Gauge | - | CPU usage % |
| `process_open_fds` | Gauge | - | Open file descriptors |

### Health Check Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `health_checks_total` | Counter | level, status | Check count |
| `recovery_actions_total` | Counter | action_type, success | Recovery actions |
| `health_check_duration_seconds` | Histogram | check_name | Check duration |

---

## Alert Rules Reference

### Availability Alerts

| Alert | Expression | For | Severity | Description |
|-------|------------|-----|----------|-------------|
| `DaemonNotRunning` | `absent(up{job="memory-daemon"} == 1)` | 1m | P0 | Daemon not running |
| `PostgreSQLUnreachable` | `pg_up{job="postgres"} == 0` | 1m | P0 | DB unreachable |
| `PostgreSQLContainerDown` | `container_last_seen{container="postgres"} == 0` | 2m | P1 | Container down |
| `MemoryDaemonHealthCheckFailed` | `memory_daemon_health_status != 1` | 3m | P1 | Health check failing |
| `MCPClientDisconnected` | `mcp_client_connected != 1` | 5m | P2 | MCP disconnected |

### Performance Alerts

| Alert | Expression | For | Severity | Description |
|-------|------------|-----|----------|-------------|
| `QueryLatencyP95Critical` | `pg_stat_statements_p95_ms > 5000` | 5m | P0 | Query > 5s p95 |
| `QueryLatencyP95High` | `pg_stat_statements_p95_ms > 2000` | 10m | P1 | Query > 2s p95 |
| `MemoryUsageHigh` | `(1 - available/total) > 0.80` | 5m | P1 | Memory > 80% |
| `MemoryUsageCritical` | `(1 - available/total) > 0.95` | 2m | P0 | Memory > 95% |
| `CPUUsageSustainedHigh` | `100 - cpu_idle > 90` | 15m | P1 | CPU > 90% |
| `QueueBacklogGrowing` | `increase(queue[10m]) > 100` | - | P2 | Queue growing |
| `ConnectionPoolNearMax` | `active/max > 0.8` | 5m | P2 | Pool > 80% |
| `EmbeddingGenerationSlow` | `embedding_duration_p95 > 5` | 10m | P2 | Embedding > 5s |

### Error Alerts

| Alert | Expression | For | Severity | Description |
|-------|------------|-----|----------|-------------|
| `ErrorRateCritical` | `rate(5xx[5m]) / rate(total[5m]) > 0.10` | 5m | P0 | Error rate > 10% |
| `ErrorRateHigh` | `rate(5xx[5m]) / rate(total[5m]) > 0.05` | 5m | P1 | Error rate > 5% |
| `ConnectionPoolExhausted` | `pool_available == 0` | 2m | P0 | No connections |
| `FailedExtractions` | `increase(extraction_failures[5m]) > 5` | 5m | P1 | Multiple failures |
| `EmbeddingFailures` | `increase(embedding_errors[5m]) > 10` | 5m | P1 | Embedding errors |
| `DeadlockDetected` | `increase(pg_deadlocks[5m]) > 0` | - | P2 | Deadlock occurred |

### Capacity Alerts

| Alert | Expression | For | Severity | Description |
|-------|------------|-----|----------|-------------|
| `DiskSpaceCritical` | `(1 - free/total) > 0.90` | 5m | P0 | Disk < 10% |
| `DiskSpaceWarning` | `(1 - free/total) > 0.85` | 10m | P1 | Disk < 15% |
| `PostgreSQLConnectionsNearMax` | `activity/max > 0.8` | 10m | P2 | DB conns > 80% |
| `CacheHitRateDeclining` | `rate(hits[1h]) / rate(requests[1h]) < 0.5` | 1h | P2 | Cache < 50% |
| `TableSizeGrowing` | `increase(size[24h]) > 10GB` | - | P3 | Table +10GB/day |
| `OpenFileDescriptorsHigh` | `open_fds / max_fds > 0.8` | 10m | P3 | FDs > 80% |

---

## CLI Commands

### Health Check CLI

```bash
# Full health status
uv run python scripts/core/health_check.py status
uv run python scripts/core/health_check.py status --recover

# Specific checks
uv run python scripts/core/health_check.py liveness
uv run python/scripts/core/health_check.py readiness
uv run python scripts/core/health_check.py startup

# Run specific check type
uv run python scripts/core/health_check.py check all
uv run python scripts/core/health_check.py check database_connection --recover

# Prometheus metrics
uv run python scripts/core/health_check.py metrics

# Run HTTP server (for Kubernetes)
uv run python scripts/core/health_check.py server --port 8080
```

### Health Check Output Example

```
============================================================
Health Report - LIVENESS
============================================================
Overall Status: HEALTHY
Timestamp: 2026-01-11T10:00:00Z

[OK] pid_file: Process 12345 is alive
[OK] process_liveness: Process responsive (status: running)
```

### Metrics Server

```bash
# Run metrics HTTP server
uv run python scripts/core/metrics_server.py --port 9091

# View metrics in browser
open http://localhost:9091/metrics
```

---

## Prometheus Queries

### Useful Queries

#### Daemon Health

```promql
# Is daemon running?
up{job="memory-daemon"}

# Daemon restart count (last hour)
increase(memory_daemon_restarts_total[1h])

# Daemon uptime in hours
(time() - process_start_time_seconds) / 3600
```

#### Queue Metrics

```promql
# Current queue depth
memory_daemon_queue_depth

# Queue growth rate
rate(memory_daemon_queue_depth[5m])

# Extraction rate
rate(memory_daemon_extractions_total[5m])

# Extraction success rate
rate(memory_daemon_extraction_duration_seconds{status="success"}[5m])
```

#### Query Latency

```promql
# Query latency p95
pg_stat_statements_p95_ms

# Query latency p99
histogram_quantile(0.99, rate(pg_stat_statements_duration_ms_bucket[5m]))

# Slow queries (> 1s)
pg_stat_statements_duration_ms > 1000
```

#### Stream Monitoring

```promql
# Active stream monitors
stream_active_monitors

# Events per second
rate(stream_events_processed_total[1m])

# Stuck agents
stream_active_stuck_agents

# Stuck detection rate
rate(stream_stuck_detections_total[5m])

# Redis publish failures
rate(stream_redis_publishes_total{status="failed"}[5m])
```

#### Memory and CPU

```promql
# Process memory in MB
process_resident_memory_bytes / 1024 / 1024

# System memory usage
(1 - (memory_available_bytes / memory_total_bytes)) * 100

# CPU usage
process_cpu_percent

# GC pressure
rate(process_gc_collects_total[5m])
```

#### Database Connection Pool

```promql
# Pool utilization
pg_pool_connections_active / pg_pool_connections_max

# Available connections
pg_pool_connections_available

# Waiters count
pg_pool_waiters
```

#### Cache Performance

```promql
# Cache hit rate
rate(recall_cache_hits_total[1h]) /
  (rate(recall_cache_hits_total[1h]) + rate(recall_cache_misses_total[1h]))

# Cache hit rate by type
rate(recall_cache_hits_total{cache_type="embedding"}[1h])
```

### Recording Rules

Recording rules pre-compute frequently used queries:

```yaml
# In monitoring/recording-rules.yml
groups:
  - name: derived_metrics
    rules:
      - record: memory_daemon_extractions_per_minute
        expr: rate(memory_daemon_extractions_total[1m]) * 60

      - record: query_latency_p95
        expr: histogram_quantile(0.95, rate(pg_stat_statements_duration_ms_bucket[5m]))

      - record: stream_events_per_minute
        expr: sum(rate(stream_events_processed_total[1m])) * 60
```

---

## Grafana Dashboard URLs

| Dashboard | URL |
|-----------|-----|
| Overview | http://localhost:3000/d/continuous-claude-overview |
| Stream Monitoring | http://localhost:3000/d/continuous-claude-stream |
| Memory System | http://localhost:3000/d/continuous-claude-memory |
| MCP Clients | http://localhost:3000/d/continuous-claude-mcp |
| Alert Dashboard | http://localhost:3000/d/alert-dashboard |

---

## Alertmanager Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/alerts` | GET | List all alerts |
| `/api/v1/alerts?silenced=true` | GET | List including silenced |
| `/api/v1/silences` | GET | List silences |
| `/api/v1/silences` | POST | Create silence |
| `/api/v1/status` | GET | Alertmanager status |
