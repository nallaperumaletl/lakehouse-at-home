#!/bin/bash

set -e  # Exit on error

JARS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../jars" && pwd)"

echo "Downloading Lance JARs to ${JARS_DIR}..."
mkdir -p "${JARS_DIR}"
cd "${JARS_DIR}"

# Lance Spark Bundle for Spark 4.0 (Scala 2.13) - ~260MB
# This bundle includes all necessary dependencies (lance-core, lance-jni, etc.)
LANCE_VERSION="0.0.15"
LANCE_JAR="lance-spark-bundle-4.0_2.13-${LANCE_VERSION}.jar"
LANCE_URL="https://repo1.maven.org/maven2/com/lancedb/lance-spark-bundle-4.0_2.13/${LANCE_VERSION}/${LANCE_JAR}"

if [ -f "${LANCE_JAR}" ]; then
    echo "Lance Spark bundle already exists: ${LANCE_JAR}"
else
    echo "Downloading Lance Spark Bundle ${LANCE_VERSION} for Spark 4.0..."
    wget -q --show-progress "${LANCE_URL}"
fi

echo ""
echo "Lance JARs downloaded successfully!"
echo ""
echo "JAR details:"
ls -lh "${JARS_DIR}"/lance-*.jar 2>/dev/null || echo "No lance JARs found"
