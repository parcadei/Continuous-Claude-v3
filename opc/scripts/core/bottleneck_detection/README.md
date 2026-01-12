# Bottleneck Detection System for Continuous-Claude-v3

A comprehensive performance monitoring system that detects bottlenecks across database, memory, CPU, and network components.

## Overview

This system provides:
- **Baseline Management**: Collect and compare against performance baselines
- **Detection Algorithms**: Statistical thresholds, trend analysis, anomaly detection
- **Specific Detectors**: Database, memory, CPU, and network bottleneck detection
- **Alert Integration**: Prometheus Alertmanager, webhooks, Slack
- **Visualization**: Dashboard data for Grafana and custom interfaces

## Components

### 1. `analyzer.py` - Main Orchestrator
The `BottleneckAnalyzer` class coordinates all detection:
```python
from scripts.core.bottleneck_detection import BottleneckAnalyzer

analyzer = BottleneckAnalyzer(
    prometheus_url="http://localhost:9090",
    alertmanager_url="http://localhost:9093",
)

report = await analyzer.run_analysis()
```

### 2. `baselines.py` - Baseline Management
Collect and compare against performance baselines:
```python
from scripts.core.bottleneck_detection import BaselineManager

manager = BaselineManager()
baseline = manager.compute_baseline_from_samples(
    component="database",
    metric_name="pg_query_latency_ms",
    samples=[10.5, 12.3, 11.1, ...],
)
comparison = manager.compare_to_baseline("database", "pg_query_latency_ms", 15.0)
```

### 3. `detectors.py` - Bottleneck Detectors
Specialized detectors for each component:
- `DatabaseBottleneckDetector` - Slow queries, pool saturation, deadlocks
- `MemoryBottleneckDetector` - Memory leaks, cache growth
- `CPUBottleneckDetector` - High CPU, sustained usage
- `NetworkBottleneckDetector` - MCP latency, Redis RTT

### 4. `alerting.py` - Alert Generation
Route alerts to multiple channels:
```python
from scripts.core.bottleneck_detection import AlertGenerator, AlertChannel

alert_gen = AlertGenerator(
    alertmanager_url="http://localhost:9093",
    slack_webhook_url="https://hooks.slack.com/...",
)

results = await alert_gen.send_alerts(results, channels=[
    AlertChannel.PROMETHEUS_ALERTMANAGER,
    AlertChannel.SLACK,
])
```

### 5. `visualization.py` - Dashboard Data
Generate visualization data for dashboards:
```python
from scripts.core.bottleneck_detection import VisualizationGenerator

viz = VisualizationGenerator()
dashboard = await viz.generate_dashboard_data()
grafana_dashboard = viz.generate_grafana_dashboard()
```

## Usage

### Command Line

```bash
# Health check
python -m scripts.core.bottleneck_detection.cli --health

# Run specific detector
python -m scripts.core.bottleneck_detection.cli --detector database

# Full analysis with output
python -m scripts.core.bottleneck_detection.cli -o report.json

# Update baselines
python -m scripts.core.bottleneck_detection.cli --update-baselines database

# Compare value to baseline
python -m scripts.core.bottleneck_detection.cli --compare database pg_query_latency_ms 15.0
```

### Python API

```python
import asyncio
from scripts.core.bottleneck_detection import BottleneckAnalyzer, AlertChannel

async def main():
    analyzer = BottleneckAnalyzer(
        prometheus_url="http://localhost:9090",
        alertmanager_url="http://localhost:9093",
    )
    
    # Run full analysis
    report = await analyzer.run_analysis(
        alert_channels=[AlertChannel.PROMETHEUS_ALERTMANAGER],
    )
    
    print(f"Found {len(report.bottlenecks_found)} bottlenecks")
    
    # Get system health
    health = await analyzer.get_system_health()
    print(f"Health score: {health['health_score']}")

asyncio.run(main())
```

## Configuration

### Threshold Configuration

Edit `config.py` to adjust thresholds:

