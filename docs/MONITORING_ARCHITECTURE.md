# Continuous-Claude-v3 Monitoring Architecture

## System Architecture Diagram

```
+---------------------------------------------------------------------+
|                         Continuous-Claude-v3                         |
|                                                                      |
|  +------------------+    +------------------+    +-----------------+ |
|  |   Claude Agent   |    |  Memory Daemon   |    |   MCP Clients   | |
|  +--------+---------+    +--------+---------+    +--------+--------+ |
|           |                       |                       |          |
|           v                       v                       v          |
|  +--------+---------+    +--------+---------+    +--------+--------+ |
|  | Stream Monitor   |    | Health Check     |    |  MCP Metrics    | |
|  | (stream_json)    |    | (health_check.py)|    |  (mcp module)   | |
|  +--------+---------+    +--------+---------+    +--------+--------+ |
|           |                       |                       |          |
+-----------+-----------------------+-----------------------+----------+
            |                       |                       |
            v                       v                       v
+---------------------------------------------------------------------+
|                        Application Metrics Layer                     |
|                                                                      |
|  +--------------------+  +--------------------+  +----------------+ |
|  | MemoryDaemonMetrics|  | RecallMetrics      |  | MCPMetrics     | |
|  | StreamMonitorMetrics|  | StoreMetrics       |  | SystemMetrics  | |
|  +--------------------+  +--------------------+  +----------------+ |
|                                                                      |
+------------------------------+--------------------------------------+
                               |
                               v
+---------------------------------------------------------------------+
|                     Prometheus Collectors                             |
|                                                                      |
|  +---------------------------------------------------------------+  |
|  |                  Prometheus Server (:9090)                     |  |
|  |  +----------------+  +----------------+  +------------------+ |  |
|  |  | Alert Rules    |  | Recording      |  | TSDB Storage     | |  |
|  |  | (alert-rules)  |  | Rules          |  | (30 day retention)| |  |
|  |  +----------------+  +----------------+  +------------------+ |  |
|  +---------------------------------------------------------------+  |
|                                                                      |
+------------------------------+--------------------------------------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
+---------------------------------------------------------------------+
|                      Exporters & Agents                              |
|                                                                      |
|  +----------------+  +----------------+  +------------------------+  |
|  | Node Exporter  |  | Postgres       |  | Blackbox Exporter      |  |
|  | (:9100)        |  | Exporter (:9187)|  | (:9115)                |  |
|  | System metrics |  | DB metrics     |  | HTTP/SSL checks        |  |
|  +----------------+  +----------------+  +------------------------+  |
|                                                                      |
+---------------------------------------------------------------------+
                               |
                               v
+---------------------------------------------------------------------+
|                       Alertmanager (:9093)                            |
|                                                                      |
|  +------------------+  +------------------+  +--------------------+ |
|  | Alert Routing    |  | Silences         |  | Notification       | |
|  | (severity/category)|  | Management      |  | (Email/Slack/PD)   | |
|  +------------------+  +------------------+  +--------------------+ |
|                                                                      |
+------------------------------+--------------------------------------+
                               |
                               v
+---------------------------------------------------------------------+
|                         Grafana (:3000)                               |
|                                                                      |
|  +--------------------+  +--------------------+  +----------------+ |
|  | Overview Dashboard |  | Stream Monitoring  |  | Alert Status   | |
|  +--------------------+  +--------------------+  +----------------+ |
|                                                                      |
+---------------------------------------------------------------------+
```

## Data Flow Diagrams

### Metric Collection Flow

```
1. Application Metrics Flow
===========================

   Application Code
         |
         | (emit metrics via prometheus_client)
         v
   +------------------+
   | Metrics Module   |
   | (metrics.py,     |
   |  stream_*)       |
   +--------+---------+
            |
            | (HTTP scrape /metrics)
            v
   +------------------+
   | Prometheus       |----> [TSDB Storage]
   | (:9090)          |           |
   +--------+---------+           |
            |                     |
            | (evaluate rules)    |
            v                     |
   +------------------+           |
   | Alert Rules      |           |
   | (alert-rules.yml)|           |
   +--------+---------+           |
            |                     |
            | (fire alerts)       |
            v                     |
   +------------------+<----------+
   | Alertmanager     |
   +--------+---------+
            |
            | (route notifications)
            v
   +------------------+     +------------------+     +------------------+
   | Email            |     | Slack            |     | PagerDuty        |
   +------------------+     +------------------+     +------------------+


2. Health Check Flow
====================

   Kubernetes/Load Balancer
         |
         | (probe request)
         v
   +------------------+
   | Health Check     |
   | Server           |
   | (:8080/health)   |
   +--------+---------+
            |
            | (run checks)
            v
   +------------------+     +------------------+     +------------------+
   | PidFileCheck     |     | DB Connection    |     | QueueDepthCheck  |
   | (process alive)  |     | Check            |     | (backlog size)   |
   +--------+---------+     +--------+---------+     +--------+---------+
            |                       |                       |
            +----------+------------+-----------------------+
                       |
                       v
              +------------------+
              | Health Report    |
              | (status + details)|
              +--------+---------+
                       |
                       v
              +------------------+
              | HTTP Response    |
              | 200 = healthy    |
              | 503 = unhealthy  |
              +------------------+
```

## Component Relationships

### Dependency Graph

