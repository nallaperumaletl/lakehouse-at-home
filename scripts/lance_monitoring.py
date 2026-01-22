"""
Lance Monitoring and Observability
==================================
Monitoring utilities for LanceDB in production environments.

Features:
- Prometheus-compatible metrics export
- Health check endpoints
- Performance dashboards data
- Alerting thresholds
- Log aggregation

Usage:
    from lance_monitoring import LanceMonitor

    monitor = LanceMonitor("/path/to/lance")

    # Get Prometheus metrics
    metrics = monitor.get_prometheus_metrics()

    # Health check (for load balancer)
    health = monitor.health_check()

    # Dashboard data
    dashboard = monitor.get_dashboard_data()
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

import lancedb

logger = logging.getLogger("lance_monitoring")


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    metric_type: str = "gauge"  # gauge, counter, histogram


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric: str
    operator: str  # gt, lt, eq
    threshold: float
    duration_seconds: int = 60
    severity: str = "warning"  # info, warning, critical


@dataclass
class Alert:
    """Active alert."""
    rule: AlertRule
    value: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None


class MetricsCollector:
    """Collects and stores metrics time series."""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self._metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, name: str, value: float, labels: Dict[str, str] = None, metric_type: str = "gauge"):
        """Record a metric value."""
        point = MetricPoint(
            name=name,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(),
            metric_type=metric_type,
        )
        with self._lock:
            self._metrics[name].append(point)
            self._cleanup(name)

    def _cleanup(self, name: str):
        """Remove old metrics beyond retention period."""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        self._metrics[name] = [p for p in self._metrics[name] if p.timestamp > cutoff]

    def get_latest(self, name: str) -> Optional[MetricPoint]:
        """Get the latest value for a metric."""
        with self._lock:
            points = self._metrics.get(name, [])
            return points[-1] if points else None

    def get_series(self, name: str, duration_minutes: int = 60) -> List[MetricPoint]:
        """Get time series for a metric."""
        cutoff = datetime.now() - timedelta(minutes=duration_minutes)
        with self._lock:
            return [p for p in self._metrics.get(name, []) if p.timestamp > cutoff]

    def get_all_latest(self) -> Dict[str, MetricPoint]:
        """Get latest values for all metrics."""
        with self._lock:
            return {name: points[-1] for name, points in self._metrics.items() if points}


class LanceMonitor:
    """
    Comprehensive monitoring for LanceDB.

    Collects metrics on:
    - Table sizes and row counts
    - Query latencies
    - Write throughput
    - Index health
    - System resources
    """

    def __init__(
        self,
        lance_path: str,
        collect_interval_seconds: int = 60,
        enable_background_collection: bool = False,
    ):
        """
        Initialize the monitor.

        Args:
            lance_path: Path to LanceDB storage
            collect_interval_seconds: Interval for background metric collection
            enable_background_collection: Enable automatic background collection
        """
        self.lance_path = lance_path
        self.collect_interval = collect_interval_seconds

        self._db = None
        self._collector = MetricsCollector()
        self._alerts: List[Alert] = []
        self._alert_rules: List[AlertRule] = []

        # Background collection
        self._stop_event = threading.Event()
        self._collection_thread = None

        if enable_background_collection:
            self.start_background_collection()

        # Default alert rules
        self._setup_default_alerts()

    @property
    def db(self) -> lancedb.DBConnection:
        """Get LanceDB connection."""
        if self._db is None:
            self._db = lancedb.connect(self.lance_path)
        return self._db

    def _setup_default_alerts(self):
        """Setup default alerting rules."""
        self._alert_rules = [
            AlertRule(
                name="high_query_latency",
                metric="lance_query_latency_ms",
                operator="gt",
                threshold=1000,  # 1 second
                duration_seconds=300,
                severity="warning",
            ),
            AlertRule(
                name="write_failures",
                metric="lance_write_failures_total",
                operator="gt",
                threshold=10,
                duration_seconds=60,
                severity="critical",
            ),
            AlertRule(
                name="table_too_large",
                metric="lance_table_size_bytes",
                operator="gt",
                threshold=10 * 1024 * 1024 * 1024,  # 10 GB
                duration_seconds=0,
                severity="warning",
            ),
        ]

    def collect_metrics(self):
        """Collect all metrics from LanceDB."""
        try:
            tables = self.db.table_names()

            # Overall metrics
            self._collector.record("lance_tables_total", len(tables))

            total_rows = 0
            total_size = 0

            for table_name in tables:
                try:
                    table = self.db.open_table(table_name)
                    row_count = table.count_rows()
                    total_rows += row_count

                    # Table-specific metrics
                    labels = {"table": table_name}
                    self._collector.record("lance_table_rows", row_count, labels)

                    # Calculate table size
                    table_path = os.path.join(self.lance_path, f"{table_name}.lance")
                    if os.path.exists(table_path):
                        size = sum(
                            os.path.getsize(os.path.join(root, f))
                            for root, _, files in os.walk(table_path)
                            for f in files
                        )
                        total_size += size
                        self._collector.record("lance_table_size_bytes", size, labels)

                        # Check for index
                        index_path = os.path.join(table_path, "_indices")
                        has_index = 1 if os.path.exists(index_path) and os.listdir(index_path) else 0
                        self._collector.record("lance_table_has_index", has_index, labels)

                except Exception as e:
                    logger.warning(f"Error collecting metrics for {table_name}: {e}")

            # Aggregate metrics
            self._collector.record("lance_total_rows", total_rows)
            self._collector.record("lance_total_size_bytes", total_size)

            # Check alerts
            self._check_alerts()

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self._collector.record("lance_collection_errors_total", 1, metric_type="counter")

    def record_query(self, table_name: str, latency_ms: float, result_count: int):
        """Record a query execution."""
        labels = {"table": table_name}
        self._collector.record("lance_query_latency_ms", latency_ms, labels)
        self._collector.record("lance_query_results", result_count, labels)
        self._collector.record("lance_queries_total", 1, labels, metric_type="counter")

    def record_write(self, table_name: str, rows: int, latency_ms: float, success: bool):
        """Record a write operation."""
        labels = {"table": table_name}
        if success:
            self._collector.record("lance_write_latency_ms", latency_ms, labels)
            self._collector.record("lance_rows_written_total", rows, labels, metric_type="counter")
            self._collector.record("lance_writes_total", 1, labels, metric_type="counter")
        else:
            self._collector.record("lance_write_failures_total", 1, labels, metric_type="counter")

    def _check_alerts(self):
        """Check alert rules against current metrics."""
        now = datetime.now()

        for rule in self._alert_rules:
            latest = self._collector.get_latest(rule.metric)
            if not latest:
                continue

            triggered = False
            if rule.operator == "gt" and latest.value > rule.threshold:
                triggered = True
            elif rule.operator == "lt" and latest.value < rule.threshold:
                triggered = True
            elif rule.operator == "eq" and latest.value == rule.threshold:
                triggered = True

            # Find existing alert
            existing = next((a for a in self._alerts if a.rule.name == rule.name and not a.resolved_at), None)

            if triggered:
                if not existing:
                    alert = Alert(rule=rule, value=latest.value, triggered_at=now)
                    self._alerts.append(alert)
                    logger.warning(f"Alert triggered: {rule.name} ({latest.value} {rule.operator} {rule.threshold})")
            else:
                if existing:
                    existing.resolved_at = now
                    logger.info(f"Alert resolved: {rule.name}")

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active alerts."""
        return [
            {
                "name": a.rule.name,
                "severity": a.rule.severity,
                "metric": a.rule.metric,
                "value": a.value,
                "threshold": a.rule.threshold,
                "triggered_at": a.triggered_at.isoformat(),
            }
            for a in self._alerts
            if not a.resolved_at
        ]

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check suitable for load balancer probes.

        Returns:
            Health status with HTTP-compatible status code
        """
        health = {
            "status": "healthy",
            "status_code": 200,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        # Check 1: Database connectivity
        try:
            tables = self.db.table_names()
            health["checks"]["database"] = {"status": "pass", "tables": len(tables)}
        except Exception as e:
            health["checks"]["database"] = {"status": "fail", "error": str(e)}
            health["status"] = "unhealthy"
            health["status_code"] = 503

        # Check 2: Write capability
        try:
            test_file = os.path.join(self.lance_path, ".health_probe")
            with open(test_file, 'w') as f:
                f.write(datetime.now().isoformat())
            os.remove(test_file)
            health["checks"]["writable"] = {"status": "pass"}
        except Exception as e:
            health["checks"]["writable"] = {"status": "fail", "error": str(e)}
            health["status"] = "unhealthy"
            health["status_code"] = 503

        # Check 3: Active alerts
        active_alerts = self.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a["severity"] == "critical"]
        health["checks"]["alerts"] = {
            "status": "fail" if critical_alerts else "pass",
            "active": len(active_alerts),
            "critical": len(critical_alerts),
        }
        if critical_alerts:
            health["status"] = "degraded"
            health["status_code"] = 503

        return health

    def get_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        lines.append("# HELP lance_tables_total Total number of Lance tables")
        lines.append("# TYPE lance_tables_total gauge")

        all_metrics = self._collector.get_all_latest()

        for name, point in all_metrics.items():
            # Format labels
            if point.labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in point.labels.items())
                lines.append(f"{name}{{{label_str}}} {point.value}")
            else:
                lines.append(f"{name} {point.value}")

        return "\n".join(lines)

    def get_dashboard_data(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        Get data formatted for dashboard visualization.

        Args:
            duration_minutes: Time range for time series data

        Returns:
            Dashboard-ready data structure
        """
        # Collect fresh metrics
        self.collect_metrics()

        all_metrics = self._collector.get_all_latest()

        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tables": all_metrics.get("lance_tables_total", MetricPoint("", 0, {}, datetime.now())).value,
                "total_rows": all_metrics.get("lance_total_rows", MetricPoint("", 0, {}, datetime.now())).value,
                "total_size_mb": round(all_metrics.get("lance_total_size_bytes", MetricPoint("", 0, {}, datetime.now())).value / (1024 * 1024), 2),
            },
            "tables": [],
            "alerts": self.get_active_alerts(),
            "time_series": {},
        }

        # Per-table data
        for name, point in all_metrics.items():
            if name == "lance_table_rows" and point.labels.get("table"):
                table_name = point.labels["table"]
                size_metric = next(
                    (m for n, m in all_metrics.items() if n == "lance_table_size_bytes" and m.labels.get("table") == table_name),
                    None
                )
                index_metric = next(
                    (m for n, m in all_metrics.items() if n == "lance_table_has_index" and m.labels.get("table") == table_name),
                    None
                )
                dashboard["tables"].append({
                    "name": table_name,
                    "rows": int(point.value),
                    "size_mb": round(size_metric.value / (1024 * 1024), 2) if size_metric else 0,
                    "has_index": bool(index_metric.value) if index_metric else False,
                })

        # Time series for key metrics
        for metric_name in ["lance_query_latency_ms", "lance_total_rows", "lance_total_size_bytes"]:
            series = self._collector.get_series(metric_name, duration_minutes)
            if series:
                dashboard["time_series"][metric_name] = [
                    {"timestamp": p.timestamp.isoformat(), "value": p.value}
                    for p in series
                ]

        return dashboard

    def start_background_collection(self):
        """Start background metric collection."""
        if self._collection_thread and self._collection_thread.is_alive():
            return

        self._stop_event.clear()

        def collect_loop():
            while not self._stop_event.is_set():
                self.collect_metrics()
                self._stop_event.wait(self.collect_interval)

        self._collection_thread = threading.Thread(target=collect_loop, daemon=True)
        self._collection_thread.start()
        logger.info(f"Started background collection every {self.collect_interval}s")

    def stop_background_collection(self):
        """Stop background metric collection."""
        self._stop_event.set()
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        logger.info("Stopped background collection")


