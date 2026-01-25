"""
Airflow DAG validation tests.

Tests DAG structure, task dependencies, and configuration without requiring
a running Airflow instance.
"""

import ast
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAGS_DIR = os.path.join(PROJECT_ROOT, "dags")

# Add dags directory to path for imports
sys.path.insert(0, DAGS_DIR)


class TestDAGSyntax:
    """Test DAG files for valid Python syntax."""

    def test_medallion_pipeline_syntax(self):
        """Medallion pipeline DAG should have valid Python syntax."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            source = f.read()
        # This will raise SyntaxError if invalid
        ast.parse(source)

    def test_iceberg_maintenance_syntax(self):
        """Iceberg maintenance DAG should have valid Python syntax."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            source = f.read()
        ast.parse(source)


class TestDAGStructure:
    """Test DAG structure and configuration."""

    @pytest.fixture(autouse=True)
    def mock_airflow(self):
        """Mock Airflow components for testing without Airflow installed."""
        # Mock Variable.get to return default values
        mock_variable = MagicMock()
        mock_variable.get = MagicMock(return_value="4.1")

        with patch.dict(
            "sys.modules",
            {
                "airflow": MagicMock(),
                "airflow.models": MagicMock(Variable=mock_variable),
                "airflow.operators.bash": MagicMock(),
                "airflow.operators.python": MagicMock(),
                "airflow.providers.apache.kafka.sensors.kafka": MagicMock(),
            },
        ):
            yield

    def test_medallion_pipeline_has_required_tasks(self):
        """Medallion pipeline should have all required tasks."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        required_tasks = [
            "check_kafka",
            "choose_spark",
            "run_pipeline_spark41",
            "run_pipeline_spark40",
            "verify_tables",
        ]

        for task in required_tasks:
            assert task in content, f"Missing task: {task}"

    def test_iceberg_maintenance_has_required_tasks(self):
        """Iceberg maintenance DAG should have maintenance tasks."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        required_patterns = [
            "expire_snapshots",
            "remove_orphans",
            "compact_files",
            "check_spark",
        ]

        for pattern in required_patterns:
            assert pattern in content, f"Missing pattern: {pattern}"

    def test_medallion_pipeline_dag_config(self):
        """Medallion pipeline should have correct DAG configuration."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        # Check DAG ID
        assert 'dag_id="lakehouse_medallion_pipeline"' in content

        # Check schedule
        assert 'schedule="@daily"' in content

        # Check catchup is disabled
        assert "catchup=False" in content

        # Check tags
        assert '"lakehouse"' in content
        assert '"iceberg"' in content

    def test_iceberg_maintenance_dag_config(self):
        """Iceberg maintenance should have correct DAG configuration."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Check DAG ID
        assert 'dag_id="iceberg_maintenance"' in content

        # Check schedule (daily at 3 AM)
        assert '"0 3 * * *"' in content

        # Check catchup is disabled
        assert "catchup=False" in content

    def test_compact_on_demand_dag_config(self):
        """On-demand compaction DAG should have manual trigger."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Check DAG ID
        assert 'dag_id="iceberg_compact_on_demand"' in content

        # Check no schedule (manual only)
        assert "schedule=None" in content


class TestDAGDependencies:
    """Test task dependencies are correctly defined."""

    def test_medallion_pipeline_dependencies(self):
        """Medallion pipeline should have correct task flow."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        # Check dependency chain
        assert "check_kafka >> choose_spark" in content
        assert "choose_spark >> [run_pipeline_spark41, run_pipeline_spark40]" in content
        assert "[run_pipeline_spark41, run_pipeline_spark40] >> verify_tables" in content

    def test_iceberg_maintenance_dependencies(self):
        """Iceberg maintenance should chain tasks correctly."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Check that tasks are chained: check_spark -> expire -> orphans -> compact
        assert "check_spark >> expire_task >> orphan_task >> compact_task" in content


class TestDAGDefaultArgs:
    """Test DAG default arguments."""

    def test_medallion_pipeline_default_args(self):
        """Medallion pipeline should have sensible default args."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        # Check owner
        assert '"owner": "lakehouse"' in content

        # Check retries
        assert '"retries":' in content

        # Check depends_on_past is False
        assert '"depends_on_past": False' in content

    def test_iceberg_maintenance_default_args(self):
        """Iceberg maintenance should have sensible default args."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Check owner
        assert '"owner": "lakehouse"' in content

        # Check retries (should be > 1 for maintenance tasks)
        assert '"retries": 2' in content


class TestSparkIntegration:
    """Test Spark integration in DAGs."""

    def test_medallion_pipeline_uses_docker_exec(self):
        """Pipeline should execute Spark via docker exec."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        assert "docker exec spark-master-41" in content
        assert "docker exec spark-master" in content
        assert "spark-submit" in content

    def test_iceberg_maintenance_uses_spark_sql(self):
        """Maintenance DAG should use spark-sql for Iceberg procedures."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        assert "spark-sql" in content
        assert "iceberg.system.expire_snapshots" in content
        assert "iceberg.system.remove_orphan_files" in content
        assert "iceberg.system.rewrite_data_files" in content

    def test_spark_version_variable_used(self):
        """DAGs should use spark_version variable for flexibility."""
        for dag_file in ["lakehouse_medallion_pipeline.py", "iceberg_maintenance.py"]:
            dag_path = os.path.join(DAGS_DIR, dag_file)
            with open(dag_path) as f:
                content = f.read()

            assert 'Variable.get("spark_version"' in content, f"{dag_file} should use spark_version variable"


class TestIcebergMaintenance:
    """Test Iceberg maintenance specific configurations."""

    def test_tables_to_maintain(self):
        """Should maintain all medallion layer tables."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        expected_tables = [
            "iceberg.bronze.orders",
            "iceberg.silver.orders_clean",
            "iceberg.gold.daily_summary",
        ]

        for table in expected_tables:
            assert table in content, f"Missing table: {table}"

    def test_snapshot_retention(self):
        """Should retain reasonable number of snapshots."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Check retain_last parameter
        assert "retain_last => 5" in content

    def test_file_compaction_target_size(self):
        """Should use reasonable target file size for compaction."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # 128MB = 134217728 bytes
        assert "134217728" in content or "target-file-size-bytes" in content


class TestErrorHandling:
    """Test error handling in DAGs."""

    def test_medallion_pipeline_soft_fail_kafka(self):
        """Kafka check should not fail the entire DAG."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        # Should continue even if Kafka is unavailable
        assert "Kafka not available - continuing anyway" in content

    def test_maintenance_handles_missing_tables(self):
        """Maintenance tasks should handle missing tables gracefully."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        # Should have fallback for non-existent tables
        assert "table may not exist" in content

    def test_verify_tables_trigger_rule(self):
        """Verify tables task should run even if one branch fails."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        assert 'trigger_rule="none_failed_min_one_success"' in content
