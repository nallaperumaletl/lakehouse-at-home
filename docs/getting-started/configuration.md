# Configuration

This guide covers configuring the lakehouse stack for your environment.

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables (credentials, endpoints) |
| `config/spark/spark-defaults.conf` | Spark and Iceberg settings |

## Environment Variables (.env)

Create from the template:
```bash
cp .env.example .env
```

### Required Variables

```bash
# PostgreSQL (Iceberg catalog)
POSTGRES_USER=lakehouse
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=host.docker.internal  # or localhost
POSTGRES_PORT=5432

# SeaweedFS (S3-compatible storage)
S3_ENDPOINT=http://host.docker.internal:8333
S3_BUCKET=lakehouse
S3_WAREHOUSE=s3a://lakehouse/warehouse

# Iceberg (derived from above)
ICEBERG_CATALOG_URI=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/iceberg_catalog
ICEBERG_WAREHOUSE=${S3_WAREHOUSE}
```

### Host Configuration

| Environment | POSTGRES_HOST | S3_ENDPOINT |
|-------------|---------------|-------------|
| macOS/Windows Docker | `host.docker.internal` | `http://host.docker.internal:8333` |
| Linux Docker | `172.17.0.1` or `localhost` | `http://172.17.0.1:8333` |
| Native (no Docker) | `localhost` | `http://localhost:8333` |

## Spark Configuration

Create from the template:
```bash
cp config/spark/spark-defaults.conf.example config/spark/spark-defaults.conf
```

### Key Settings

```properties
# Iceberg Catalog (JDBC)
spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.type=jdbc
spark.sql.catalog.iceberg.uri=jdbc:postgresql://host.docker.internal:5432/iceberg_catalog
spark.sql.catalog.iceberg.jdbc.user=lakehouse
spark.sql.catalog.iceberg.jdbc.password=your_password
spark.sql.catalog.iceberg.warehouse=s3a://lakehouse/warehouse

# S3/SeaweedFS
spark.hadoop.fs.s3a.endpoint=http://host.docker.internal:8333
spark.hadoop.fs.s3a.path.style.access=true
spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem
spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider

# Performance
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
```

### Spark Version Differences

| Setting | Spark 4.0 | Spark 4.1 |
|---------|-----------|-----------|
| Master port | 7077 | 7078 |
| UI port | 8080 | 8082 |
| Worker UI | 8081 | 8083 |
| Java version | 17 | 21 |

## Docker Compose Configuration

### Spark 4.1 (docker-compose-spark41.yml)

Key environment variables passed to containers:
- All Spark config from `config/spark/spark-defaults.conf`
- JARs mounted from `./jars/`
- Scripts mounted from `./scripts/`

#### Scripts Directory Structure

```
scripts/
├── quickstarts/     # Learning tutorials (01-04)
├── quickstarts/     # Tutorials and demos
├── tools/           # Utilities (download-jars.sh, kafka-producer.py)
├── connectivity/    # Integration tests (test-iceberg.py, test-kafka.py)
└── testdata/        # Test data generation module
```

### Kafka (docker-compose-kafka.yml)

Default configuration:
- Zookeeper: port 2181
- Kafka broker: port 9092
- Single broker setup (development only)

## Resource Limits

For local development, recommended minimums:
- **Memory**: 8GB RAM (16GB recommended)
- **Disk**: 20GB free space (for JARs + data)
- **CPU**: 4 cores

Adjust Docker Desktop resources if needed:
- Docker Desktop → Settings → Resources

## Network Modes

The stack uses `network_mode: host` for Docker containers, meaning:
- Containers share the host's network namespace
- No port mapping needed (containers bind directly)
- Services communicate via `localhost`

This simplifies configuration but requires:
- No conflicting services on the same ports
- PostgreSQL and SeaweedFS running on the host

## Validation

After configuration, validate with:

```bash
# Check all settings
./lakehouse setup

# Test connectivity
./lakehouse test

# View current status (JSON)
./lakehouse status --json
```

## Next Steps

- [CLI Reference](../guides/cli-reference.md) - All available commands
- [Troubleshooting](../troubleshooting.md) - Configuration issues
