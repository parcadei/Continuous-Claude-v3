#!/usr/bin/env python3
"""
Alertmanager Webhook Receiver for Continuous-Claude-v3

Receives alerts from Alertmanager and:
- Logs alerts for audit trail
- Triggers custom actions for critical alerts
- Updates external status systems
- Forwards to Slack for human notification

Usage:
    docker run -p 5001:5001 \
      -v ./alert-webhook:/app \
      cc3-alert-webhook
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from flask import Flask, request, jsonify

# Configure logging
LOG_FILE = Path("/var/log/alert-webhook.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATUS_PAGE_URL = os.environ.get("STATUS_PAGE_URL")
AUDIT_LOG_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "/var/log/alerts.jsonl"))


def load_secrets() -> dict[str, str]:
    """Load secrets from file if available."""
    secrets_file = Path("/run/secrets/alert-webhook-secrets")
    if secrets_file.exists():
        return json.loads(secrets_file.read_text())
    return {}


def format_slack_message(alert: dict[str, Any]) -> dict[str, Any]:
    """Format alert for Slack notification."""
    status = alert.get("status", "firing")
    color = "#dc2626" if status == "firing" else "#16a34a"

    return {
        "attachments": [
            {
                "color": color,
                "title": f"[{alert.get('labels', {}).get('severity', 'UNKNOWN')}] {alert.get('annotations', {}).get('summary', 'Unknown Alert')}",
                "text": alert.get("annotations", {}).get("description", "No description"),
                "fields": [
                    {"title": "Alert Name", "value": alert.get("labels", {}).get("alertname", "N/A"), "short": True},
                    {"title": "Severity", "value": alert.get("labels", {}).get("severity", "N/A"), "short": True},
                    {"title": "Category", "value": alert.get("labels", {}).get("category", "N/A"), "short": True},
                    {"title": "Status", "value": status.upper(), "short": True},
                    {"title": "Instance", "value": alert.get("labels", {}).get("instance", "N/A"), "short": True},
                ],
                "footer": "Continuous-Claude-v3 Alertmanager",
                "ts": int(datetime.now().timestamp()),
                "actions": [
                    {
                        "type": "button",
                        "text": "View Dashboard",
                        "url": "https://grafana.continuous-claude.local/d/continuous-claude-overview",
                    },
                    {
                        "type": "button",
                        "text": "Silence Alert",
                        "url": f"http://localhost:9093/silences/new?matchers=alertname%3D{alert.get('labels', {}).get('alertname', '')}",
                    },
                ],
            }
        ]
    }


def send_to_slack(alert: dict[str, Any]) -> bool:
    """Send alert notification to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured")
        return False

    try:
        message = format_slack_message(alert)
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"Alert sent to Slack: {alert.get('labels', {}).get('alertname')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send to Slack: {e}")
        return False


def send_to_discord(alert: dict[str, Any]) -> bool:
    """Send alert notification to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    try:
        message = {
            "embeds": [
                {
                    "title": f"[{alert.get('labels', {}).get('severity', 'UNKNOWN')}] {alert.get('annotations', {}).get('summary', 'Unknown Alert')}",
                    "description": alert.get('annotations', {}).get('description', 'No description'),
                    "color": 0xDC2626 if alert.get('status') == 'firing' else 0x16A34A,
                    "fields": [
                        {"name": "Alert", "value": alert.get('labels', {}).get('alertname', 'N/A')},
                        {"name": "Category", "value": alert.get('labels', {}).get('category', 'N/A')},
                    ],
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send to Discord: {e}")
        return False


def update_status_page(alert: dict[str, Any]) -> bool:
    """Update status page with alert information."""
    if not STATUS_PAGE_URL:
        return False

    try:
        # Status Page API integration would go here
        # This is a placeholder for the actual API call
        logger.info(f"Would update status page for: {alert.get('labels', {}).get('alertname')}")
        return True
    except Exception as e:
        logger.error(f"Failed to update status page: {e}")
        return False


def audit_log(alert: dict[str, Any]) -> None:
    """Log alert to audit trail."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_PATH, "a") as f:
            record = {
                "timestamp": datetime.now().isoformat(),
                "alert": alert,
            }
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"Failed to audit log: {e}")


def process_critical_alert(alert: dict[str, Any]) -> None:
    """Execute custom actions for critical alerts."""
    severity = alert.get("labels", {}).get("severity", "")
    alertname = alert.get("labels", {}).get("alertname", "")

    # P0 alerts trigger additional actions
    if severity == "P0":
        logger.critical(f"P0 ALERT: {alertname} - executing critical response")

        # Placeholder for P0-specific actions:
        # - Page on-call engineer
        # - Create incident ticket
        # - Disable automated scaling
        # - Notify Slack channel

        # Example: Send to incident channel
        if SLACK_WEBHOOK_URL:
            try:
                requests.post(
                    SLACK_WEBHOOK_URL,
                    json={
                        "channel": "#critical-alerts",
                        "text": f":rotating_light: *CRITICAL P0 ALERT* :rotating_light:\n{alertname}\n{alert.get('annotations', {}).get('summary')}",
                    },
                    timeout=10,
                )
            except Exception as e:
                logger.error(f"Failed to send P0 notification: {e}")


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Alertmanager webhooks."""
    data = request.get_json()

    if not data:
        logger.warning("Received empty webhook")
        return jsonify({"status": "error", "message": "empty payload"}), 400

    logger.info(f"Received webhook with {len(data.get('alerts', []))} alerts")

    # Process each alert
    for alert in data.get("alerts", []):
        alertname = alert.get("labels", {}).get("alertname", "unknown")
        status = alert.get("status", "firing")
        severity = alert.get("labels", {}).get("severity", "P3")

        logger.info(f"Processing alert: {alertname} [{status}] [{severity}]")

        # Audit log every alert
        audit_log(alert)

        # Send to Slack
        send_to_slack(alert)

        # Send to Discord
        send_to_discord(alert)

        # Update status page
        update_status_page(alert)

        # Execute critical alert actions
        if status == "firing" and severity == "P0":
            process_critical_alert(alert)

    return jsonify({"status": "success", "message": "alerts processed"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "alert-webhook"}), 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check endpoint."""
    # Check if external connections are configured and working
    checks = {
        "slack_configured": bool(SLACK_WEBHOOK_URL),
        "discord_configured": bool(DISCORD_WEBHOOK_URL),
        "statuspage_configured": bool(STATUS_PAGE_URL),
    }

    all_ready = all(checks.values())

    return jsonify({"status": "ready" if all_ready else "degraded", "checks": checks}), 200 if all_ready else 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    logger.info(f"Starting Alertmanager Webhook Receiver on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
