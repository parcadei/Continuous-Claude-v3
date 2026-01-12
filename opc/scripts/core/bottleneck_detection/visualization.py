"""
Visualization Data Generation

Generates data structures for dashboards and charts.
Supports Grafana, custom dashboards, and trend visualizations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np


@dataclass
class DashboardData:
    """Complete dashboard data structure."""
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary: dict[str, Any]
    trends: dict[str, Any]
    comparisons: dict[str, Any]
    bottlenecks: list[dict[str, Any]]
    alerts_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "summary": self.summary,
            "trends": self.trends,
            "comparisons": self.comparisons,
            "bottlenecks": self.bottlenecks,
            "alerts_summary": self.alerts_summary,
        }


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
        }


class VisualizationGenerator:
    """Generates visualization data for dashboards."""

    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        grafana_url: str = "http://localhost:3001",
    ):
        """Initialize generator.
        
        Args:
            prometheus_url: Prometheus server URL
            grafana_url: Grafana server URL
        """
        self.prometheus_url = prometheus_url
        self.grafana_url = grafana_url

    async def fetch_metric_timeseries(
        self,
        query: str,
        duration_hours: int = 24,
        step: str = "1m",
    ) -> list[TimeSeriesPoint]:
        """Fetch time series data from Prometheus.
        
        Args:
            query: PromQL query
            duration_hours: How far back to fetch
            step: Query resolution step
            
        Returns:
            List of time series points
        """
        import aiohttp
        
        end = datetime.utcnow()
        start = end - timedelta(hours=duration_hours)
        
        params = {
            "query": query,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params=params,
            ) as response:
                data = await response.json()
        
        points = []
        if data.get("status") == "success":
            for result in data.get("data", {}).get("result", []):
                for timestamp, value in result.get("values", []):
                    points.append(TimeSeriesPoint(
                        timestamp=datetime.fromtimestamp(timestamp),
                        value=float(value),
                    ))
        return points

    async def generate_dashboard_data(
        self,
        duration_hours: int = 24,
        detection_results: list | None = None,
    ) -> DashboardData:
        """Generate complete dashboard data.
        
        Args:
            duration_hours: Time period for dashboard
            detection_results: Recent detection results
            
        Returns:
            DashboardData with all visualization data
        """
        end = datetime.utcnow()
        start = end - timedelta(hours=duration_hours)

        # Fetch key metrics
        metrics = await self._fetch_key_metrics(duration_hours)

        # Generate trends
        trends = self._calculate_trends(metrics)

        # Generate comparisons
        comparisons = await self._generate_comparisons(duration_hours)

        # Process bottlenecks
        bottlenecks = self._process_bottleneck_results(detection_results)

        # Generate alerts summary
        alerts_summary = self._generate_alerts_summary(bottlenecks)

        # Generate summary
        summary = self._generate_summary(metrics, trends, bottlenecks)

        return DashboardData(
            generated_at=datetime.utcnow(),
            period_start=start,
            period_end=end,
            summary=summary,
            trends=trends,
            comparisons=comparisons,
            bottlenecks=bottlenecks,
            alerts_summary=alerts_summary,
        )

    async def _fetch_key_metrics(self, duration_hours: int) -> dict[str, list[TimeSeriesPoint]]:
        """Fetch key metrics for visualization."""
        import aiohttp
        
        queries = {
            "cpu_usage": "system:cpu:usage:ratio",
            "memory_usage": "system:memory:usage:ratio",
            "db_query_latency": "pg:query_latency:percentiles",
            "db_pool_utilization": "pg:pool:utilization:ratio",
            "redis_latency": "histogram_quantile(0.95, rate(redis_operation_latency_seconds_bucket[5m]))",
            "mcp_latency": "histogram_quantile(0.95, rate(mcp_tool_latency_seconds_bucket[5m]))",
            "embedding_latency": "embedding:latency:percentiles_seconds",
        }
        
        metrics = {}
        end = datetime.utcnow()
        start = end - timedelta(hours=duration_hours)
        
        async with aiohttp.ClientSession() as session:
            for name, query in queries.items():
                params = {
                    "query": query,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "step": "5m",
                }
                try:
                    async with session.get(
                        f"{self.prometheus_url}/api/v1/query_range",
                        params=params,
                    ) as response:
                        data = await response.json()
                    
                    points = []
                    if data.get("status") == "success":
                        for result in data.get("data", {}).get("result", []):
                            for timestamp, value in result.get("values", []):
                                points.append(TimeSeriesPoint(
                                    timestamp=datetime.fromtimestamp(timestamp),
                                    value=float(value),
                                ))
                    metrics[name] = points
                except Exception:
                    metrics[name] = []
        
        return metrics

    def _calculate_trends(self, metrics: dict[str, list[TimeSeriesPoint]]) -> dict[str, Any]:
        """Calculate trend data for metrics."""
        trends = {}
        
        for name, points in metrics.items():
            if len(points) < 2:
                trends[name] = {"status": "insufficient_data"}
                continue
            
            values = [p.value for p in points]
            timestamps = [p.timestamp for p in points]
            
            # Calculate simple linear regression
            n = len(values)
            x = list(range(n))
            x_mean = n / 2
            y_mean = sum(values) / n
            
            numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            
            # Determine trend direction
            if slope > 0.01:
                trend_direction = "increasing"
            elif slope < -0.01:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"
            
            # Calculate percent change
            first_value = values[0]
            last_value = values[-1]
            pct_change = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
            
            # Current, min, max, avg
            current = values[-1] if values else 0
            minimum = min(values)
            maximum = max(values)
            average = sum(values) / len(values)
            
            trends[name] = {
                "status": "ok",
                "direction": trend_direction,
                "slope": slope,
                "percent_change": pct_change,
                "current": current,
                "min": minimum,
                "max": maximum,
                "avg": average,
                "data_points": len(values),
            }
        
        return trends

    async def _generate_comparisons(self, duration_hours: int) -> dict[str, Any]:
        """Generate comparison data (today vs last week)."""
        comparisons = {}
        
        # Calculate last week's period
        end = datetime.utcnow()
        this_start = end - timedelta(hours=duration_hours)
        week_ago = end - timedelta(hours=duration_hours * 7 + duration_hours)
        last_week_start = end - timedelta(hours=duration_hours * 7)
        
        # For now, return structure with placeholders
        # In production, fetch actual data for both periods
        metrics_to_compare = [
            "cpu_usage",
            "memory_usage",
            "db_query_latency",
            "db_pool_utilization",
            "redis_latency",
        ]
        
        for metric in metrics_to_compare:
            comparisons[metric] = {
                "current_period": {
                    "start": this_start.isoformat(),
                    "end": end.isoformat(),
                    "avg": 0,  # Would fetch actual value
                    "p95": 0,
                },
                "previous_period": {
                    "start": week_ago.isoformat(),
                    "end": last_week_start.isoformat(),
                    "avg": 0,
                    "p95": 0,
                },
                "change_percent": 0,
                "trend": "stable",
            }
        
        return comparisons

    def _process_bottleneck_results(
        self, results: list | None
    ) -> list[dict[str, Any]]:
        """Process detection results for visualization."""
        if not results:
            return []
        
        processed = []
        for result in results:
            processed.append({
                "type": result.bottleneck_type.value,
                "severity": result.severity,
                "metric": result.metric_name,
                "current_value": result.current_value,
                "threshold": result.threshold_value,
                "pct_above": result.percent_above_threshold,
                "detected_at": result.detected_at.isoformat(),
                "component": result.affected_component,
                "description": result.description,
                "runbook_url": result.runbook_url,
            })
        
        return processed

    def _generate_alerts_summary(self, bottlenecks: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary of alerts."""
        critical = sum(1 for b in bottlenecks if b["severity"] == "critical")
        warning = sum(1 for b in bottlenecks if b["severity"] == "warning")
        info = sum(1 for b in bottlenecks if b["severity"] == "info")
        
        by_type = {}
        for b in bottlenecks:
            t = b["type"]
            by_type[t] = by_type.get(t, 0) + 1
        
        by_component = {}
        for b in bottlenecks:
            c = b["component"]
            by_component[c] = by_component.get(c, 0) + 1
        
        return {
            "total": len(bottlenecks),
            "critical": critical,
            "warning": warning,
            "info": info,
            "by_type": by_type,
            "by_component": by_component,
            "status": "critical" if critical > 0 else ("warning" if warning > 0 else "healthy"),
        }

    def _generate_summary(
        self,
        metrics: dict[str, list[TimeSeriesPoint]],
        trends: dict[str, Any],
        bottlenecks: list[dict],
    ) -> dict[str, Any]:
        """Generate overall summary."""
        # Calculate overall health score
        health_score = 100
        
        # Deduct for critical issues
        critical_count = sum(1 for b in bottlenecks if b["severity"] == "critical")
        warning_count = sum(1 for b in bottlenecks if b["severity"] == "warning")
        
        health_score -= critical_count * 20
        health_score -= warning_count * 5
        health_score = max(0, health_score)
        
        # Check for concerning trends
        concerning_trends = [
            name for name, trend in trends.items()
            if trend.get("status") == "ok" and trend.get("direction") == "increasing"
        ]
        
        return {
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else ("degraded" if health_score >= 50 else "critical"),
            "critical_issues": critical_count,
            "warning_issues": warning_count,
            "concerning_trends": concerning_trends,
            "total_metrics_monitored": len(metrics),
        }

    def generate_grafana_dashboard(self) -> dict[str, Any]:
        """Generate Grafana dashboard JSON.
        
        Returns:
            Dashboard JSON for Grafana import
        """
        dashboard = {
            "annotations": {
                "list": [
                    {
                        "builtIn": 1,
                        "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                        "enable": True,
                        "hide": True,
                        "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts",
                        "type": "dashboard",
                    }
                ]
            },
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "30s",
            "schemaVersion": 39,
            "tags": ["bottleneck-detection", "continuous-claude"],
            "templating": {
                "list": [
                    {
                        "current": {"selected": True, "text": "All", "value": "$__all"},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "definition": "label_values(up, job)",
                        "hide": 0,
                        "includeAll": True,
                        "label": "Job",
                        "multi": True,
                        "name": "job",
                        "options": [],
                        "query": "label_values(up, job)",
                        "refresh": 2,
                        "regex": "",
                        "skipUrlSync": False,
                        "sort": 1,
                        "type": "query",
                    }
                ]
            },
            "time": {
                "from": "now-24h",
                "to": "now",
            },
            "timepicker": {},
            "timezone": "browser",
            "title": "Continuous-Claude-v3 Bottleneck Detection",
            "uid": "bottleneck-detection",
            "version": 1,
            "weekStart": "",
        }

        # Add panels
        panels = []
        
        # Health Score Panel
        panels.append({
            "gridPos": {"h": 4, "w": 4, "x": 0, "y": 0},
            "id": 1,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "textMode": "auto",
            },
            "pluginVersion": "10.0.0",
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": "100",
                    "refId": "A",
                }
            ],
            "title": "Health Score",
            "type": "stat",
        })

        # Critical Alerts Panel
        panels.append({
            "gridPos": {"h": 4, "w": 4, "x": 4, "y": 0},
            "id": 2,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
            },
            "pluginVersion": "10.0.0",
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": 'ALERTS{severity="critical", alertname=~"bottleneck.*"}',
                    "refId": "A",
                }
            ],
            "title": "Critical Alerts",
            "type": "stat",
        })

        # CPU Usage Panel
        panels.append({
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
            "id": 3,
            "options": {
                "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                "tooltipMode": "single",
            },
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": "system:cpu:usage:ratio * 100",
                    "refId": "A",
                }
            ],
            "title": "CPU Usage %",
            "type": "timeseries",
        })

        # Memory Usage Panel
        panels.append({
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
            "id": 4,
            "options": {
                "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                "tooltipMode": "single",
            },
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": "system:memory:usage:ratio * 100",
                    "refId": "A",
                }
            ],
            "title": "Memory Usage %",
            "type": "timeseries",
        })

        # Database Latency Panel
        panels.append({
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
            "id": 5,
            "options": {
                "legend": {"calcs": ["mean", "max", "p95"], "displayMode": "table", "placement": "bottom"},
                "tooltipMode": "single",
            },
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": "pg:query_latency:percentiles",
                    "refId": "A",
                }
            ],
            "title": "Database Query Latency",
            "type": "timeseries",
        })

        # MCP Latency Panel
        panels.append({
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
            "id": 6,
            "options": {
                "legend": {"calcs": ["mean", "max", "p95"], "displayMode": "table", "placement": "bottom"},
                "tooltipMode": "single",
            },
            "targets": [
                {
                    "datasource": {"type": "prometheus", "uid": "prometheus"},
                    "expr": "histogram_quantile(0.95, rate(mcp_tool_latency_seconds_bucket[5m])) * 1000",
                    "refId": "A",
                }
            ],
            "title": "MCP Latency (ms)",
            "type": "timeseries",
        })

        dashboard["panels"] = panels
        return dashboard

    def generate_trend_chart_data(
        self,
        current_data: list[TimeSeriesPoint],
        baseline_data: list[TimeSeriesPoint] | None = None,
    ) -> dict[str, Any]:
        """Generate data for a trend chart with baseline overlay.
        
        Args:
            current_data: Current period data
            baseline_data: Baseline data for comparison
            
        Returns:
            Chart data structure
        """
        series = []
        
        # Current data series
        if current_data:
            series.append({
                "name": "Current",
                "data": [p.to_dict() for p in current_data],
                "type": "line",
            })
        
        # Baseline series
        if baseline_data:
            series.append({
                "name": "Baseline",
                "data": [p.to_dict() for p in baseline_data],
                "type": "line",
                "dashed": True,
            })
        
        return {
            "series": series,
            "x_axis": {
                "type": "datetime",
            },
            "y_axis": {
                "title": "Value",
            },
        }

    def generate_impact_analysis(
        self,
        bottleneck: dict[str, Any],
        affected_metrics: list[str],
    ) -> dict[str, Any]:
        """Generate impact analysis for a bottleneck.
        
        Args:
            bottleneck: Bottleneck details
            affected_metrics: List of affected metric names
            
        Returns:
            Impact analysis structure
        """
        impact_score = 0
        
        # Severity impact
        severity_weights = {"critical": 100, "warning": 50, "info": 25}
        impact_score += severity_weights.get(bottleneck.get("severity", "info"), 25)
        
        # Duration impact
        duration = bottleneck.get("duration_seconds", 0)
        if duration > 300:  # > 5 minutes
            impact_score *= 1.5
        elif duration > 600:  # > 10 minutes
            impact_score *= 2.0
        
        # Affected component impact
        component_weights = {
            "database": 1.5,
            "memory": 1.3,
            "cpu": 1.2,
            "network": 1.1,
        }
        impact_score *= component_weights.get(
            bottleneck.get("component", "unknown"), 1.0
        )
        
        return {
            "bottleneck": bottleneck["type"],
            "severity": bottleneck["severity"],
            "impact_score": min(100, int(impact_score)),
            "impact_level": "high" if impact_score >= 70 else ("medium" if impact_score >= 40 else "low"),
            "affected_metrics": affected_metrics,
            "estimated_user_impact": self._estimate_user_impact(bottleneck),
            "recommended_actions": self._get_recommended_actions(bottleneck),
        }

    def _estimate_user_impact(self, bottleneck: dict[str, Any]) -> str:
        """Estimate user impact from bottleneck."""
        severity = bottleneck.get("severity", "info")
        component = bottleneck.get("component", "unknown")
        pct_above = bottleneck.get("pct_above", 0)
        
        if severity == "critical":
            return "Severe degradation - immediate action required"
        elif severity == "warning":
            if pct_above > 50:
                return "Noticeable performance degradation"
            else:
                return "Minor performance impact"
        else:
            return "Minimal user impact"

    def _get_recommended_actions(self, bottleneck: dict[str, Any]) -> list[str]:
        """Get recommended actions for bottleneck."""
        bottleneck_type = bottleneck.get("type", "")
        actions = {
            "db_query_slow": [
                "Review slow query log",
                "Check for missing indexes",
                "Optimize query execution plans",
            ],
            "db_pool_saturated": [
                "Increase connection pool size",
                "Check for connection leaks",
                "Implement connection retry logic",
            ],
            "memory_leak": [
                "Profile memory allocations",
                "Check for unbounded caches",
                "Review object retention patterns",
            ],
            "cpu_high": [
                "Profile CPU hotspots",
                "Review async task scheduling",
                "Consider horizontal scaling",
            ],
            "mcp_latency_high": [
                "Check MCP server health",
                "Review network latency",
                "Implement request caching",
            ],
        }
        return actions.get(bottleneck_type, ["Review runbook for specific guidance"])
