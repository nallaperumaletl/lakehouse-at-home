#!/bin/bash

# Load credentials
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../.env"

echo "Running Iceberg integration test with PySpark..."

# Run spark-submit with Python script
docker exec -i spark-master /opt/spark/bin/spark-submit \
  --master local[*] \
  --deploy-mode client \
  --jars /opt/spark/jars-extra/iceberg-spark-runtime-4.0_2.13-1.10.0.jar,/opt/spark/jars-extra/hadoop-aws-3.4.1.jar,/opt/spark/jars-extra/aws-java-sdk-bundle-1.12.780.jar,/opt/spark/jars-extra/bundle-2.24.6.jar,/opt/spark/jars-extra/postgresql-42.7.4.jar \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.iceberg.type=jdbc \
  --conf spark.sql.catalog.iceberg.uri=jdbc:postgresql://localhost:5432/iceberg_catalog \
  --conf spark.sql.catalog.iceberg.jdbc.user=${POSTGRES_USER} \
  --conf spark.sql.catalog.iceberg.jdbc.password=${POSTGRES_PASSWORD} \
  --conf spark.sql.catalog.iceberg.warehouse=${S3_WAREHOUSE} \
  --conf spark.hadoop.fs.s3a.endpoint=${S3_ENDPOINT} \
  --conf spark.hadoop.fs.s3a.access.key=${S3_ACCESS_KEY} \
  --conf spark.hadoop.fs.s3a.secret.key=${S3_SECRET_KEY} \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
  /scripts/test-iceberg.py

echo ""
echo "Test complete!"
