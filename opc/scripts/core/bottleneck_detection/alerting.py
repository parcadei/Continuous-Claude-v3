"""
Alert Generation and Routing

Handles alert creation, routing, and cooldown management.
Integrates with Prometheus Alertmanager and other notification channels.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import httpx


class AlertChannel(Enum):
    """Available alert notification channels."""
    PROMETHEUS_ALERTMANAGER = "alertmanager"
    SLACK = "slack"
    WEBHOOK = "webhook"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"


@dataclass
class Alert:
    """Represents an alert to be sent."""
    fingerprint: str  # Unique identifier for deduplication
    title: str
    description: str
    severity: str  # "info", "warning", "critical"
    status: str = "firing"  # "firing", "resolved"
    starts_at: datetime = field(default_factory=datetime.utcnow)
    ends_at: datetime | None = None
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    source: str = "bottleneck-detector"
    runbook_url: str | None = None
    bottleneck_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "fingerprint": self.fingerprint,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "labels": self.labels,
            "annotations": self.annotations,
            "source": self.source,
            "runbook_url": self.runbook_url,
            "bottleneck_type": self.bottleneck_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        return cls(
            fingerprint=data["fingerprint"],
            title=data["title"],
            description=data["description"],
            severity=data["severity"],
            status=data.get("status", "firing"),
            starts_at=datetime.fromisoformat(data["starts_at"]),
            ends_at=datetime.fromisoformat(data["ends_at"]) if data.get("ends_at") else None,
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {}),
            source=data.get("source", "bottleneck-detector"),
            runbook_url=data.get("runbook_url"),
            bottleneck_type=data.get("bottleneck_type"),
        )


class AlertCooldownManager:
    """Manages alert cooldowns to prevent alert storms."""

    def __init__(self, cooldown_seconds: int = 300):
        """Initialize cooldown manager.
        
        Args:
            cooldown_seconds: Seconds to wait before re-alerting
        """
        self.cooldown_seconds = cooldown_seconds
        self._last_alerts: dict[str, datetime] = {}

    def can_alert(self, fingerprint: str) -> bool:
        """Check if an alert can be sent based on cooldown.
        
        Args:
            fingerprint: Alert fingerprint
            
        Returns:
            True if alert can be sent
        """
        last = self._last_alerts.get(fingerprint)
        if last is None:
            return True
        
        return datetime.utcnow() - last > timedelta(seconds=self.cooldown_seconds)

    def record_alert(self, fingerprint: str) -> None:
        """Record that an alert was sent.
        
        Args:
            fingerprint: Alert fingerprint
        """
        self._last_alerts[fingerprint] = datetime.utcnow()

    def get_cooldown_remaining(self, fingerprint: str) -> int:
        """Get seconds remaining in cooldown.
        
        Args:
            fingerprint: Alert fingerprint
            
        Returns:
            Seconds remaining, 0 if not in cooldown
        """
        last = self._last_alerts.get(fingerprint)
        if last is None:
            return 0
        
        elapsed = (datetime.utcnow() - last).total_seconds()
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))

    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """Clean up expired cooldown entries.
        
        Args:
            max_age_hours: Maximum age of entries to keep
            
        Returns:
            Number of entries removed
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        fingerprints_to_remove = [
            fp for fp, dt in self._last_alerts.items() if dt < cutoff
        ]
        for fp in fingerprints_to_remove:
            del self._last_alerts[fp]
        return len(fingerprints_to_remove)


