# Scripts Directory

This directory contains all executable scripts for the lakehouse stack.

## Directory Structure

```
scripts/
├── quickstarts/      # Learning tutorials (run these first!)
├── connectivity/     # Service connectivity tests
├── pipelines/        # Medallion pipeline scripts
├── demos/            # SDP demo scripts
├── tools/            # Utility scripts
└── testdata/         # Test data generation module
```

## Quickstarts (Start Here)

Self-contained tutorials that create their own tables and clean up after themselves.

| Script | Description | Prerequisites |
|--------|-------------|---------------|
| `01-basics.py` | Spark + Iceberg fundamentals | Spark running |
| `02-transformations.py` | Narrow vs wide transformations, joins, aggregations | Spark running |
| `03-streaming-basic.py` | Spark Structured Streaming with rate source | Spark running |
| `04-kafka-streaming.py` | Kafka to Spark streaming | Spark + Kafka + producer |
| `iceberg-spark-quickstart.py` | Complete Iceberg features demo | Spark running |
| `unity-catalog-demo.py` | Unity Catalog REST catalog | Unity Catalog running |

**Run a quickstart:**
```bash
docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/quickstarts/01-basics.py
```

## Connectivity Tests

Used by CI and `./lakehouse test` to verify services are working.

| Script | Tests |
|--------|-------|
| `test-iceberg.py` | Iceberg catalog connectivity |
| `test-kafka.py` | Kafka broker connectivity |
| `test-seaweedfs.py` | S3-compatible storage |
| `test-full-stack.py` | All services together |
| `test-streaming-iceberg.py` | Streaming to Iceberg tables |
| `test-spark-versions.sh` | Multi-version Spark compatibility |
| `test-unity-catalog-live.py` | Unity Catalog integration |

## Pipelines

Medallion architecture pipelines for Airflow DAGs.

| Script | Description | Prerequisites |
|--------|-------------|---------------|
| `pipeline_spark41.py` | Declarative pipeline (Spark 4.1) | Test data generated |
| `pipeline_spark40.py` | Same pipeline for Spark 4.0 | Test data generated |
| `pipeline_sdp.py` | Spark Declarative Pipelines demo | Test data generated |

**Generate test data first:**
```bash
./lakehouse testdata generate --days 7
./lakehouse testdata load
```

## Demos

Interactive demos for learning specific features.

| Directory | Description |
|-----------|-------------|
| `demos/` | SDP (Spark Declarative Pipelines) demo |

**Run the SDP demo:**
```bash
cd scripts/demos
./run_demo.sh
```

## Tools

Utility scripts for development and operations.

| Script | Description |
|--------|-------------|
| `download-jars.sh` | Download required JAR dependencies |
| `kafka-producer.py` | Generate synthetic Kafka events |
| `run-spark-test.sh` | Run tests against Spark cluster |

## Test Data Module

Python module for generating realistic test data.

```bash
# Generate data
./lakehouse testdata generate --days 7

# Load to Iceberg
./lakehouse testdata load

# Stream to Kafka
./lakehouse testdata stream --speed 60
```

See `./lakehouse testdata --help` for all options.
