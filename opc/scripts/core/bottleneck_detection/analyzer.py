"""
Bottleneck Detection Analyzer

Main orchestrator for the bottleneck detection system.
Coordinates detection, baseline comparison, alerting, and visualization.
"""

from __future__ import annotations
import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from .config import (
    BottleneckDetectionConfig,
    DEFAULT_CONFIG,
    get_runbook_url,
)
from .baselines import BaselineManager, BaselineType
from .detectors import (
    DatabaseBottleneckDetector,
    MemoryBottleneckDetector,
    CPUBottleneckDetector,
    NetworkBottleneckDetector,
    DetectionResult,
    BottleneckType,
)
from .alerting import AlertGenerator, AlertChannel
from .visualization import VisualizationGenerator, DashboardData


class Severity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AnalysisReport:
    """Complete analysis report."""
    id: str
    generated_at: datetime
    duration_seconds: float
    baselines_stale: list[str]
    bottlenecks_found: list[dict[str, Any]]
    alerts_generated: int
    dashboard_data: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "generated_at": self.generated_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "baselines_stale": self.baselines_stale,
            "bottlenecks_found": self.bottlenecks_found,
            "alerts_generated": self.alerts_generated,
            "dashboard_data": self.dashboard_data,
            "errors": self.errors,
        }

    def save(self, path: str | Path) -> None:
        """Save report to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


class BottleneckAnalyzer:
    """Main bottleneck detection analyzer."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        prometheus_url: str = "http://localhost:9090",
        alertmanager_url: str | None = None,
        baseline_path: str | None = None,
    ):
        """Initialize analyzer.
        
        Args:
            config: Configuration dictionary
            prometheus_url: Prometheus server URL
            alertmanager_url: Alertmanager URL for alerts
            baseline_path: Path to baseline storage
        """
        self.config = BottleneckDetectionConfig(**(config or {}))
        self.prometheus_url = prometheus_url
        self.alertmanager_url = alertmanager_url

        # Initialize components
        self.baseline_manager = BaselineManager(baseline_path)
        self.alert_generator = AlertGenerator(
            config=self.config.__dict__,
            alertmanager_url=alertmanager_url,
        )
        self.visualization = VisualizationGenerator(prometheus_url)

        # Initialize detectors
        detector_config = {
            "prometheus_url": prometheus_url,
            **self.config.__dict__,
        }
        self.detectors = {
            "database": DatabaseBottleneckDetector(detector_config),
            "memory": MemoryBottleneckDetector(detector_config),
            "cpu": CPUBottleneckDetector(detector_config),
            "network": NetworkBottleneckDetector(detector_config),
        }

    async def run_analysis(
        self,
        include_detectors: list[str] | None = None,
        alert_channels: list[AlertChannel] | None = None,
        generate_dashboard: bool = True,
    ) -> AnalysisReport:
        """Run complete bottleneck analysis.
        
        Args:
            include_detectors: Specific detectors to run (all if None)
            alert_channels: Channels to send alerts
            generate_dashboard: Whether to generate dashboard data
            
        Returns:
            AnalysisReport with results
        """
        import uuid
        start_time = datetime.utcnow()
        errors = []
        bottlenecks = []
        baselines_stale = []

        # Check baseline staleness
        for component in self.baseline_manager.list_components():
            if self.baseline_manager.is_baseline_stale(component):
                baselines_stale.append(component)

        # Run detectors
        detectors_to_run = include_detectors or list(self.detectors.keys())
        
        for detector_name in detectors_to_run:
            detector = self.detectors.get(detector_name)
            if detector is None:
                errors.append(f"Unknown detector: {detector_name}")
                continue
            
            try:
                results = await detector.detect()
                for result in results:
                    bottlenecks.append(result.to_dict())
            except Exception as e:
                errors.append(f"Detector {detector_name} error: {str(e)}")

        # Generate alerts
        alert_results = []
        for result_dict in bottlenecks:
            # Reconstruct DetectionResult for alerting
            result = DetectionResult(
                bottleneck_type=BottleneckType(result_dict["bottleneck_type"]),
                severity=result_dict["severity"],
                metric_name=result_dict["metric_name"],
                current_value=result_dict["current_value"],
                threshold_value=result_dict["threshold_value"],
                percent_above_threshold=result_dict["percent_above_threshold"],
                detected_at=datetime.fromisoformat(result_dict["detected_at"]),
                description=result_dict.get("description", ""),
                affected_component=result_dict.get("affected_component", ""),
                recommendations=result_dict.get("recommendations", []),
                runbook_url=result_dict.get("runbook_url"),
            )
            alert_results.append(result)

        alert_send_results = await self.alert_generator.send_alerts(
            alert_results, alert_channels
        )

        # Generate dashboard data
        dashboard_data = None
        if generate_dashboard:
            try:
                dashboard = await self.visualization.generate_dashboard_data(
                    detection_results=alert_results
                )
                dashboard_data = dashboard.to_dict()
            except Exception as e:
                errors.append(f"Dashboard generation error: {str(e)}")

        duration = (datetime.utcnow() - start_time).total_seconds()

        return AnalysisReport(
            id=str(uuid.uuid4())[:8],
            generated_at=start_time,
            duration_seconds=duration,
            baselines_stale=baselines_stale,
            bottlenecks_found=bottlenecks,
            alerts_generated=len(alert_results),
            dashboard_data=dashboard_data,
            errors=errors,
        )

    async def detect_specific(
        self,
        bottleneck_type: str | BottleneckType,
    ) -> list[dict[str, Any]]:
        """Detect a specific type of bottleneck.
        
        Args:
            bottleneck_type: Type of bottleneck to detect
            
        Returns:
            List of detection results
        """
        if isinstance(bottleneck_type, str):
            bottleneck_type = BottleneckType(bottleneck_type)

        detector_map = {
            BottleneckType.DB_QUERY_SLOW: "database",
            BottleneckType.DB_POOL_SATURATED: "database",
            BottleneckType.DB_LOCK_CONTENTION: "database",
            BottleneckType.DB_DEADLOCK: "database",
            BottleneckType.MEMORY_LEAK: "memory",
            BottleneckType.MEMORY_CRITICAL: "memory",
            BottleneckType.EMBEDDING_MEMORY_HIGH: "memory",
            BottleneckType.CACHE_GROWTH: "memory",
            BottleneckType.CPU_HIGH: "cpu",
            BottleneckType.CPU_SUSTAINED: "cpu",
            BottleneckType.EMBEDDING_CPU_HIGH: "cpu",
            BottleneckType.MCP_LATENCY_HIGH: "network",
            BottleneckType.REDIS_LATENCY_HIGH: "network",
            BottleneckType.EMBEDDING_API_LATENCY: "network",
        }

        detector_name = detector_map.get(bottleneck_type)
        if detector_name is None:
            return []

        detector = self.detectors.get(detector_name)
        if detector is None:
            return []

        results = await detector.detect()
        return [r.to_dict() for r in results]

    async def compare_to_baseline(
        self,
        component: str,
        metric: str,
        current_value: float,
    ) -> dict[str, Any]:
        """Compare a current value to the baseline.
        
        Args:
            component: Component name
            metric: Metric name
            current_value: Current measurement
            
        Returns:
            Comparison result
        """
        return self.baseline_manager.compare_to_baseline(
            component, metric, current_value
        )

    async def collect_baselines(
        self,
        component: str,
        samples: dict[str, list[float]],
        baseline_type: BaselineType = BaselineType.PRODUCTION,
    ) -> dict[str, Any]:
        """Collect and save baselines from samples.
        
        Args:
            component: Component name
            samples: Dictionary of metric_name -> list of sample values
            baseline_type: Type of baseline collection
            
        Returns:
            Summary of collected baselines
        """
        results = {}
        for metric_name, values in samples.items():
            try:
                baseline = self.baseline_manager.compute_baseline_from_samples(
                    component=component,
                    metric_name=metric_name,
                    samples=values,
                    baseline_type=baseline_type,
                )
                results[metric_name] = {
                    "mean": baseline.mean,
                    "p95": baseline.p95,
                    "std_dev": baseline.std_dev,
                    "sample_count": baseline.sample_count,
                }
            except Exception as e:
                results[metric_name] = {"error": str(e)}
        
        return results

    async def update_baselines(
        self,
        component: str,
        duration_hours: int = 24,
    ) -> dict[str, Any]:
        """Update baselines from production data.
        
        Args:
            component: Component to update
            duration_hours: How far back to sample
            
        Returns:
            Update summary
        """
        import aiohttp

        metrics_map = {
            "database": [
                "pg_stat_statements_p95_ms",
                "pg_pool_connections_active",
            ],
            "memory": [
                "system:memory:usage:ratio",
                "process_memory_bytes",
            ],
            "cpu": [
                "system:cpu:usage:ratio",
                "embedding_generation_duration_seconds",
            ],
            "network": [
                "mcp_tool_latency_seconds",
                "redis_operation_latency_seconds",
            ],
        }

        metrics = metrics_map.get(component, [])
        samples = {}

        async with aiohttp.ClientSession() as session:
            for metric in metrics:
                try:
                    end = datetime.utcnow()
                    start = end - timedelta(hours=duration_hours)

                    async with session.get(
                        f"{self.prometheus_url}/api/v1/query_range",
                        params={
                            "query": f"rate({metric}[1m])",
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                            "step": "5m",
                        },
                    ) as response:
                        data = await response.json()

                    values = []
                    if data.get("status") == "success":
                        for result in data.get("data", {}).get("result", []):
                            for _, value in result.get("values", []):
                                values.append(float(value))
                    samples[metric] = values

                except Exception as e:
                    samples[metric] = []

        return await self.collect_baselines(component, samples, BaselineType.WEEKLY)

    async def get_system_health(self) -> dict[str, Any]:
        """Get overall system health assessment.
        
        Returns:
            Health assessment with scores and issues
        """
        # Run quick analysis
        report = await self.run_analysis(
            include_detectors=["database", "memory", "cpu", "network"],
            alert_channels=[],  # Don't send alerts for health check
            generate_dashboard=False,
        )

        # Calculate health scores
        critical_count = sum(
            1 for b in report.bottlenecks_found
            if b.get("severity") == "critical"
        )
        warning_count = sum(
            1 for b in report.bottlenecks_found
            if b.get("severity") == "warning"
        )

        # Health score calculation
        health_score = 100
        health_score -= critical_count * 25
        health_score -= warning_count * 5
        health_score = max(0, health_score)

        # Determine status
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "degraded"
        elif health_score >= 50:
            status = "warning"
        else:
            status = "critical"

        # Check baselines
        stale_count = len(report.baselines_stale)
        baseline_status = "ok" if stale_count == 0 else f"{stale_count} stale"

        return {
            "status": status,
            "health_score": health_score,
            "critical_issues": critical_count,
            "warning_issues": warning_count,
            "baseline_status": baseline_status,
            "stale_baselines": report.baselines_stale,
            "analysis_duration_ms": int(report.duration_seconds * 1000),
            "last_analysis": report.generated_at.isoformat(),
        }

    def generate_report_summary(self, report: AnalysisReport) -> str:
        """Generate a text summary of an analysis report.
        
        Args:
            report: Analysis report
            
        Returns:
            Formatted summary string
        """
        lines = [
            f"Bottleneck Analysis Report",
            f"ID: {report.id}",
            f"Generated: {report.generated_at.isoformat()}",
            f"Duration: {report.duration_seconds:.2f}s",
            "",
            f"Baselines: {len(report.baselines_stale)} stale",
            f"Bottlenecks: {len(report.bottlenecks_found)} found",
            f"Alerts: {report.alerts_generated} generated",
            "",
        ]

        if report.baselines_stale:
            lines.append(f"Stale baselines: {', '.join(report.baselines_stale)}")

        # Group by severity
        critical = [b for b in report.bottlenecks_found if b.get("severity") == "critical"]
        warnings = [b for b in report.bottlenecks_found if b.get("severity") == "warning"]

        if critical:
            lines.append("")
            lines.append("CRITICAL ISSUES:")
            for b in critical:
                lines.append(f"  - {b['bottleneck_type']}: {b['description']}")

        if warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for b in warnings:
                lines.append(f"  - {b['bottleneck_type']}: {b['description']}")

        if report.errors:
            lines.append("")
            lines.append("ERRORS:")
            for e in report.errors:
                lines.append(f"  - {e}")

        return "\n".join(lines)


