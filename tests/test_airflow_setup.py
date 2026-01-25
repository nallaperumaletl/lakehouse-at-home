"""Tests for Airflow orchestration setup.

These tests validate the Airflow configuration without requiring
a running Airflow instance - they check file structure, syntax,
and configuration validity.
"""

import os
import ast
import pytest
import yaml


# Paths relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAGS_DIR = os.path.join(PROJECT_ROOT, "dags")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config", "airflow")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker", "airflow")


class TestAirflowDockerSetup:
    """Tests for Airflow Docker configuration."""

    def test_docker_compose_exists(self):
        """docker-compose-airflow.yml should exist."""
        compose_path = os.path.join(PROJECT_ROOT, "docker-compose-airflow.yml")
        assert os.path.exists(compose_path), "docker-compose-airflow.yml not found"

    def test_docker_compose_valid_yaml(self):
        """docker-compose-airflow.yml should be valid YAML."""
        compose_path = os.path.join(PROJECT_ROOT, "docker-compose-airflow.yml")
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        assert config is not None
        assert "services" in config or "x-airflow-common" in config

    def test_docker_compose_has_required_services(self):
        """Docker compose should define required Airflow services."""
        compose_path = os.path.join(PROJECT_ROOT, "docker-compose-airflow.yml")
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        services = config.get("services", {})
        required_services = ["airflow-webserver", "airflow-scheduler", "airflow-init"]

        for service in required_services:
            assert service in services, f"Missing required service: {service}"

    def test_docker_compose_uses_correct_port(self):
        """Airflow webserver should use port 8085 to avoid Spark conflict."""
        compose_path = os.path.join(PROJECT_ROOT, "docker-compose-airflow.yml")
        with open(compose_path) as f:
            content = f.read()

        # Check that port 8085 is configured (avoids Spark 4.0 UI and worker ports)
        assert "8085" in content, "Airflow should use port 8085"

    def test_dockerfile_exists(self):
        """Airflow Dockerfile should exist."""
        dockerfile_path = os.path.join(DOCKER_DIR, "Dockerfile")
        assert os.path.exists(dockerfile_path), "docker/airflow/Dockerfile not found"

    def test_dockerfile_has_required_components(self):
        """Dockerfile should install required components."""
        dockerfile_path = os.path.join(DOCKER_DIR, "Dockerfile")
        with open(dockerfile_path) as f:
            content = f.read()

        # Check for essential components
        assert "apache-airflow" in content.lower(), "Airflow base image required"
        assert "spark" in content.lower(), "Spark installation required"
        assert "providers" in content.lower(), "Airflow providers required"