# Simple HTTP server for metrics endpoint
def start_metrics_server(monitor: LanceMonitor, port: int = 9090):
    """
    Start a simple HTTP server for Prometheus scraping.

    Args:
        monitor: LanceMonitor instance
        port: Port to listen on
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics":
                metrics = monitor.get_prometheus_metrics()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(metrics.encode())
            elif self.path == "/health":
                health = monitor.health_check()
                self.send_response(health["status_code"])
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(health).encode())
            elif self.path == "/dashboard":
                dashboard = monitor.get_dashboard_data()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(dashboard).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress logs

    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    logger.info(f"Metrics server started on port {port}")
    logger.info(f"  /metrics   - Prometheus metrics")
    logger.info(f"  /health    - Health check")
    logger.info(f"  /dashboard - Dashboard data")
    server.serve_forever()


# Demo
if __name__ == "__main__":
    print("=" * 60)
    print("LANCE MONITORING DEMO")
    print("=" * 60)

    # Initialize with some test data
    lance_path = "/tmp/lance_monitoring_demo"
    os.makedirs(lance_path, exist_ok=True)

    db = lancedb.connect(lance_path)

    # Create test table
    import numpy as np
    test_data = [
        {"id": f"doc_{i}", "text": f"Document {i}", "vector": np.random.rand(128).tolist()}
        for i in range(100)
    ]
    db.create_table("test_table", data=test_data, mode="overwrite")

    # Initialize monitor
    monitor = LanceMonitor(lance_path)

    # Collect metrics
    print("\n[1] Collecting metrics...")
    monitor.collect_metrics()

    # Record some operations
    print("\n[2] Recording operations...")
    monitor.record_query("test_table", 15.5, 10)
    monitor.record_query("test_table", 22.3, 5)
    monitor.record_write("test_table", 50, 100.5, True)
    monitor.record_write("test_table", 0, 0, False)  # Simulated failure

    # Health check
    print("\n[3] Health check...")
    health = monitor.health_check()
    print(f"    Status: {health['status']}")
    print(f"    Checks: {health['checks']}")

    # Prometheus metrics
    print("\n[4] Prometheus metrics...")
    metrics = monitor.get_prometheus_metrics()
    print(metrics[:500] + "..." if len(metrics) > 500 else metrics)

    # Dashboard data
    print("\n[5] Dashboard data...")
    dashboard = monitor.get_dashboard_data()
    print(f"    Summary: {dashboard['summary']}")
    print(f"    Tables: {dashboard['tables']}")
    print(f"    Alerts: {dashboard['alerts']}")

    print("\n" + "=" * 60)
    print("To start metrics server: start_metrics_server(monitor, port=9090)")
    print("=" * 60)