# CLI interface for running analysis
async def run_cli_analysis():
    """Run analysis from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Bottleneck Detection Analysis")
    parser.add_argument(
        "--prometheus", default="http://localhost:9090",
        help="Prometheus URL"
    )
    parser.add_argument(
        "--alertmanager", default=None,
        help="Alertmanager URL"
    )
    parser.add_argument(
        "--detector", choices=["database", "memory", "cpu", "network"],
        help="Specific detector to run"
    )
    parser.add_argument(
        "--channels", nargs="+",
        choices=["alertmanager", "webhook", "slack"],
        help="Alert channels"
    )
    parser.add_argument(
        "--output", "-o", help="Output file path"
    )
    parser.add_argument(
        "--health", action="store_true",
        help="Show system health"
    )

    args = parser.parse_args()

    # Parse alert channels
    channel_map = {
        "alertmanager": AlertChannel.PROMETHEUS_ALERTMANAGER,
        "webhook": AlertChannel.WEBHOOK,
        "slack": AlertChannel.SLACK,
    }
    channels = [channel_map[c] for c in (args.channels or [])]

    analyzer = BottleneckAnalyzer(
        prometheus_url=args.prometheus,
        alertmanager_url=args.alertmanager,
    )

    if args.health:
        health = await analyzer.get_system_health()
        print(json.dumps(health, indent=2))
    else:
        detectors = [args.detector] if args.detector else None
        report = await analyzer.run_analysis(
            include_detectors=detectors,
            alert_channels=channels,
        )

        summary = analyzer.generate_report_summary(report)
        print(summary)

        if args.output:
            report.save(args.output)
            print(f"\nReport saved to {args.output}")

        # Print dashboard preview
        if report.dashboard_data:
            print("\nDashboard Summary:")
            print(f"  Health Score: {report.dashboard_data.get('summary', {}).get('health_score', 'N/A')}")
            print(f"  Status: {report.dashboard_data.get('summary', {}).get('status', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(run_cli_analysis())