class TestAirflowDAGs:
    """Tests for Airflow DAG files."""

    def test_dags_directory_exists(self):
        """DAGs directory should exist."""
        assert os.path.exists(DAGS_DIR), "dags/ directory not found"

    def test_medallion_pipeline_dag_exists(self):
        """Medallion pipeline DAG should exist."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        assert os.path.exists(dag_path), "lakehouse_medallion_pipeline.py not found"

    def test_iceberg_maintenance_dag_exists(self):
        """Iceberg maintenance DAG should exist."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        assert os.path.exists(dag_path), "iceberg_maintenance.py not found"

    def test_dag_files_valid_python_syntax(self):
        """All DAG files should have valid Python syntax."""
        dag_files = [f for f in os.listdir(DAGS_DIR) if f.endswith(".py")]

        for dag_file in dag_files:
            dag_path = os.path.join(DAGS_DIR, dag_file)
            with open(dag_path) as f:
                source = f.read()

            try:
                ast.parse(source)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {dag_file}: {e}")

    def test_medallion_pipeline_has_dag_definition(self):
        """Medallion pipeline should define a DAG."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        assert "DAG(" in content or 'dag_id=' in content, "DAG definition not found"
        assert "lakehouse_medallion_pipeline" in content, "Expected dag_id not found"

    def test_iceberg_maintenance_has_dag_definition(self):
        """Iceberg maintenance should define a DAG."""
        dag_path = os.path.join(DAGS_DIR, "iceberg_maintenance.py")
        with open(dag_path) as f:
            content = f.read()

        assert "DAG(" in content or 'dag_id=' in content, "DAG definition not found"
        assert "iceberg_maintenance" in content, "Expected dag_id not found"

    def test_dags_use_bash_operator_for_spark(self):
        """DAGs should use BashOperator for Spark job submission."""
        dag_path = os.path.join(DAGS_DIR, "lakehouse_medallion_pipeline.py")
        with open(dag_path) as f:
            content = f.read()

        # Should use BashOperator to call docker exec spark-submit
        assert "BashOperator" in content, "BashOperator should be used for Spark jobs"
        assert "spark-submit" in content or "spark-master" in content, \
            "DAG should reference Spark submission"


class TestAirflowConfig:
    """Tests for Airflow configuration files."""

    def test_config_directory_exists(self):
        """Airflow config directory should exist."""
        assert os.path.exists(CONFIG_DIR), "config/airflow/ directory not found"

    def test_setup_connections_script_exists(self):
        """Connection setup script should exist."""
        script_path = os.path.join(CONFIG_DIR, "setup_connections.sh")
        assert os.path.exists(script_path), "setup_connections.sh not found"

    def test_setup_connections_has_kafka(self):
        """Setup script should configure Kafka connection."""
        script_path = os.path.join(CONFIG_DIR, "setup_connections.sh")
        with open(script_path) as f:
            content = f.read()

        assert "kafka" in content.lower(), "Kafka connection setup missing"

    def test_setup_connections_has_spark(self):
        """Setup script should configure Spark connections."""
        script_path = os.path.join(CONFIG_DIR, "setup_connections.sh")
        with open(script_path) as f:
            content = f.read()

        assert "spark" in content.lower(), "Spark connection setup missing"

    def test_setup_connections_has_postgres(self):
        """Setup script should configure PostgreSQL connection."""
        script_path = os.path.join(CONFIG_DIR, "setup_connections.sh")
        with open(script_path) as f:
            content = f.read()

        assert "postgres" in content.lower(), "PostgreSQL connection setup missing"


class TestEnvironmentConfig:
    """Tests for environment configuration."""

    def test_env_example_has_airflow_vars(self):
        """env.example should include Airflow variables."""
        env_path = os.path.join(PROJECT_ROOT, ".env.example")
        with open(env_path) as f:
            content = f.read()

        assert "AIRFLOW_ADMIN_USER" in content, "AIRFLOW_ADMIN_USER missing"
        assert "AIRFLOW_ADMIN_PASSWORD" in content, "AIRFLOW_ADMIN_PASSWORD missing"
        assert "AIRFLOW_FERNET_KEY" in content, "AIRFLOW_FERNET_KEY missing"

    def test_gitignore_excludes_airflow_logs(self):
        """gitignore should exclude Airflow logs."""
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()

        assert "airflow" in content.lower(), "Airflow entries missing from .gitignore"


class TestCLIIntegration:
    """Tests for lakehouse CLI Airflow integration."""

    def test_cli_has_airflow_commands(self):
        """Lakehouse CLI should include Airflow commands."""
        cli_path = os.path.join(PROJECT_ROOT, "lakehouse")
        with open(cli_path) as f:
            content = f.read()

        # Check for Airflow in start/stop commands
        assert "airflow)" in content, "Airflow case missing in CLI"
        assert "docker-compose-airflow.yml" in content, "Airflow compose file reference missing"

    def test_cli_help_mentions_airflow(self):
        """CLI help should document Airflow service."""
        cli_path = os.path.join(PROJECT_ROOT, "lakehouse")
        with open(cli_path) as f:
            content = f.read()

        # Check help text includes airflow
        assert "airflow" in content.lower(), "Airflow not mentioned in CLI"

    def test_cli_status_includes_airflow(self):
        """CLI status should check Airflow containers."""
        cli_path = os.path.join(PROJECT_ROOT, "lakehouse")
        with open(cli_path) as f:
            content = f.read()

        assert "airflow-webserver" in content, "Airflow webserver status check missing"
        assert "airflow-scheduler" in content, "Airflow scheduler status check missing"
