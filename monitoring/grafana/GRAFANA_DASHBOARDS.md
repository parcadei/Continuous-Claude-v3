# Continuous-Claude-v3 Grafana Dashboards

This document provides comprehensive specifications for the Grafana monitoring dashboards.

## Dashboard Overview

| Dashboard | UID | Refresh | Description |
|-----------|-----|---------|-------------|
| Overview | `continuous-claude-overview` | 30s | System-wide health and status |
| Memory System | `continuous-claude-memory` | 30s | Learning pipeline monitoring |
| Stream Monitoring | `continuous-claude-stream` | 30s | Event processing monitoring |
| MCP Clients | `continuous-claude-mcp` | 30s | MCP integration metrics |
| Performance | `continuous-claude-performance` | 30s | Bottleneck detection |

## Data Source Configuration

All dashboards use Prometheus as the primary data source:

```yaml
datasource:
  type: prometheus
  uid: prometheus
```

### Required Prometheus Jobs

```yaml
scrape_configs:
  # Memory Daemon
  - job_name: 'memory-daemon'
    metrics_path: /metrics

  # PostgreSQL with pg_exporter
  - job_name: 'postgres'
    metrics_path: /metrics

  # Node exporter for system metrics
  - job_name: 'node'
    metrics_path: /metrics

  # Custom application metrics
  - job_name: 'continuous-claude-app'
    metrics_path: /health/metrics
```

---

## 1. Overview Dashboard

**UID:** `continuous-claude-overview`
**Panels:** 17 | **Variables:** 3

### Panel Specifications

| Panel ID | Title | Type | Visualization | Refresh |
|----------|-------|------|---------------|---------|
| 1 | Daemon Status | stat | Single stat | 30s |
| 2 | PostgreSQL Status | stat | Single stat | 30s |
| 3 | Daemon Restarts (1h) | stat | Single stat | 30s |
| 4 | Active Sessions | stat | Single stat | 30s |
| 5 | PostgreSQL Connections | timeseries | Line chart | 30s |
| 6 | PostgreSQL Query Latency | timeseries | Line chart | 30s |
| 7 | Redis Memory Usage | timeseries | Line chart | 30s |
| 8 | Redis Connected Clients | timeseries | Line chart | 30s |
| 9 | CPU Usage | timeseries | Line chart | 30s |
| 10 | Memory Usage (RSS) | timeseries | Line chart | 30s |
| 11 | Disk Usage | gauge | Gauge | 30s |
| 12 | Firing Alerts (Last 1h) | stat | Single stat | 30s |
| 13 | Firing Alerts (Last 24h) | stat | Single stat | 30s |
| 14 | Active Stream Monitors | timeseries | Line chart | 30s |
| 15 | MCP Servers Connected | timeseries | Line chart | 30s |
| 16 | Process Uptime | timeseries | Line chart | 30s |
| 17 | Extraction Queue Depth | timeseries | Line chart | 30s |

### Variables

| Name | Type | Query | Description |
|------|------|-------|-------------|
| `job` | Query | `label_values(up, job)` | Filter by Prometheus job |
| `severity` | Query | `label_values(ALERTS, severity)` | Filter alerts by severity |
| `pg_state` | Query | `label_values(pg_stat_activity, state)` | Filter PostgreSQL state |

### Alert Thresholds

- Daemon Status: green=1 (UP), red=0 (DOWN)
- CPU Usage: yellow=70%, red=90%
- Memory Usage: yellow=512MB, red=1024MB
- Disk Usage: yellow=80%, red=90%
- Queue Depth: yellow=50, red=100

---

## 2. Memory System Dashboard

**UID:** `continuous-claude-memory`
**Panels:** 19 | **Variables:** 4

### Panel Specifications

