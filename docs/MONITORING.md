# Continuous-Claude-v3 Production Monitoring System

## Overview

The Continuous-Claude-v3 monitoring system provides comprehensive observability for the memory daemon, stream processing, MCP clients, and database operations. It combines Prometheus for metrics collection, Grafana for visualization, and Alertmanager for alert routing.

## What the Monitoring System Does

### Core Functions

| Component | Purpose |
|-----------|---------|
| **Prometheus** | Time-series database that collects and stores all metrics |
| **Alertmanager** | Routes alerts to appropriate channels based on severity |
| **Grafana** | Visualization dashboards for real-time monitoring |
| **Health Checks** | Liveness, readiness, and startup probes for service health |
| **Stream Monitor** | Tracks Claude agent events and detects stuck agents |

### Why Each Component Exists

1. **Prometheus**: Provides a pull-based metrics collection model with PromQL for querying. Chosen for:
   - Simple deployment (single binary)
   - Efficient time-series storage
   - Strong alerting capabilities
   - Large ecosystem of exporters

2. **Alertmanager**: Handles alert deduplication, grouping, and routing:
   - Prevents alert storms
   - Routes by severity and category
   - Supports multiple notification channels
   - Handles alert silences

3. **Grafana**: Creates visual dashboards:
   - Real-time metrics visualization
   - Alert status overlays
   - Historical trend analysis
   - Cross-dashboard navigation

4. **Health Check System**: Three-tier health verification:
   - **Startup**: One-time checks (schema, directories)
   - **Readiness**: Traffic acceptance (connections, queue depth)
   - **Liveness**: Process health (PID valid, not zombie)

## Quick Start Guide

### Starting the Monitoring Stack

```bash
# From the project root
docker compose -f docker/monitoring-compose.yml up -d

# Verify all services are running
docker compose -f docker/monitoring-compose.yml ps
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | http://localhost:9090 | No auth |
| Grafana | http://localhost:3000 | admin/admin |
| Alertmanager | http://localhost:9093 | No auth |
| Health Check | http://localhost:8080/health | No auth |

### Checking System Health

```bash
# Run CLI health check
uv run python scripts/core/health_check.py status

# Check specific levels
uv run python scripts/core/health_check.py liveness
uv run python scripts/core/health_check.py readiness
uv run python scripts/core/health_check.py startup
```

### Viewing Metrics

```bash
# View all Prometheus metrics
curl http://localhost:9090/metrics

# View health check metrics
curl http://localhost:8080/metrics

# Query specific metrics
curl 'http://localhost:9090/api/v1/query?query=memory_daemon_queue_depth'
```

### Accessing Dashboards

1. **Main Overview**: http://localhost:3000/d/continuous-claude-overview
2. **Stream Monitoring**: http://localhost:3000/d/continuous-claude-stream
3. **Memory System**: http://localhost:3000/d/continuous-claude-memory
4. **MCP Clients**: http://localhost:3000/d/continuous-claude-mcp

## Key Metrics Reference

### Memory Daemon Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `memory_daemon_queue_depth` | Pending extractions | > 100 |
| `memory_daemon_cycles_total` | Total daemon cycles | N/A |
| `memory_daemon_extractions_total` | Total extractions | N/A |
| `memory_daemon_restarts_total` | Restart count | Spike |

### Stream Monitoring Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `stream_events_per_second` | Events processed rate | > 500/min |
| `stream_stuck_detections_total` | Stuck agent count | Any |
| `stream_redis_backlog` | Redis stream backlog | > 1000 |
| `stream_turn_count` | Current turn number | N/A |

### Database Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `pg_stat_activity_count` | Active connections | > 80% max |
| `pg_stat_statements_p95_ms` | Query latency p95 | > 2s |
| `pg_pool_connections_available` | Available pool connections | 0 |

### Process Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `process_memory_bytes` | RSS memory usage | > 90% system |
| `process_cpu_percent` | CPU usage | > 90% sustained |
| `process_open_fds` | Open file descriptors | > 80% limit |

## Alert Severity Levels

| Level | Meaning | Response Time | Notification |
|-------|---------|---------------|--------------|
| **P0** | Critical - Service down | Immediate | All channels |
| **P1** | High - Degraded service | 15 min | Slack + PagerDuty |
| **P2** | Medium - Warning | 1 hour | Slack |
| **P3** | Low - Informational | 24 hours | Dashboard only |

## Common Tasks

### Checking if Daemon is Running

```bash
# Method 1: Health check CLI
uv run python scripts/core/health_check.py liveness

# Method 2: Check PID file
cat ~/.claude/memory-daemon.pid
ps aux | grep memory_daemon

# Method 3: Prometheus query
curl 'http://localhost:9090/api/v1/query?query=up{job="memory-daemon"}'
```

### Restarting the Daemon

```bash
# Using health check with recovery
uv run python scripts/core/health_check.py status --recover

# Manual restart
pkill -f memory_daemon
uv run python scripts/core/memory_daemon.py start
```

### Viewing Active Alerts

```bash
# In Alertmanager
open http://localhost:9093

# Via CLI
curl http://localhost:9093/api/v1/alerts | jq

# In Grafana
open http://localhost:3000/alerting/list
```

### Creating a Silence

```bash
# Via Alertmanager UI
open http://localhost:9093/silences/new

# Match example for memory daemon alerts
matchers:
  - name: job
    value: memory-daemon
  - name: severity
    value: P2
```

## File Locations

```
 Continuous-Claude-v3/
├── docker/
│   └── monitoring-compose.yml     # Monitoring stack deployment
├── monitoring/
│   ├── prometheus.yml             # Prometheus configuration
│   ├── alert-rules.yml            # Alert definitions
│   ├── alertmanager.yml           # Alert routing
│   ├── recording-rules.yml        # Recording rules
│   ├── grafana/
│   │   └── provisioning/dashboards/ # Dashboard configs
│   └── blackbox/                  # External monitoring
├── opc/scripts/core/
│   ├── health_check.py            # Health check system
│   ├── metrics.py                 # Core metrics
│   ├── stream_monitor_metrics.py  # Stream metrics
│   └── metrics_grafana_dashboard.json
└── docs/
    ├── MONITORING.md              # This file
    ├── MONITORING_ARCHITECTURE.md # Architecture details
    ├── RUNBOOKS.md                # Operational procedures
    ├── MONITORING_API.md          # API reference
    └── MONITORING_TROUBLESHOOTING.md # Troubleshooting
```

## Next Steps

- **[Architecture](MONITORING_ARCHITECTURE.md)**: Detailed system architecture and data flows
- **[Runbooks](RUNBOOKS.md)**: Step-by-step procedures for common scenarios
- **[API Reference](MONITORING_API.md)**: Health endpoints, metrics, and CLI commands
- **[Troubleshooting](MONITORING_TROUBLESHOOTING.md)**: Common issues and fixes
