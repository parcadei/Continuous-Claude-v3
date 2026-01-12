# Continuous-Claude-v3 Monitoring Runbooks

## Table of Contents

1. [Daemon Crash Investigation](#daemon-crash-investigation)
2. [Slow Query Diagnosis](#slow-query-diagnosis)
3. [Stuck Agent Recovery](#stuck-agent-recovery)
4. [Memory Pressure Handling](#memory-pressure-handling)
5. [Alert Response Procedures](#alert-response-procedures)

---

## Daemon Crash Investigation

### Symptoms
- `DaemonNotRunning` alert fired
- Memory extractions stopped
- PID file missing or stale

### Diagnosis Steps

```bash
# 1. Check if daemon process exists
ps aux | grep memory_daemon

# 2. Check PID file
cat ~/.claude/memory-daemon.pid
# If file exists, check if process is running
kill -0 $(cat ~/.claude/memory-daemon.pid) 2>/dev/null && echo "Running" || echo "Stale"

# 3. Check logs for crash reason
tail -100 ~/.claude/memory-daemon.log

# 4. Check health endpoint (if server still running)
curl http://localhost:8080/health

# 5. Check Prometheus for last successful scrape
curl 'http://localhost:9090/api/v1/query?query=up{job="memory-daemon"}'
```

### Common Causes and Fixes

| Cause | Fix |
|-------|-----|
| **Out of Memory** | Increase system memory or reduce queue processing |
| **Database Connection Lost** | Check PostgreSQL connectivity, restart daemon |
| **Schema Mismatch** | Run migrations before restarting |
| **Disk Full** | Clean up logs and old data |

### Recovery Procedure

```bash
# 1. Stop any zombie processes
pkill -9 -f memory_daemon
rm -f ~/.claude/memory-daemon.pid

# 2. Check disk space
df -h ~

# 3. Check database connectivity
uv run python scripts/core/health_check.py check database_connection

# 4. Start daemon fresh
cd /Users/grantray/Github/Continuous-Claude-v3
uv run python scripts/core/memory_daemon.py start

# 5. Verify health
uv run python scripts/core/health_check.py status
```

### Post-Incident Actions

1. Review logs for root cause
2. Check if pattern exists (recurring crashes)
3. Consider adding restart limits or health monitoring
4. Document incident in team channel

---

## Slow Query Diagnosis

### Symptoms
- `QueryLatencyP95High` or `QueryLatencyP95Critical` alert
- User reports of slow responses
- Connection pool exhaustion

### Diagnosis Steps

```bash
# 1. Identify slow queries in PostgreSQL
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT query, calls, mean_time, max_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 20;"

# 2. Check active connections
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# 3. Check for locks
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT * FROM pg_locks WHERE NOT granted;"

# 4. Check connection pool status
curl http://localhost:9090/api/v1/query?query=pg_pool_connections_active
curl http://localhost:9090/api/v1/query?query=pg_pool_connections_available

# 5. Check query latency trend in Grafana
open http://localhost:3000/d/continuous-claude-overview
```

### Common Causes and Fixes

| Cause | Fix |
|-------|-----|
| **Missing Index** | Add index on WHERE/JOIN columns |
| **N+1 Queries** | Batch queries or use eager loading |
| **Connection Leak** | Fix connection cleanup in code |
| **Long-Running Transaction** | Find and kill stuck transactions |
| **I/O Bottleneck** | Add SSD or increase memory |

### Immediate Mitigation

```bash
# 1. Kill long-running transactions (> 5 minutes)
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND now() - state_change > interval '5 minutes';"

# 2. Flush connection pool (restart application)
pkill -HUP -f memory_daemon

# 3. Increase connections temporarily (if max_connections allows)
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "ALTER SYSTEM SET max_connections = 200; SELECT pg_reload_conf();"
```

### Long-Term Fixes

1. Add missing indexes based on slow query analysis
2. Implement query result caching
3. Add connection timeout enforcement
4. Consider read replicas for heavy queries

---

## Stuck Agent Recovery

### Symptoms
- `StuckDetected` or `StreamStuckAgent` alert
- Agent not progressing (no tool results for extended period)
- Turn count not incrementing

### Diagnosis Steps

```bash
# 1. Check active stream monitors
curl http://localhost:9090/api/v1/query?query=stream_active_monitors

# 2. Check stuck agent count
curl http://localhost:9090/api/v1/query?query=stream_active_stuck_agents

# 3. Get stuck agent details
curl http://localhost:9090/api/v1/query?query=stream_stuck_detections_total

# 4. Check stream event rate (should be > 0)
curl http://localhost:9090/api/v1/query?query=rate(stream_events_processed_total[5m])

# 5. Check Redis connection
redis-cli ping
```

### Recovery Procedures

#### Automatic Recovery (Preferred)

```bash
# The stream monitor has built-in recovery - verify it's active
uv run python scripts/core/stream_monitor.py status

# If monitoring is active, stuck detection should trigger auto-recovery
# Check recovery count
curl http://localhost:9090/api/v1/query?query=stream_stuck_recoveries_total
```

#### Manual Recovery

```bash
# 1. Identify stuck agent PID
ps aux | grep -E "claude|agent" | grep -v grep

# 2. Check what the agent is doing
# Look for stuck state in logs
tail -f ~/.claude/sessions/*/logs/*.log 2>/dev/null | grep -i "stuck\|hung\|timeout"

# 3. Force restart the agent (if safe to do so)
kill -TERM <agent_pid>
# OR for force kill
kill -9 <agent_pid>

# 4. Start fresh agent session
claude # Start new session
```

#### Clearing Stuck State in Redis

```bash
# 1. List stuck agent streams
redis-cli KEYS "agent:*:events"

# 2. Check stream lengths
redis-cli XLEN agent:<agent_id>:events

# 3. Clear stuck agent stream (if needed)
redis-cli DEL agent:<agent_id>:events

# 4. Reset stuck detection counters
redis-cli DEL stream:stuck:<agent_id>
```

### Preventing Stuck Agents

| Strategy | Implementation |
|----------|----------------|
| **Timeout Limits** | Set `max_turn_time` per agent |
| **Tool Call Limits** | Limit consecutive same-tool calls |
| **Heartbeat Monitoring** | Check for activity every 30s |
| **Graceful Shutdown** | Handle SIGTERM properly |

---

## Memory Pressure Handling

### Symptoms
- `MemoryUsageHigh` or `MemoryUsageCritical` alert
- System becoming slow or unresponsive
- Out of memory errors in logs

### Diagnosis Steps

```bash
# 1. Check system memory
free -h
vmstat 1 5

# 2. Check process memory
ps aux --sort=-rss | head -20
curl http://localhost:9090/api/v1/query?query=process_resident_memory_bytes

# 3. Check memory trend in Grafana
open http://localhost:3000/d/continuous-claude-memory

# 4. Check for memory leaks (RSS growth over time)
curl 'http://localhost:9090/api/v1/query?query=increase(process_resident_memory_bytes[1h])'

# 5. Check GC activity
curl http://localhost:9090/api/v1/query?query=rate(process_gc_collects_total[5m])
```

### Immediate Mitigation

```bash
# 1. Force garbage collection (Python)
# Can add to application code:
import gc
gc.collect()

# 2. Clear memory caches (Linux)
sync
echo 3 > /proc/sys/vm/drop_caches

# 3. Restart memory-intensive processes
pkill -HUP memory_daemon

# 4. Check for memory ballooning in containers
docker stats --no-stream
```

### Finding Memory Leaks

```python
# Use tracemalloc to find memory leaks
import tracemalloc

tracemalloc.start()

# ... run problematic code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 memory allocations ]")
for stat in top_stats[:10]:
    print(stat)
```

### Long-Term Solutions

| Solution | When to Apply |
|----------|---------------|
| **Increase System RAM** | If system is consistently near 90% |
| **Add Swap Space** | Temporary relief for memory spikes |
| **Optimize Data Structures** | If Python objects are too large |
| **Implement Pagination** | If loading too much data at once |
| **Use Generators** | For large data processing |
| **Connection Pool Limits** | If DB connections consume too much |

---

## Alert Response Procedures

### P0 Critical Alerts (Immediate Response)

**Alerts:**
- `DaemonNotRunning`
- `PostgreSQLUnreachable`
- `MemoryUsageCritical`
- `ConnectionPoolExhausted`

**Response SLA:** < 5 minutes

```bash
# 1. Acknowledge in PagerDuty
open https://your-org.pagerduty.com/incidents

# 2. Check Grafana for context
open http://localhost:3000/alerting/list

# 3. Join incident channel
# Notify team in Slack: #continuous-claude-critical

# 4. Execute emergency procedures (see above sections)

# 5. Post-mortem if service was down > 15 minutes
```

### P1 High Alerts (15-Minute Response)

**Alerts:**
- `MemoryDaemonHealthCheckFailed`
- `QueryLatencyP95High`
- `MemoryUsageHigh`
- `CPUUsageSustainedHigh`

**Response SLA:** < 15 minutes

```bash
# 1. Check Grafana for trends
open http://localhost:3000/d/continuous-claude-overview

# 2. Acknowledge in Slack
# Post in #continuous-claude-alerts

# 3. Monitor for escalation to P0
# If not resolved in 30 minutes, escalate to P0

# 4. Document in incident log
```

### P2 Medium Alerts (1-Hour Response)

**Alerts:**
- `QueueBacklogGrowing`
- `ConnectionPoolNearMax`
- `EmbeddingGenerationSlow`
- `FailedExtractions`

**Response SLA:** < 1 hour

```bash
# 1. Check during next work cycle
# No immediate action required

# 2. Add to maintenance backlog
# Create ticket if not already present

# 3. Monitor for worsening
curl http://localhost:9090/api/v1/query?query=alert_name
```

### P3 Low Alerts (24-Hour Response)

**Alerts:**
- `DiskSpaceWarning`
- `CacheHitRateDeclining`
- `TableSizeGrowing`
- `LowExtractionRate`

**Response SLA:** < 24 hours

```bash
# 1. Review during regular maintenance
# Add to sprint backlog

# 2. Plan fix for next cycle
```

### Creating Silences

When you need to suppress alerts during maintenance:

```bash
# Via Alertmanager UI
open http://localhost:9093/silences/new

# Or via API
curl -X POST http://localhost:9093/api/v1/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "job", "value": "memory-daemon", "isEqual": true},
      {"name": "severity", "value": "P2", "isEqual": true}
    ],
    "startsAt": "2026-01-11T10:00:00Z",
    "endsAt": "2026-01-11T12:00:00Z",
    "createdBy": "ops-team",
    "comment": "Planned maintenance window"
  }'
```

### Post-Incident Procedure

1. **Document**: Create incident report with timeline
2. **Analyze**: Root cause analysis in blameless post-mortem
3. **Fix**: Implement prevention measures
4. **Test**: Verify fix works in staging
5. **Share**: Brief team on lessons learned

---

## Emergency Contacts

| Role | Contact | When |
|------|---------|------|
| Primary On-Call | PagerDuty rotation | P0 alerts |
| Infrastructure Lead | @infra-lead | System outages |
| Database Admin | @dba | PostgreSQL issues |
| Application Lead | @dev-team | Code-related issues |

---

## Quick Reference Commands

```bash
# Health check
uv run python scripts/core/health_check.py status

# View all alerts
curl http://localhost:9093/api/v1/alerts | jq

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# View Grafana alerts
open http://localhost:3000/alerting/list

# Restart monitoring stack
docker compose -f docker/monitoring-compose.yml restart

# Restart memory daemon
pkill -f memory_daemon && uv run python scripts/core/memory_daemon.py start

# Check disk usage
df -h ~

# Check memory
free -h

# View logs
tail -f ~/.claude/memory-daemon.log
```