| Panel ID | Title | Type | Visualization | Refresh |
|----------|-------|------|---------------|---------|
| 1 | Extractions Rate (per min) | timeseries | Line chart | 30s |
| 2 | Extraction Status | piechart | Pie chart | 30s |
| 3 | Extraction Duration | timeseries | Line chart | 30s |
| 4 | Queue Backlog | timeseries | Line chart | 30s |
| 5 | Recall Query Latency | timeseries | Line chart | 30s |
| 6 | Recall Queries by Backend | timeseries | Line chart | 30s |
| 7 | Recall Search Type Distribution | piechart | Pie chart | 30s |
| 8 | Cache Hit Rate | timeseries | Line chart | 30s |
| 9 | Cache Hits vs Misses | timeseries | Line chart | 30s |
| 10 | Store Operations by Status | timeseries | Line chart | 30s |
| 11 | Store Latency by Phase | timeseries | Line chart | 30s |
| 12 | Deduplication Rate | timeseries | Line chart | 30s |
| 13 | Learning Types Distribution | barchart | Bar chart | 30s |
| 14 | Confidence Levels | piechart | Pie chart | 30s |
| 15 | Embedding Latency | timeseries | Line chart | 30s |
| 16 | Backend Switches | timeseries | Line chart | 30s |
| 17 | Results Returned Distribution | histogram | Histogram | 30s |
| 18 | Stale Sessions Found | timeseries | Line chart | 30s |
| 19 | Error Rate by Type | timeseries | Line chart | 30s |

### Variables

| Name | Type | Query | Description |
|------|------|-------|-------------|
| `backend` | Query | `label_values(recall_queries_total, backend)` | PostgreSQL/SQLite |
| `search_type` | Query | `label_values(recall_queries_total, search_type)` | text/vector/hybrid |
| `store_status` | Query | `label_values(store_operations_total, status)` | success/error/skipped |
| `learning_type` | Query | `label_values(store_learning_types_total, type)` | FAILED_APPROACH, etc. |

### Key Metrics

```promql
# Extraction rate
rate(memory_daemon_extractions_total[1m])

# Recall latency percentiles
histogram_quantile(0.95, rate(recall_query_latency_seconds_bucket[5m]))

# Cache hit rate
rate(recall_cache_hits_total[5m]) /
  (rate(recall_cache_hits_total[5m]) + rate(recall_cache_misses_total[5m]))

# Deduplication rate
rate(store_deduplication_skipped_total[5m])
```

---

## 3. Stream Monitoring Dashboard

**UID:** `continuous-claude-stream`
**Panels:** 15 | **Variables:** 3

### Panel Specifications

| Panel ID | Title | Type | Visualization | Refresh |
|----------|-------|------|---------------|---------|
| 1 | Active Stream Monitors | stat | Single stat | 30s |
| 2 | Events Processed (Last Hour) | stat | Single stat | 30s |
| 3 | Stuck Detections (Last Hour) | stat | Single stat | 30s |
| 4 | Redis Publishes (1h) | stat | Single stat | 30s |
| 5 | Events per Minute | timeseries | Line chart | 30s |
| 6 | Events by Type | timeseries | Line chart | 30s |
| 7 | Event Type Distribution | piechart | Pie chart | 30s |
| 8 | Stream Lag | timeseries | Line chart | 30s |
| 9 | Stuck Detection Count | timeseries | Line chart | 30s |
| 10 | Stuck Detection by Reason | barchart | Bar chart | 30s |
| 11 | Turn Count by Agent | timeseries | Line chart | 30s |
| 12 | Queue Depth by Agent | timeseries | Line chart | 30s |
| 13 | Redis Publish Status | timeseries | Line chart | 30s |
| 14 | Processing Latency by Event Type | heatmap | Heatmap | 30s |
| 15 | Total Events Heatmap | heatmap | Heatmap | 30s |

### Variables

| Name | Type | Query | Description |
|------|------|-------|-------------|
| `agent_id` | Query | `label_values(stream_events_processed_total, agent_id)` | Agent identifier |
| `event_type` | Query | `label_values(stream_events_processed_total, event_type)` | thinking/tool_use/etc |
| `stuck_reason` | Query | `label_values(stream_stuck_detections_total, reason)` | consecutive_tool |

### Key Metrics

```promql
# Events per minute
rate(stream_events_processed_total[1m]) * 60

# Stream lag percentiles
histogram_quantile(0.95, rate(stream_lag_seconds_bucket[5m]))

# Stuck detections
increase(stream_stuck_detections_total[5m])

# Queue depth
stream_event_queue_depth
```

---

## 4. MCP Clients Dashboard

**UID:** `continuous-claude-mcp`
**Panels:** 18 | **Variables:** 4

### Panel Specifications