```
Memory Daemon
    |
    +-- depends on --> PostgreSQL (:5432)
    |                    |
    |                    +-- postgres_exporter (:9187)
    |
    +-- depends on --> Redis (:6379)
    |                    |
    |                    +-- redis_exporter (optional)
    |
    +-- writes to --> PID file (~/.claude/memory-daemon.pid)
    |
    +-- writes to --> Log file (~/.claude/memory-daemon.log)
    |
    +-- exposes --> Health check (:8080)
    |
    +-- emits --> Prometheus metrics (:9090 scrape)

Stream Monitor
    |
    +-- reads from --> Claude stdout (subprocess)
    |
    +-- writes to --> Redis streams
    |
    +-- emits --> Stream metrics

Prometheus
    |
    +-- scrapes --> Memory daemon metrics
    +-- scrapes --> Node exporter (:9100)
    +-- scrapes --> Postgres exporter (:9187)
    +-- scrapes --> Blackbox exporter (:9115)
    |
    +-- queries --> Alertmanager (:9093)
    |
    +-- provides --> Grafana datasource (:9090)

Alertmanager
    |
    +-- receives --> Alerts from Prometheus
    |
    +-- sends --> Notifications to:
    |            - Email (SMTP)
    |            - Slack (webhook)
    |            - PagerDuty
    |
    +-- provides --> Silences API (:9093)

Grafana
    |
    +-- queries --> Prometheus (:9090)
    |
    +-- displays --> Dashboards
    |
    +-- triggers --> Alert annotations
```

## Technology Choices and Rationale

### Why Prometheus?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Architecture** | Pull-based | Decouples metric producers from collector; easier horizontal scaling |
| **Query Language** | PromQL | Powerful for time-series operations; native alerting support |
| **Storage** | TSDB | Efficient compression; built-in retention management |
| **Ecosystem** | Large | Many exporters available; strong community |
| **Resource Usage** | Lightweight | Single binary; low memory footprint |

### Why Alertmanager?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Alert Grouping** | Essential | Prevents alert storms during incidents |
| **Routing** | Tree-based | Flexible routing by labels and severity |
| **Silences** | Useful | Temporary suppression for maintenance |
| **Inhibition** | Smart | Suppresses related lower-priority alerts |
| **Integrations** | Multiple | Email, Slack, PagerDuty, webhooks |

### Why Grafana?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Visualization** | Best-in-class | Rich panel types; flexible dashboards |
| **Data Sources** | Multi-source | Prometheus, PostgreSQL, Loki, etc. |
| **Alerting** | Integrated | Grafana-native alerting available |
| **Provisioning** | GitOps-friendly | Dashboards as code |

### Why Custom Health Check System?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Kubernetes Probes** | Native support | liveness/readiness/startup endpoints |
| **Recovery Actions** | Automated | Can auto-restart services |
| **Multiple Levels** | Tiered checks | Startup, readiness, liveness separation |
| **Prometheus Metrics** | Integrated | Health status exported as metrics |

### Why Stream Monitor?

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Claude Stream-json** | Native format | Parses Claude's event stream |
| **Stuck Detection** | Critical | Detects hung agents early |
| **Redis Integration** | Persistence | Events survive restarts |
| **Adaptive Thresholds** | Smart detection | Reduces false positives |

## Network Ports Reference

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 8080 | Health Check | HTTP | Kubernetes probes |
| 9090 | Prometheus | HTTP | Metrics collection |
| 9093 | Alertmanager | HTTP | Alert management |
| 9100 | Node Exporter | HTTP | System metrics |
| 9187 | Postgres Exporter | HTTP | Database metrics |
| 3000 | Grafana | HTTP | Dashboards |

## Configuration Files

### Core Configuration Files

| File | Purpose |
|------|---------|
| `docker/monitoring-compose.yml` | Docker Compose for stack deployment |
| `monitoring/prometheus.yml` | Prometheus scrape configuration |
| `monitoring/alert-rules.yml` | Alert condition definitions |
| `monitoring/recording-rules.yml` | Pre-computed metrics |
| `monitoring/alertmanager.yml` | Alert routing and receivers |
| `monitoring/grafana/provisioning/` | Dashboard and datasource config |

### Application Configuration

| File | Purpose |
|------|---------|
| `opc/scripts/core/health_check.py` | Health check implementation |
| `opc/scripts/core/metrics.py` | Prometheus metrics definitions |
| `opc/scripts/core/stream_monitor_metrics.py` | Stream monitoring metrics |

## Scaling Considerations

### Current Architecture

- Single Prometheus instance (sufficient for < 100k samples/sec)
- All exporters run as sidecars or separate containers
- 30-day metric retention (configurable)

### Scaling Paths

| Approach | When to Use |
|----------|-------------|
| **Remote write** | When exceeding local storage |
| **联邦** (Federation) | When multi-cluster needed |
| **Thanos/Cortex** | Long-term storage + HA |
| **Mimir** | When Grafana 10+ features needed |

## Security Considerations

| Aspect | Current State | Recommendation |
|--------|---------------|----------------|
| **Authentication** | Basic auth on Grafana | Add SSO/OIDC |
| **TLS** | None (localhost) | Enable TLS in production |
| **Network** | Localhost only | Use reverse proxy |
| **Secrets** | Environment variables | Use secrets manager |
| **Access Control** | None | Implement RBAC |
