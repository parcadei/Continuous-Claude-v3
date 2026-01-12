#!/usr/bin/env python3
"""
Bottleneck Detection CLI

Command-line interface for running bottleneck detection analysis.

Usage:
    python -m scripts.core.bottleneck_detection.cli --health
    python -m scripts.core.bottleneck_detection.cli --detector database
    python -m scripts.core.bottleneck_detection.cli --output report.json
"""

from __future__ import annotations
import argparse
import asyncio
import json

from .analyzer import BottleneckAnalyzer, AlertChannel


async def main():
    parser = argparse.ArgumentParser(
        description="Continuous-Claude-v3 Bottleneck Detection Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--prometheus", default="http://localhost:9090",
        help="Prometheus URL (default: http://localhost:9090)"
    )
    parser.add_argument(
        "--alertmanager", default=None,
        help="Alertmanager URL for alerts"
    )
    parser.add_argument(
        "--webhook", default=None,
        help="Generic webhook URL for alerts"
    )
    parser.add_argument(
        "--slack-webhook", default=None,
        help="Slack webhook URL for alerts"
    )
    parser.add_argument(
        "--detector", choices=["database", "memory", "cpu", "network"],
        help="Specific detector to run (default: all)"
    )
    parser.add_argument(
        "--channels", nargs="+",
        choices=["alertmanager", "webhook", "slack"],
        help="Alert channels to send to"
    )
    parser.add_argument(
        "--output", "-o", help="Output file path for JSON report"
    )
    parser.add_argument(
        "--health", action="store_true",
        help="Show system health summary"
    )
    parser.add_argument(
        "--baseline-status", action="store_true",
        help="Show baseline status"
    )
    parser.add_argument(
        "--update-baselines", choices=["database", "memory", "cpu", "network"],
        help="Update baselines for a component"
    )
    parser.add_argument(
        "--compare", nargs=3, metavar=("COMPONENT", "METRIC", "VALUE"),
        help="Compare value to baseline: COMPONENT METRIC VALUE"
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Generate dashboard JSON"
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

    # Health check
    if args.health:
        health = await analyzer.get_system_health()
        print(json.dumps(health, indent=2))
        return

    # Baseline status
    if args.baseline_status:
        components = analyzer.baseline_manager.list_components()
        print("Components with baselines:")
        for comp in components:
            summary = analyzer.baseline_manager.get_baseline_summary(comp)
            if summary:
                print(f"  {comp}: {summary['metric_count']} metrics, ", end="")
                print(f"stale: {summary['is_stale']}")
        return

    # Update baselines
    if args.update_baselines:
        result = await analyzer.update_baselines(args.update_baselines)
        print(f"Baseline update for {args.update_baselines}:")
        for metric, data in result.items():
            print(f"  {metric}: {data}")
        return

    # Compare to baseline
    if args.compare:
        component, metric, value = args.compare
        result = await analyzer.compare_to_baseline(
            component, metric, float(value)
        )
        print(json.dumps(result, indent=2))
        return

    # Generate dashboard
    if args.dashboard:
        dashboard = await analyzer.visualization.generate_dashboard_data()
        print(json.dumps(dashboard.to_dict(), indent=2))
        return

    # Full analysis
    detectors = [args.detector] if args.detector else None
    report = await analyzer.run_analysis(
        include_detectors=detectors,
        alert_channels=channels,
    )

    # Print summary
    summary = analyzer.generate_report_summary(report)
    print(summary)

    if report.errors:
        print("\nErrors encountered:")
        for error in report.errors:
            print(f"  - {error}")

    # Save report
    if args.output:
        report.save(args.output)
        print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