| Panel ID | Title | Type | Visualization | Refresh |
|----------|-------|------|---------------|---------|
| 1 | MCP Servers Connected | stat | Single stat | 30s |
| 2 | Active Connections | stat | Single stat | 30s |
| 3 | Total Tool Calls (1h) | stat | Single stat | 30s |
| 4 | Success Rate (1h) | stat | Single stat | 30s |
| 5 | Connection State Distribution | piechart | Pie chart | 30s |
| 6 | Tool Call Rate by Server | timeseries | Line chart | 30s |
| 7 | Tool Call Latency p50 | timeseries | Line chart | 30s |
| 8 | Tool Call Latency p95 | timeseries | Line chart | 30s |
| 9 | Tool Call Latency p99 | timeseries | Line chart | 30s |
| 10 | Tool Call Status | timeseries | Line chart | 30s |
| 11 | Error Rate by Server | timeseries | Line chart | 30s |
| 12 | Tools Available per Server | timeseries | Line chart | 30s |
| 13 | Cache Hit Rate | timeseries | Line chart | 30s |
| 14 | Cache Hits vs Misses | timeseries | Line chart | 30s |
| 15 | Retry Count | timeseries | Line chart | 30s |
| 16 | Connection Latency by Transport | timeseries | Line chart | 30s |
| 17 | Top Tools by Call Volume | barchart | Bar chart | 30s |
| 18 | Slowest Tools (p99 Latency) | barchart | Bar chart | 30s |

### Variables

| Name | Type | Query | Description |
|------|------|-------|-------------|
| `server` | Query | `label_values(mcp_connection_state, server_name)` | MCP server name |
| `tool` | Query | `label_values(mcp_tool_calls_total, tool_name)` | Tool name |
| `transport` | Query | `label_values(mcp_connection_state, transport)` | stdio/sse/http |
| `status` | Query | `label_values(mcp_tool_calls_total, status)` | success/error/retry |

### Key Metrics

```promql
# Success rate
increase(mcp_tool_calls_total{status="success"}[1h]) /
  (increase(mcp_tool_calls_total{status="success"}[1h]) +
   increase(mcp_tool_calls_total{status="error"}[1h]))

# Latency percentiles
histogram_quantile(0.95, rate(mcp_tool_latency_seconds_bucket[5m]))

# Cache hit rate
rate(mcp_cache_hits_total[5m]) /
  (rate(mcp_cache_hits_total[5m]) + rate(mcp_cache_misses_total[5m]))

# Error rate
rate(mcp_tool_calls_total{status="error"}[5m]) /
  rate(mcp_tool_calls_total[5m])
```

---

## 5. Performance Dashboard

**UID:** `continuous-claude-performance`
**Panels:** 18 | **Variables:** 4

### Panel Specifications

| Panel ID | Title | Type | Visualization | Refresh |
|----------|-------|------|---------------|---------|
| 1 | Query Latency p50 | timeseries | Line chart | 30s |
| 2 | Query Latency p95 | timeseries | Line chart | 30s |
| 3 | Query Latency p99 | timeseries | Line chart | 30s |
| 4 | Baseline Comparison | timeseries | Line chart | 30s |
| 5 | Embedding Generation Time | timeseries | Line chart | 30s |
| 6 | Memory Usage Over Time | timeseries | Line chart | 30s |
| 7 | CPU Usage Over Time | timeseries | Line chart | 30s |
| 8 | PostgreSQL Pool Utilization | timeseries | Line chart | 30s |
| 9 | Connection Pool Waiters | timeseries | Line chart | 30s |
| 10 | Pool Acquire Time | timeseries | Line chart | 30s |
| 11 | Redis Operations Rate | timeseries | Line chart | 30s |
| 12 | Latency Heatmap (All Operations) | heatmap | Heatmap | 30s |
| 13 | Throughput vs Latency | timeseries | Line chart | 30s |
| 14 | Thread Count | timeseries | Line chart | 30s |
| 15 | PostgreSQL Active Transactions | timeseries | Line chart | 30s |
| 16 | PostgreSQL Queries by Type | timeseries | Line chart | 30s |
| 17 | GC Activity | timeseries | Line chart | 30s |
| 18 | GC Time | timeseries | Line chart | 30s |

### Variables

| Name | Type | Query | Description |
|------|------|-------|-------------|
| `query_type` | Query | `label_values(pg_stat_statements, query_type)` | select/insert/update |
| `redis_operation` | Query | `label_values(redis_operations_total, operation)` | get/set/lpush |
| `pg_state` | Query | `label_values(pg_stat_activity, state)` | active/idle |
| `baseline_window` | Interval | `1h, 6h, 24h, 7d` | Baseline comparison |

### Key Metrics

