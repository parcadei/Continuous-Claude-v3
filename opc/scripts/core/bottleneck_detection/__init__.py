"""
Bottleneck Detection System for Continuous-Claude-v3

A comprehensive performance monitoring system that detects bottlenecks across
database, memory, CPU, and network components.

Components:
- analyzer: Core detection orchestration
- baselines: Performance baseline management
- detectors: Specific bottleneck detection algorithms
- alerting: Alert generation and routing
- visualization: Dashboard data generation
"""

from .analyzer import BottleneckAnalyzer, DetectionResult, BottleneckType, Severity
from .baselines import BaselineManager, Baseline, MetricBaseline
from .detectors import (
    DatabaseBottleneckDetector,
    MemoryBottleneckDetector,
    CPUBottleneckDetector,
    NetworkBottleneckDetector,
)
from .alerting import AlertGenerator, Alert, AlertChannel
from .visualization import VisualizationGenerator, DashboardData

__version__ = "1.0.0"
__all__ = [
    "BottleneckAnalyzer",
    "DetectionResult",
    "BottleneckType",
    "Severity",
    "BaselineManager",
    "Baseline",
    "MetricBaseline",
    "DatabaseBottleneckDetector",
    "MemoryBottleneckDetector",
    "CPUBottleneckDetector",
    "NetworkBottleneckDetector",
    "AlertGenerator",
    "Alert",
    "AlertChannel",
    "VisualizationGenerator",
    "DashboardData",
]
