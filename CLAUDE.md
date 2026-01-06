# CLAUDE.md - Developer Guide for lakehouse-stack

## Project Overview

A self-hostable data lakehouse stack combining Apache Spark 4.1, Apache Iceberg 1.10, and Kafka for local development and testing of OSS data workflows. Uses PostgreSQL for Iceberg catalog metadata and SeaweedFS for S3-compatible object storage.

## Quick Commands

```bash
# Start all services
./lakehouse start all

# Stop all services
./lakehouse stop all

# Check service status
./lakehouse status

# Run connectivity tests
./lakehouse test

# View logs
./lakehouse logs spark-master
./lakehouse logs kafka

# Start Kafka producer (synthetic events)
./lakehouse producer

# Start Spark streaming consumer
./lakehouse consumer
```

### Docker Compose

```bash
# Spark 4.1 cluster
docker compose -f docker-compose-spark41.yml up -d

# Kafka + Zookeeper
docker compose -f docker-compose-kafka.yml up -d
```

### Python/Poetry

```bash
poetry install          # Install dependencies
poetry run pytest       # Run tests
poetry run black .      # Format code
poetry run ruff check   # Lint code
```

## Architecture

```
Spark 4.1 (Master/Workers)
    ↓
Iceberg 1.10 (Table Format)
    ↓
PostgreSQL 16 (Catalog)  +  SeaweedFS (S3 Storage)
    ↓
Kafka 3.6.1 (Streaming)
```

**Table Naming Convention (Medallion):**
- `iceberg.bronze.*` - Raw data
- `iceberg.silver.*` - Cleaned/transformed
- `iceberg.gold.*` - Business-ready

## Code Style

- **Formatter:** Black (line length 88)
- **Linter:** Ruff (rules: E, F, I)
- **Python:** 3.10+
- **Import alias:** `from pyspark.sql import functions as f`

## Key Files

| Path | Purpose |
|------|---------|
| `lakehouse` | CLI management script |
| `docker-compose-spark41.yml` | Spark 4.1 cluster |
| `docker-compose-kafka.yml` | Kafka + Zookeeper |
| `config/spark/spark-defaults.conf` | Spark + Iceberg config |
| `.env` | Environment variables (credentials) |
| `scripts/` | PySpark example scripts |
| `jars/` | External JARs (~956MB) |

## Environment Variables

Required in `.env`:
```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET
ICEBERG_CATALOG_URI, ICEBERG_WAREHOUSE
```

## Critical Version Locks

**Do not upgrade without testing compatibility:**
- AWS SDK v2: **2.24.6** (exact match for Hadoop 3.4.1)
- Iceberg: **1.10.0** (for Spark 4.0/4.1)
- Spark: **4.1.0** with Scala 2.13

## Scripts Reference

| Script | Description |
|--------|-------------|
| `01-basics.py` | Basic Spark table operations |
| `02-transformations.py` | Narrow & wide transformations |
| `03-streaming-basic.py` | Streaming with rate source |
| `04-kafka-streaming.py` | Kafka streaming (WIP) |
| `kafka-producer.py` | Synthetic event generator |
| `test-iceberg.py` | Iceberg connectivity test |
| `download-jars.sh` | Download required JARs |

## Network Configuration

- Services use `network_mode: host` for Docker
- PostgreSQL and SeaweedFS run natively on host
- Use `host.docker.internal` for Docker-to-host communication

## Common Tasks

### Submit a Spark job
```bash
spark-submit --master spark://localhost:7077 scripts/01-basics.py
```

### Test Iceberg connectivity
```bash
./scripts/run-spark-test.sh
```

### Download JAR dependencies
```bash
./scripts/download-jars.sh
```

## Troubleshooting

- **JAR conflicts:** Ensure exact versions in `jars/` directory
- **Connection refused:** Check that PostgreSQL/SeaweedFS are running on host
- **Kafka not connecting:** Verify Zookeeper is healthy first
- **Spark UI:** http://localhost:8080 (master), http://localhost:4040 (app)