class AlertGenerator:
    """Generates and routes alerts from detection results."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        alertmanager_url: str | None = None,
        webhook_url: str | None = None,
        slack_webhook_url: str | None = None,
    ):
        """Initialize alert generator.
        
        Args:
            config: Configuration dictionary
            alertmanager_url: Prometheus Alertmanager URL
            webhook_url: Generic webhook URL
            slack_webhook_url: Slack webhook URL
        """
        self.config = config or {}
        self.alertmanager_url = alertmanager_url or os.environ.get(
            "ALERTMANAGER_URL", "http://localhost:9093"
        )
        self.webhook_url = webhook_url or os.environ.get(
            "WEBHOOK_URL"
        )
        self.slack_webhook_url = slack_webhook_url or os.environ.get(
            "SLACK_WEBHOOK_URL"
        )
        
        cooldown_seconds = self.config.get("alert_cooldown_seconds", 300)
        self.cooldown_manager = AlertCooldownManager(cooldown_seconds)
        
        # Track active alerts for resolution
        self._active_alerts: dict[str, Alert] = {}

    def _generate_fingerprint(self, result) -> str:
        """Generate unique fingerprint for a detection result."""
        components = [
            result.bottleneck_type.value,
            result.metric_name,
            result.severity,
            result.affected_component,
        ]
        return "-".join(components).lower().replace("_", "-")

    def _severity_to_prometheus(self, severity: str) -> str:
        """Convert severity to Prometheus label format."""
        mapping = {
            "info": "info",
            "warning": "warning",
            "critical": "critical",
        }
        return mapping.get(severity, "warning")

    def _create_alert(self, result) -> Alert:
        """Create an Alert from a DetectionResult."""
        fingerprint = self._generate_fingerprint(result)
        
        labels = {
            "alertname": result.bottleneck_type.value,
            "severity": self._severity_to_prometheus(result.severity),
            "component": result.affected_component,
            "source": "bottleneck-detector",
            "bottleneck_type": result.bottleneck_type.value,
        }
        
        annotations = {
            "summary": f"{result.bottleneck_type.value.replace('_', ' ').title()}: {result.description}",
            "description": result.description,
            "current_value": str(result.current_value),
            "threshold_value": str(result.threshold_value),
            "percent_above": f"{result.percent_above_threshold:.1f}%",
            "detected_at": result.detected_at.isoformat(),
        }
        
        if result.recommendations:
            annotations["recommendations"] = "\n".join(
                f"- {r}" for r in result.recommendations
            )
        
        if result.runbook_url:
            annotations["runbook_url"] = result.runbook_url
            labels["runbook"] = result.runbook_url
        
        return Alert(
            fingerprint=fingerprint,
            title=f"{result.bottleneck_type.value.replace('_', ' ').title()}: {result.metric_name}",
            description=result.description,
            severity=result.severity,
            labels=labels,
            annotations=annotations,
            runbook_url=result.runbook_url,
            bottleneck_type=result.bottleneck_type.value,
        )

    def generate_alerts(self, results: list) -> list[Alert]:
        """Generate alerts from detection results.
        
        Args:
            results: List of DetectionResults
            
        Returns:
            List of Alerts to send
        """
        alerts = []
        for result in results:
            fingerprint = self._generate_fingerprint(result)
            
            # Check cooldown
            if not self.cooldown_manager.can_alert(fingerprint):
                continue
            
            alert = self._create_alert(result)
            alerts.append(alert)
            self.cooldown_manager.record_alert(fingerprint)
            
            # Track as active
            self._active_alerts[fingerprint] = alert
        
        return alerts

    async def send_to_alertmanager(self, alerts: list[Alert]) -> dict[str, Any]:
        """Send alerts to Prometheus Alertmanager.
        
        Args:
            alerts: List of alerts to send
            
        Returns:
            Response from Alertmanager
        """
        if not alerts:
            return {"status": "no alerts"}

        payload = {
            "alerts": [
                {
                    "fingerprint": a.fingerprint,
                    "status": a.status,
                    "labels": a.labels,
                    "annotations": a.annotations,
                    "startsAt": a.starts_at.isoformat(),
                    "endsAt": a.ends_at.isoformat() if a.ends_at else None,
                    "generatorURL": f"{self.alertmanager_url}/graph",
                }
                for a in alerts
            ],
            "commonLabels": {
                "source": "bottleneck-detector",
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.alertmanager_url}/api/v1/alerts",
                    json=payload,
                    timeout=30.0,
                )
                return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_to_webhook(self, alerts: list[Alert], webhook_url: str | None = None) -> dict[str, Any]:
        """Send alerts to a generic webhook.
        
        Args:
            alerts: List of alerts to send
            webhook_url: Webhook URL (uses default if not provided)
            
        Returns:
            Response from webhook
        """
        url = webhook_url or self.webhook_url
        if not url:
            return {"status": "skipped", "reason": "no webhook configured"}

        payload = {
            "alerts": [a.to_dict() for a in alerts],
            "sent_at": datetime.utcnow().isoformat(),
            "source": "bottleneck-detector",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=30.0,
                )
                return {"status": "success", "response_code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_to_slack(self, alerts: list[Alert]) -> dict[str, Any]:
        """Send alerts to Slack.
        
        Args:
            alerts: List of alerts to send
            
        Returns:
            Response from Slack
        """
        if not self.slack_webhook_url:
            return {"status": "skipped", "reason": "no slack webhook configured"}

        # Format alerts for Slack
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Bottleneck Detection Alert",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"* {len(alerts)} alert(s) detected",
                },
            },
            {"type": "divider"},
        ]

        for alert in alerts[:5]:  # Limit to 5 alerts per message
            severity_emoji = {
                "info": ":information_source:",
                "warning": ":warning:",
                "critical": ":rotating_light:",
            }.get(alert.severity, ":bell:")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{severity_emoji} *{alert.title}*\n{alert.description}",
                },
            })

            if alert.runbook_url:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"<{alert.runbook_url}|Runbook>",
                        }
                    ],
                })
            blocks.append({"type": "divider"})

        payload = {"blocks": blocks}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json=payload,
                    timeout=30.0,
                )
                return {"status": "success", "response_code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_alerts(self, results: list, channels: list[AlertChannel] | None = None) -> dict[str, Any]:
        """Send alerts to all configured channels.
        
        Args:
            results: Detection results to alert on
            channels: Specific channels to use (all if not specified)
            
        Returns:
            Dictionary with results per channel
        """
        alerts = self.generate_alerts(results)
        
        if not alerts:
            return {"status": "no alerts generated"}

        results = {}

        # Determine which channels to use
        if channels is None:
            channels = []
            if self.alertmanager_url:
                channels.append(AlertChannel.PROMETHEUS_ALERTMANAGER)
            if self.webhook_url:
                channels.append(AlertChannel.WEBHOOK)
            if self.slack_webhook_url:
                channels.append(AlertChannel.SLACK)

        # Send to each channel
        for channel in channels:
            if channel == AlertChannel.PROMETHEUS_ALERTMANAGER:
                results["alertmanager"] = await self.send_to_alertmanager(alerts)
            elif channel == AlertChannel.WEBHOOK:
                results["webhook"] = await self.send_to_webhook(alerts)
            elif channel == AlertChannel.SLACK:
                results["slack"] = await self.send_to_slack(alerts)

        return results

    def get_active_alerts(self) -> list[Alert]:
        """Get list of currently active alerts."""
        return list(self._active_alerts.values())

    def resolve_alert(self, fingerprint: str) -> bool:
        """Mark an alert as resolved.
        
        Args:
            fingerprint: Alert fingerprint
            
        Returns:
            True if alert was found and resolved
        """
        if fingerprint in self._active_alerts:
            alert = self._active_alerts[fingerprint]
            alert.status = "resolved"
            alert.ends_at = datetime.utcnow()
            del self._active_alerts[fingerprint]
            return True
        return False

    def cleanup_resolved(self) -> int:
        """Clean up resolved alerts older than 1 hour."""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        fingerprints_to_remove = [
            fp for fp, a in self._active_alerts.items()
            if a.ends_at and a.ends_at < cutoff
        ]
        for fp in fingerprints_to_remove:
            del self._active_alerts[fp]
        return len(fingerprints_to_remove)


class AlertRuleGenerator:
    """Generates Prometheus alert rules from detection configurations."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize generator."""
        self.config = config or {}

    def generate_rule(self, name: str, query: str, thresholds: dict) -> dict:
        """Generate a Prometheus alert rule.
        
        Args:
            name: Name of the alert
            query: PromQL query
            thresholds: Dictionary with warning and critical thresholds
            
        Returns:
            Alert rule dictionary
        """
        return {
            "alert": name,
            "expr": query,
            "for": f"{thresholds.get('duration', '5m')}",
            "labels": {
                "severity": thresholds.get("severity", "warning"),
                "component": thresholds.get("component", "unknown"),
            },
            "annotations": {
                "summary": thresholds.get("summary", f"{name} alert"),
                "description": thresholds.get(
                    "description",
                    f"{name} has exceeded threshold"
                ),
                "runbook_url": thresholds.get("runbook_url", ""),
            },
        }

    def generate_baseline_rules(self, component: str, metric: str, baseline_p95: float) -> list[dict]:
        """Generate alert rules based on baseline percentages.
        
        Args:
            component: Component name
            metric: Metric name
            baseline_p95: Baseline 95th percentile value
            
        Returns:
            List of alert rules
        """
        warning_threshold = baseline_p95 * 1.5  # 50% above baseline
        critical_threshold = baseline_p95 * 2.0  # 100% above baseline

        return [
            self.generate_rule(
                f"{component}_{metric}_warning",
                f"{metric} > {warning_threshold}",
                {
                    "duration": "5m",
                    "severity": "warning",
                    "component": component,
                    "summary": f"{component} {metric} above baseline",
                    "description": f"{metric} is 50% above baseline ({baseline_p95}s)",
                },
            ),
            self.generate_rule(
                f"{component}_{metric}_critical",
                f"{metric} > {critical_threshold}",
                {
                    "duration": "2m",
                    "severity": "critical",
                    "component": component,
                    "summary": f"{component} {metric} critically above baseline",
                    "description": f"{metric} is 100% above baseline ({baseline_p95}s)",
                },
            ),
        ]

    def export_rules_yaml(self, rules: list[dict]) -> str:
        """Export rules as YAML for Prometheus.
        
        Args:
            rules: List of alert rules
            
        Returns:
            YAML formatted string
        """
        yaml_output = "groups:\n  - name: bottleneck_detection\n    rules:\n"
        for rule in rules:
            yaml_output += f"    - alert: {rule['alert']}\n"
            yaml_output += f"      expr: {rule['expr']}\n"
            yaml_output += f"      for: {rule['for']}\n"
            yaml_output += "      labels:\n"
            for key, value in rule["labels"].items():
                yaml_output += f"        {key}: '{value}'\n"
            yaml_output += "      annotations:\n"
            for key, value in rule["annotations"].items():
                yaml_output += f"        {key}: '{value}'\n"
            yaml_output += "\n"
        return yaml_output
