#!/bin/bash

set -e  # Exit on error

JARS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../jars" && pwd)"

echo "📦 Downloading JARs to ${JARS_DIR}..."
mkdir -p "${JARS_DIR}"
cd "${JARS_DIR}"

# Iceberg Spark Runtime (45MB)
echo "⬇️  Iceberg Spark Runtime 4.0_2.13-1.10.0..."
wget -q --show-progress https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.0_2.13/1.10.0/iceberg-spark-runtime-4.0_2.13-1.10.0.jar

# Hadoop AWS (846KB)
echo "⬇️  Hadoop AWS 3.4.1..."
wget -q --show-progress https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.jar

# AWS SDK v1 Bundle (371MB)
echo "⬇️  AWS Java SDK Bundle 1.12.780..."
wget -q --show-progress https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.780/aws-java-sdk-bundle-1.12.780.jar

# AWS SDK v2 Bundle (443MB) - CRITICAL: Must be 2.24.6 for Hadoop 3.4.1
echo "⬇️  AWS SDK v2 Bundle 2.24.6 (exact version for Hadoop 3.4.1)..."
wget -q --show-progress https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.24.6/bundle-2.24.6.jar

# PostgreSQL JDBC (1.1MB)
echo "⬇️  PostgreSQL JDBC 42.7.4..."
wget -q --show-progress https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar

echo ""
echo "✅ All JARs downloaded successfully!"
echo ""
echo "📊 Total size:"
du -sh "${JARS_DIR}"