```python
@dataclass
class BottleneckDetectionConfig:
    # Database thresholds
    db_query_latency_warning: float = 2.0  # seconds
    db_query_latency_critical: float = 5.0  # seconds
    db_pool_warning_pct: float = 0.70
    db_pool_critical_pct: float = 0.90
    
    # Memory thresholds
    memory_warning_pct: float = 0.80
    memory_critical_pct: float = 0.95
    
    # CPU thresholds
    cpu_warning_pct: float = 0.80
    cpu_critical_pct: float = 0.95
    cpu_sustained_duration: int = 300  # seconds
    
    # Network thresholds
    mcp_latency_warning_ms: float = 500.0
    mcp_latency_critical_ms: float = 2000.0
```

### Environment Variables

```bash
PROMETHEUS_URL=http://localhost:9090
ALERTMANAGER_URL=http://localhost:9093
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
WEBHOOK_URL=https://example.com/webhook
BASELINE_STORAGE_PATH=/path/to/baselines
```

## Detection Methods

### 1. Statistical Thresholds
```yaml
# Example: p95 latency > baseline + 50%
pg_stat_statements_p95_ms > baseline_p95 * 1.5
```

### 2. Trend Analysis
Detects degradation over time using linear regression:
- Monitors slope of metric over time window
- Flags metrics with consistent upward trend

### 3. Anomaly Detection
Statistical outlier detection:
- Z-score based (values > 2.5 std devs from mean)
- MAD-based for robustness

### 4. Correlation Analysis
Detects correlated resource usage:
- CPU + memory together
- Network latency + DB latency

## Bottleneck Types

### Database
- `DB_QUERY_SLOW`: Query latency above threshold
- `DB_POOL_SATURATED`: Connection pool near capacity
- `DB_LOCK_CONTENTION`: Queries waiting on locks
- `DB_DEADLOCK`: Deadlocks detected

### Memory
- `MEMORY_LEAK`: Consistent memory growth trend
- `MEMORY_CRITICAL`: Memory usage above 95%
- `EMBEDDING_MEMORY_HIGH`: Embedding model memory high
- `CACHE_GROWTH`: Cache growing with low hit rate

### CPU
- `CPU_HIGH`: CPU usage above 80%
- `CPU_SUSTAINED`: High CPU for extended period
- `EMBEDDING_CPU_HIGH`: CPU during embedding generation

### Network
- `MCP_LATENCY_HIGH`: MCP client latency high
- `REDIS_LATENCY_HIGH`: Redis operation latency high
- `EMBEDDING_API_LATENCY`: External embedding API slow

## Alert Integration

### Prometheus Alertmanager

Alerts are formatted for Prometheus:
```yaml
groups:
  - name: bottleneck_detection
    rules:
      - alert: DatabaseQuerySlow
        expr: pg_stat_statements_p95_ms > 3.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database query latency high"
```

### Slack Notifications
Alert format includes severity emoji and runbook links.

### Webhooks
Generic webhook payload:
```json
{
  "alerts": [...],
  "sent_at": "2024-01-01T00:00:00Z",
  "source": "bottleneck-detector"
}
```

## Visualization

### Grafana Dashboard
Generate dashboard JSON:
```python
grafana_dashboard = viz.generate_grafana_dashboard()
# Import into Grafana
```

### Trend Charts
Generate trend data with baseline overlay:
```python
chart_data = viz.generate_trend_chart_data(
    current_data=current_series,
    baseline_data=baseline_series,
)
```

## Files

```
scripts/core/bottleneck_detection/
├── __init__.py           # Package exports
├── analyzer.py           # Main BottleneckAnalyzer class
├── baselines.py          # Baseline management
├── config.py             # Threshold configuration
├── detectors.py          # Detection algorithms
├── alerting.py           # Alert generation
├── visualization.py      # Dashboard generation
├── cli.py               # Command-line interface
└── README.md            # This file
```

## Runbooks

Each bottleneck type has an associated runbook:
- Database: [docs/runbooks.md#query-latency](docs/runbooks.md#query-latency)
- Memory: [docs/runbooks.md#memory-leak](docs/runbooks.md#memory-leak)
- CPU: [docs/runbooks.md#cpu-usage](docs/runbooks.md#cpu-usage)
- Network: [docs/runbooks.md#mcp-latency](docs/runbooks.md#mcp-latency)

## Integration with Existing Monitoring

The system integrates with the existing Prometheus/Grafana setup:
- Uses same Prometheus URL
- Generates alerts compatible with Alertmanager
- Can import Grafana dashboards

See `/Users/grantray/Github/Continuous-Claude-v3/monitoring/` for existing configuration.
