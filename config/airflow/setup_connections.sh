#!/bin/bash
# Setup Airflow connections for lakehouse stack
# Run this after Airflow is initialized

set -e

echo "Setting up Airflow connections..."

# Kafka connection
airflow connections delete kafka_default 2>/dev/null || true
airflow connections add kafka_default \
    --conn-type kafka \
    --conn-extra '{"bootstrap.servers": "localhost:9092", "group.id": "airflow-consumer", "security.protocol": "PLAINTEXT"}'

echo "✓ Kafka connection configured"

# Spark connection for Spark 4.1
airflow connections delete spark_41 2>/dev/null || true
airflow connections add spark_41 \
    --conn-type spark \
    --conn-host "spark://localhost" \
    --conn-port 7078 \
    --conn-extra '{"deploy_mode": "client", "spark_home": "/opt/spark"}'

echo "✓ Spark 4.1 connection configured"

# Spark connection for Spark 4.0
airflow connections delete spark_40 2>/dev/null || true
airflow connections add spark_40 \
    --conn-type spark \
    --conn-host "spark://localhost" \
    --conn-port 7077 \
    --conn-extra '{"deploy_mode": "client", "spark_home": "/opt/spark"}'

echo "✓ Spark 4.0 connection configured"

# PostgreSQL connection (for direct queries)
airflow connections delete postgres_iceberg 2>/dev/null || true
airflow connections add postgres_iceberg \
    --conn-type postgres \
    --conn-host localhost \
    --conn-port 5432 \
    --conn-login "${POSTGRES_USER:-postgres}" \
    --conn-password "${POSTGRES_PASSWORD:-}" \
    --conn-schema iceberg_catalog

echo "✓ PostgreSQL connection configured"

# Set default Airflow variables
airflow variables set spark_version "4.1"
airflow variables set kafka_bootstrap_servers "localhost:9092"

echo "✓ Variables configured"

echo ""
echo "Airflow connections setup complete!"
echo "Access Airflow UI at: http://localhost:8081"