```promql
# Latency percentiles across services
histogram_quantile(0.95, rate(pg_stat_statements_seconds_bucket[5m]))
histogram_quantile(0.95, rate(redis_operation_latency_seconds_bucket[5m]))
histogram_quantile(0.95, rate(recall_query_latency_seconds_bucket[5m]))

# Baseline comparison
rate(pg_stat_statements_seconds_sum[5m]) / rate(pg_stat_statements_seconds_count[5m])
vs
rate(pg_stat_statements_seconds_sum[24h]) / rate(pg_stat_statements_seconds_count[24h])

# Pool utilization
pg_pool_connections_busy / pg_pool_connections_max * 100

# Throughput vs latency correlation
rate(pg_stat_statements_seconds_count[5m])  # queries/s
histogram_quantile(0.95, rate(pg_stat_statements_seconds_bucket[5m])) * 1000  # ms
```

---

## Alert Integrations

All dashboards integrate with the following alert rules defined in `alert-rules.yml`:

### Critical Alerts (P0)

| Alert | Expression | Panel Reference |
|-------|------------|-----------------|
| DaemonNotRunning | `absent(up{job="memory-daemon"} == 1)` | Overview Panel 1 |
| PostgreSQLUnreachable | `pg_up{job="postgres"} == 0` | Overview Panel 2 |
| ErrorRateCritical | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.10` | MCP Panel 11 |
| ConnectionPoolExhausted | `pg_pool_connections_available == 0` | Performance Panel 8 |
| DiskSpaceCritical | `(1 - (disk_available_bytes / disk_total_bytes)) > 0.90` | Overview Panel 11 |

### High Priority Alerts (P1)

| Alert | Expression | Panel Reference |
|-------|------------|-----------------|
| QueryLatencyP95High | `pg_stat_statements_p95_ms > 2000` | Performance Panels 1-3 |
| MemoryUsageHigh | `(1 - (memory_available_bytes / memory_total_bytes)) > 0.80` | Performance Panel 6 |
| FailedExtractions | `increase(extraction_failures_total[5m]) > 5` | Memory System Panels 2-3 |
| ErrorRateHigh | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05` | MCP Panel 11 |

---

## Installation

### 1. Start Grafana and Prometheus

```bash
cd monitoring
docker-compose up -d
```

### 2. Import Dashboards

Dashboards are auto-provisioned via `provisioning/dashboards/dashboard.yml`.

### 3. Configure Data Source

Ensure Prometheus is configured in `provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

---

## Customization

### Adding New Panels

1. Add panel definition to the JSON dashboard file
2. Define PromQL query in `targets[0].expr`
3. Configure `fieldConfig.defaults` for units and thresholds
4. Add to `templating.list` if filtering is needed

### Modifying Thresholds

Edit `fieldConfig.defaults.thresholds.steps` in each panel:

```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    {"color": "green", "value": null},
    {"color": "yellow", "value": YOUR_LOW_THRESHOLD},
    {"color": "red", "value": YOUR_HIGH_THRESHOLD}
  ]
}
```

### Adding Variables

Add to `templating.list` in the dashboard JSON:

```json
{
  "current": {"selected": false, "text": "All", "value": "$__all"},
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "definition": "label_values(YOUR_METRIC, YOUR_LABEL)",
  "includeAll": true,
  "label": "Display Name",
  "multi": true,
  "name": "variable_name",
  "query": "label_values(YOUR_METRIC, YOUR_LABEL)",
  "refresh": 2,
  "type": "query"
}
```

---

## Dashboard Hierarchy

```
Overview (System at a glance)
    |
    +-- Memory System (Learning pipeline)
    |       +-- Extractions
    |       +-- Recall queries
    |       +-- Store operations
    |       +-- Deduplication
    |
    +-- Stream Monitoring (Event processing)
    |       +-- Events processed
    |       +-- Stuck detection
    |       +-- Turn tracking
    |
    +-- MCP Clients (External integrations)
    |       +-- Tool calls
    |       +-- Connection state
    |       +-- Cache performance
    |
    +-- Performance (Bottleneck detection)
            +-- Latency percentiles
            +-- Resource usage
            +-- Baseline comparison
```

---

## Best Practices

1. **Refresh Interval**: 30s is suitable for most panels. Use 5s for critical metrics.
2. **Time Range**: Default to `now-6h` to `now` for operational visibility.
3. **Threshold Colors**: Green -> Yellow -> Red for progressive alerting.
4. **Variable Filtering**: Always include job/instance variables for multi-instance setups.
5. **Panel Linking**: Use dashboard links for navigation between related dashboards.
6. **Annotation**: Enable default annotations for alert and deployment markers.
