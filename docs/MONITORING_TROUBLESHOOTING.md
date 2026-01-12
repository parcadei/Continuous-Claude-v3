# Continuous-Claude-v3 Monitoring Troubleshooting Guide

## Table of Contents

1. [Common Errors and Fixes](#common-errors-and-fixes)
2. [Diagnostic Commands](#diagnostic-commands)
3. [Log Interpretation](#log-interpretation)
4. [Emergency Procedures](#emergency-procedures)

---

## Common Errors and Fixes

### Prometheus Not Scraping Targets

**Symptom:** No data in Grafana dashboards, targets show as DOWN

**Diagnosis:**
```bash
# Check target status
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Check Prometheus logs
docker logs cc3-prometheus 2>&1 | tail -50

# Test scrape endpoint manually
curl http://localhost:8080/metrics
```

**Causes and Fixes:**

| Cause | Fix |
|-------|-----|
| Target service down | Start the service (`uv run python scripts/core/memory_daemon.py start`) |
| Wrong scrape port | Update `monitoring/prometheus.yml` with correct port |
| Network blocked | Check firewall rules, ensure localhost access |
| Target not exposing metrics | Verify metrics endpoint returns data |

### Alertmanager Not Firing Alerts

**Symptom:** Alerts fire in Prometheus but no notifications sent

**Diagnosis:**
```bash
# Check for firing alerts
curl http://localhost:9093/api/v1/alerts | jq '. | length'

# Check Alertmanager config
curl http://localhost:9093/api/v1/status | jq '.config'

# Check receiver configuration
grep -A5 "receivers:" monitoring/alertmanager.yml
```

**Causes and Fixes:**

| Cause | Fix |
|-------|-----|
| Silenced alerts | Check `/silences` in Alertmanager UI |
| Inhibit rules suppressing | Review `inhibit_rules` in alertmanager.yml |
| Receiver misconfigured | Verify webhook URLs, SMTP settings |
| Route not matching | Check `matchers` in route configuration |

### Health Check Returns UNHEALTHY

**Symptom:** `/health` endpoint returns status: "unhealthy"

**Diagnosis:**
```bash
# Get full health report
curl http://localhost:8080/health | jq

# Check specific check
uv run python scripts/core/health_check.py check database_connection

# Check database connectivity
uv run python scripts/core/health_check.py check database_connection
```

**Common Issues:**

| Issue | Check | Fix |
|-------|-------|-----|
| Database not running | `docker ps | grep postgres` | Start PostgreSQL |
| Stale PID file | `ls -la ~/.claude/memory-daemon.pid` | Remove stale PID |
| Disk full | `df -h ~` | Clean up disk |
| Log file permission | `ls -la ~/.claude/*.log` | Fix permissions |

### Grafana Dashboards Empty

**Symptom:** Grafana shows "No data" in all panels

**Diagnosis:**
```bash
# Check Prometheus datasource
curl http://localhost:9090/api/v1/query?query=up

# Check datasource config in Grafana
curl http://localhost:3000/api/datasources

# Test query in Prometheus
curl 'http://localhost:9090/api/v1/query?query=memory_daemon_queue_depth'
```

**Causes and Fixes:**

| Cause | Fix |
|-------|-----|
| Datasource not configured | Add Prometheus datasource in Grafana UI |
| Datasource URL wrong | Update datasource URL to `http://prometheus:9090` |
| Time range too narrow | Expand time range in dashboard |
| Metrics not yet scraped | Wait for scrape interval (15s) |

### High Memory Usage

**Symptom:** `MemoryUsageHigh` alert, system slow

**Diagnosis:**
```bash
# Check memory by process
ps aux --sort=-rss | head -20

# Check Prometheus memory
curl http://localhost:9090/api/v1/query?query=process_resident_memory_bytes

# Check container memory
docker stats --no-stream

# Check for memory leaks
curl 'http://localhost:9090/api/v1/query?query=increase(process_resident_memory_bytes[1h])'
```

**Quick Fixes:**

```bash
# Restart Prometheus to clear cache
docker restart cc3-prometheus

# Restart memory daemon
pkill -f memory_daemon && uv run python scripts/core/memory_daemon.py start

# Drop caches (Linux)
sync && echo 3 > /proc/sys/vm/drop_caches
```

### Connection Pool Exhausted

**Symptom:** `ConnectionPoolExhausted` alert, new connections fail

**Diagnosis:**
```bash
# Check active connections
curl http://localhost:9090/api/v1/query?query=pg_pool_connections_active
curl http://localhost:9090/api/v1/query?query=pg_pool_connections_available

# Check PostgreSQL activity
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Check for idle transactions
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT pid, state, query, wait_event FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '10 minutes';"
```

**Fixes:**

```bash
# Kill long-running idle transactions
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < NOW() - INTERVAL '10 minutes';"

# Increase connection pool size (restart required)
# Edit DATABASE_URL to include pool_size=20
```

---

## Diagnostic Commands

### System Health

```bash
# Memory check
free -h
vmstat 1 5
ps aux --sort=-rss | head -15

# Disk check
df -h ~
du -sh ~/.claude/* 2>/dev/null
find ~/.claude -name "*.log" -exec ls -lh {} \; | head -10

# Process check
ps aux | grep -E "claude|prometheus|grafana|alertmanager" | grep -v grep
```

### Docker Container Health

```bash
# Container status
docker compose -f docker/monitoring-compose.yml ps

# Container logs
docker logs cc3-prometheus -f --tail 100
docker logs cc3-grafana -f --tail 100
docker logs cc3-alertmanager -f --tail 100

# Container resources
docker stats --no-stream

# Container networks
docker network ls
docker network inspect monitoring_monitoring
```

### Prometheus Diagnostics

```bash
# Target status
curl http://localhost:9090/api/v1/targets | jq

# Rule evaluation status
curl http://localhost:9090/api/v1/rules | jq

# Alert status
curl http://localhost:9090/api/v1/alerts | jq

# TSDB stats
curl http://localhost:9090/api/v1/status/tsdb

# Head dump for debugging
curl http://localhost:9090/api/v1/admin/tsdb/snapshot
```

### PostgreSQL Diagnostics

```bash
# Connection summary
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"

# Slow queries
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT query, calls, mean_time, max_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Table sizes
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT relname, pg_size_pretty(pg_relation_size(relid)) FROM pg_stat_user_tables ORDER BY pg_relation_size(relid) DESC LIMIT 10;"

# Locks
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT * FROM pg_locks WHERE NOT granted;"
```

### Redis Diagnostics

```bash
# Connection
redis-cli ping

# Memory usage
redis-cli info memory

# Key count
redis-cli info keyspace

# Slow queries
redis-cli slowlog get 10

# Connected clients
redis-cli info clients
```

### Health Check Debugging

```bash
# Verbose health check
uv run python scripts/core/health_check.py status --recover 2>&1

# Check individual components
uv run python scripts/core/health_check.py check database_connection
uv run python scripts/core/health_check.py check redis_connection
uv run python/scripts/core/health_check.py check disk_space

# View metrics
curl http://localhost:8080/metrics | grep health
```

---

## Log Interpretation

### Memory Daemon Log

**Location:** `~/.claude/memory-daemon.log`

**Log Format:**
```
2026-01-11 10:00:00,123 [INFO] memory_daemon: Starting extraction daemon
2026-01-11 10:00:01,456 [INFO] memory_daemon: Connected to PostgreSQL
2026-01-11 10:00:02,789 [INFO] memory_daemon: Processing session abc123
2026-01-11 10:00:03,012 [WARN] memory_daemon: Queue depth 95 approaching limit
2026-01-11 10:00:04,345 [ERROR] memory_daemon: Extraction failed for session xyz789
```

**Common Patterns:**

| Pattern | Meaning | Action |
|---------|---------|--------|
| `[INFO] Starting extraction daemon` | Normal startup | None |
| `[INFO] Connected to PostgreSQL` | DB connection OK | None |
| `[WARN] Queue depth X` | Growing backlog | Check system load |
| `[ERROR] Extraction failed` | Processing error | Check error details |
| `[ERROR] Connection refused` | DB unreachable | Check PostgreSQL |
| `[CRITICAL] Out of memory` | OOM | Increase memory |

### Prometheus Logs

**Location:** `docker logs cc3-prometheus`

**Common Messages:**

| Message | Meaning | Action |
|---------|---------|--------|
| `TSDB started` | Normal startup | None |
| `Scrape target updated` | New target added | Verify target |
| `Rule group X changed` | Alert rule modified | Check rules |
| `Cannot evaluate rule Y` | Rule evaluation error | Check rule syntax |
| `Storage cleanup triggered` | Retention cleanup | Normal |
| `WAL checkpoint forced` | Write-ahead log | May indicate slow disk |

### Alertmanager Logs

**Location:** `docker logs cc3-alertmanager`

**Common Messages:**

| Message | Meaning | Action |
|---------|---------|--------|
| `Route: Starting route` | Normal startup | None |
| `Alert Y sent to receiver Z` | Notification sent | Verify delivery |
| `Failed to send notification` | Delivery failed | Check receiver config |
| `Silenced alert X` | Alert suppressed | Review silence |
| `Inhibited alert Y` | Suppressed by higher priority | Expected during P0 |

### Grafana Logs

**Location:** `docker logs cc3-grafana`

**Common Messages:**

| Message | Meaning | Action |
|---------|---------|--------|
| `server started` | Normal startup | None |
| `Datasource updated` | Config changed | Verify settings |
| `Dashboard X saved` | User saved dashboard | Normal |
| `Rendering request failed` | Panel render error | Check panel config |
| `Query failed` | Data source error | Check datasource |

---

## Emergency Procedures

### Complete Monitoring Stack Restart

```bash
# Stop all monitoring containers
docker compose -f docker/monitoring-compose.yml down

# Clean up any zombie processes
pkill -9 -f "prometheus|alertmanager|grafana"

# Start monitoring stack
docker compose -f docker/monitoring-compose.yml up -d

# Verify all services healthy
docker compose -f docker/monitoring-compose.yml ps
```

### Emergency Daemon Recovery

```bash
# 1. Force kill any running daemon
pkill -9 -f memory_daemon
rm -f ~/.claude/memory-daemon.pid

# 2. Clear any stuck queue
# (If database is accessible)
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "UPDATE sessions SET memory_extracted_at = NOW() WHERE memory_extracted_at IS NULL LIMIT 100;"

# 3. Restart daemon fresh
uv run python scripts/core/memory_daemon.py start

# 4. Verify health
sleep 5 && uv run python scripts/core/health_check.py status
```

### Database Emergency Procedures

```bash
# Emergency: Stop all connections and restart PostgreSQL
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity;"

docker restart continuous-claude-postgres

# Emergency: Reset connection pool
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "SELECT pg_reload_conf();"

# Emergency: Recover from disk full
docker exec continuous-claude-postgres psql -U claude -d continuous_claude \
  -c "CHECKPOINT;"

# Remove old WAL files (if needed)
# docker exec continuous-claude-postgres sh -c "rm -f /var/lib/postgresql/data/pg_wal/*"
```

### Redis Emergency Procedures

```bash
# Emergency: Flush stuck queue (DANGEROUS - loses data)
redis-cli FLUSHALL

# Emergency: Kill blocked commands
redis-cli CLIENT KILL <client_id>

# Emergency: Reset memory
redis-cli CONFIG SET maxmemory 512mb
redis-cli CONFIG REWRITE

# Emergency: Recover from fork failure
redis-cli BGSAVE
```

### Prometheus Data Recovery

```bash
# Emergency: Force snapshot
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Emergency: Clean up corrupted data
curl -X POST http://localhost:9090/api/v1/admin/tsdb/clean_tombstones

# Emergency: Rebuild index (last resort)
# Stop Prometheus first
docker restart cc3-prometheus
```

### Emergency Contact Rollback

If recent changes caused issues:

```bash
# 1. Check git history
git log --oneline -10

# 2. Identify problematic commit
git show <commit_hash>

# 3. Revert changes
git revert <commit_hash>

# 4. Deploy previous version
docker compose -f docker/monitoring-compose.yml down
docker compose -f docker/monitoring-compose.yml up -d
```

### Emergency Communication

When P0 incident occurs:

```bash
# 1. Acknowledge in PagerDuty
# Open: https://your-org.pagerduty.com/incidents

# 2. Post to Slack emergency channel
# Message: "@channel P0 INCIDENT: [brief description]"

# 3. Document timeline
# Record all actions taken with timestamps

# 4. Escalate if not resolved in 15 minutes
```

### Downtime Procedures

If monitoring will be down for maintenance:

```bash
# 1. Create maintenance window in Alertmanager
curl -X POST http://localhost:9093/api/v1/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [{"name": "severity", "value": "P0", "isEqual": true}],
    "startsAt": "2026-01-11T10:00:00Z",
    "endsAt": "2026-01-11T11:00:00Z",
    "createdBy": "ops-team",
    "comment": "Planned maintenance window"
  }'

# 2. Notify team
# Post in Slack: "#continuous-claude-alerts"

# 3. Perform maintenance

# 4. Verify all services
uv run python scripts/core/health_check.py status

# 5. Close maintenance window (automatic based on endsAt)
```
