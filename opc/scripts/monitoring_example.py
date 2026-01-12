#!/usr/bin/env python3
"""
Example: Using the new webhook and tool failure monitoring metrics.

This script demonstrates how to record MCP tool failures and webhook delivery
for the Prometheus monitoring stack.
"""

import time
from opc.scripts.core.metrics import mcp, webhook


def example_tool_failure_tracker():
    """Example: Track MCP tool failures."""

    # Simulate a successful tool call
    mcp.record_tool_call(
        server_name="github",
        tool_name="git_search",
        duration=0.15,
        success=True,
        retries=0,
    )

    # Simulate a failed tool call
    mcp.record_tool_call(
        server_name="github",
        tool_name="git_search",
        duration=2.5,
        success=False,
        retries=2,
    )

    # Update connection count
    mcp.update_connection_count(3)

    print("✓ MCP tool calls recorded")
    print(f"  - Success: github/git_search")
    print(f"  - Failed: github/git_search (2 retries)")


def example_webhook_tracker():
    """Example: Track webhook delivery."""

    # Successful webhook delivery
    webhook.record_webhook_delivery(
        webhook_url="https://hooks.slack.com/services/xxx",
        success=True,
        duration=0.25,
    )

    # Failed webhook delivery
    webhook.record_webhook_delivery(
        webhook_url="https://hooks.slack.com/services/xxx",
        success=False,
        duration=5.5,
    )

    # Track external API call
    webhook.record_external_api_request(
        api_name="perplexity",
        endpoint="/api/search",
        success=True,
        status_code=200,
        duration=1.2,
    )

    # Failed external API call
    webhook.record_external_api_request(
        api_name="perplexity",
        endpoint="/api/search",
        success=False,
        status_code=500,
        duration=3.4,
    )

    print("✓ Webhook and API calls recorded")
    print("  - Slack webhook: 1 success, 1 failed")
    print("  - Perplexity API: 1 success, 1 failed")


def example_alert_rules():
    """Show the new alert rules that were added."""

    print("\n📋 New Alert Rules Added:")
    print("-" * 50)

    alerts = [
        ("MCPToolCallFailing", "P1", "MCP tool call failed"),
        ("MCPToolLatencyHigh", "P1", "MCP tool latency p95 > 10s"),
        ("MCPToolRetriesHigh", "P2", "MCP tool retries > 5"),
        ("MCPCacheMissRateHigh", "P2", "MCP cache miss rate > 50%"),
        ("AllMCPServersDisconnected", "P0", "All MCP servers disconnected"),
        ("MCPConnectionFlapping", "P2", "MCP connection flapping"),
        ("AlertWebhookDeliveryFailed", "P1", "Alert webhook delivery failed"),
        ("WebhookResponseTimeHigh", "P2", "Webhook response time p95 > 5s"),
        ("ExternalAPIFailureRateHigh", "P2", "External API error rate > 10%"),
    ]

    for name, severity, description in alerts:
        print(f"  [{severity}] {name}")
        print(f"         {description}")


if __name__ == "__main__":
    print("=" * 60)
    print("Webhook & Tool Failure Monitoring Example")
    print("=" * 60)

    example_tool_failure_tracker()
    example_webhook_tracker()
    example_alert_rules()

    print("\n" + "=" * 60)
    print("To view these metrics:")
    print("  1. Start the metrics server: python -m scripts.core.metrics_server")
    print("  2. Scrape: curl http://localhost:9090/metrics")
    print("  3. Search for: mcp_tool_calls_total, alert_webhook_delivery_total")
    print("=" * 60)
