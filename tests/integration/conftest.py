"""Pytest fixtures for integration tests.

Provides service fixtures using testcontainers for isolated testing.
"""

import os
import pytest
import time
from typing import Generator

# Check if testcontainers is available
try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.kafka import KafkaContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None
    KafkaContainer = None


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may require Docker)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )


@pytest.fixture(scope="session")
def docker_available() -> bool:
    """Check if Docker is available."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def postgres_container(docker_available) -> Generator:
    """Start a PostgreSQL container for testing.

    Provides an isolated PostgreSQL instance with the iceberg_catalog database.
    """
    if not docker_available:
        pytest.skip("Docker not available")

    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed")

    container = PostgresContainer(
        image="postgres:16",
        username="iceberg",
        password="iceberg",
        dbname="iceberg_catalog",
    )

    try:
        container.start()
        # Wait for PostgreSQL to be ready
        time.sleep(2)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def kafka_container(docker_available) -> Generator:
    """Start a Kafka container for testing.

    Provides an isolated Kafka broker for streaming tests.
    """
    if not docker_available:
        pytest.skip("Docker not available")

    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed")

    container = KafkaContainer(image="confluentinc/cp-kafka:7.5.0")

    try:
        container.start()
        # Wait for Kafka to be ready
        time.sleep(5)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def postgres_connection_string(postgres_container) -> str:
    """Get PostgreSQL connection string from container."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def kafka_bootstrap_servers(kafka_container) -> str:
    """Get Kafka bootstrap servers from container."""
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def spark_with_postgres(postgres_container):
    """Create a SparkSession configured for PostgreSQL Iceberg catalog.

    This fixture creates a Spark session that uses the test PostgreSQL
    container as the Iceberg catalog backend.
    """
    from pyspark.sql import SparkSession

    # Get connection details
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    jdbc_url = f"jdbc:postgresql://{host}:{port}/iceberg_catalog"

    # Build SparkSession with Iceberg configuration
    spark = (
        SparkSession.builder.appName("lakehouse-integration-tests")
        .master("local[2]")
        .config("spark.driver.memory", "1g")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        # Iceberg configuration
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "jdbc")
        .config("spark.sql.catalog.iceberg.uri", jdbc_url)
        .config("spark.sql.catalog.iceberg.jdbc.user", "iceberg")
        .config("spark.sql.catalog.iceberg.jdbc.password", "iceberg")
        .config("spark.sql.catalog.iceberg.warehouse", "/tmp/iceberg-warehouse")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")
    yield spark
    spark.stop()


@pytest.fixture(scope="function")
def clean_warehouse(tmp_path):
    """Provide a clean temporary warehouse directory for each test."""
    warehouse_path = tmp_path / "warehouse"
    warehouse_path.mkdir(parents=True, exist_ok=True)
    return str(warehouse_path)


@pytest.fixture(scope="session")
def project_root() -> str:
    """Return the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def lakehouse_cli(project_root) -> str:
    """Return the path to the lakehouse CLI script."""
    return os.path.join(project_root, "lakehouse")
