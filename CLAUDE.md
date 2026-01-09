# CLAUDE.md - Agent Guide for lakehouse-stack

## Project Overview

Self-hostable data lakehouse: Spark 4.x + Iceberg 1.10 + Kafka 3.6 + PostgreSQL + SeaweedFS.

## Documentation

Full docs in `docs/` directory:
- `docs/getting-started/` - Installation, quickstart, configuration
- `docs/guides/` - CLI reference, streaming, test data, multi-version Spark
- `docs/deployment/` - Local and AWS deployment
- `docs/architecture.md` - System design
- `docs/troubleshooting.md` - Common issues

## Quick Commands

```bash
./lakehouse setup          # Validate prereqs, download JARs, install deps
./lakehouse start all      # Start Spark + Kafka
./lakehouse stop all       # Stop all services
./lakehouse status         # Human-readable status
./lakehouse status --json  # Machine-readable status
./lakehouse test           # Connectivity tests (returns exit code)
./lakehouse logs <service> # View logs (spark-master, kafka, etc.)
```

## Test Data

```bash
./lakehouse testdata generate --days 7   # Generate 7 days of order data
./lakehouse testdata load                # Load to Iceberg tables
./lakehouse testdata stream --speed 60   # Stream to Kafka at 60x speed
```

## Key Files

| Path | Purpose |
|------|---------|
| `lakehouse` | CLI script (bash) |
| `.env` | Credentials (from .env.example) |
| `config/spark/spark-defaults.conf` | Spark config (from .example) |
| `docker-compose-spark41.yml` | Spark 4.1 cluster |
| `docker-compose-kafka.yml` | Kafka + Zookeeper |
| `jars/` | Required JARs (~860MB) |
| `scripts/` | PySpark examples |
| `terraform/` | AWS infrastructure |

## Architecture

```
Spark 4.x → Iceberg 1.10 → PostgreSQL (metadata) + SeaweedFS (data)
                ↑
            Kafka 3.6 (streaming)
```

**Namespaces (Medallion):**
- `iceberg.bronze.*` - Raw data
- `iceberg.silver.*` - Cleaned
- `iceberg.gold.*` - Aggregated

## Ports

| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| SeaweedFS | 8333 |
| Spark 4.0 | 7077 (UI: 8080) |
| Spark 4.1 | 7078 (UI: 8082) |
| Kafka | 9092 |
| Zookeeper | 2181 |

## Code Style

- **Python:** 3.10+, Black (88 chars), Ruff
- **PySpark:** `from pyspark.sql import functions as f`

## Critical Versions

Do not change without testing:
- AWS SDK v2: **2.24.6** (exact for Hadoop 3.4.1)
- Iceberg: **1.10.0**
- Spark: **4.0.1** or **4.1.0** (Scala 2.13)

## Credentials

Stored in `config/spark/spark-defaults.conf` (not in git):
- PostgreSQL: `spark.sql.catalog.iceberg.jdbc.user/password`
- S3: `spark.hadoop.fs.s3a.access.key/secret.key`

## Common Tasks

```bash
# Submit Spark job
docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/01-basics.py

# Download JARs
./scripts/download-jars.sh

# Format Python
poetry run black .
poetry run ruff check .
```

## Troubleshooting

See `docs/troubleshooting.md` for full guide.

Quick checks:
```bash
./lakehouse test                    # Test all services
./lakehouse status --json           # Check health
docker logs spark-master-41         # Spark logs
docker logs kafka                   # Kafka logs
```
