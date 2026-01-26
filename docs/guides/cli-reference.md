# CLI Reference

Complete reference for the `./lakehouse` command-line interface.

## Usage

```bash
./lakehouse <command> [options] [--version 4.0|4.1] [--json]
```

## Global Options

| Option | Description |
|--------|-------------|
| `--version 4.0\|4.1` | Select Spark version (default: 4.1) |
| `--json` | Output in JSON format (status command) |

## Commands

### setup

Validate environment and install dependencies.

```bash
./lakehouse setup
```

Performs:
1. Checks prerequisites (Docker, Poetry, curl, etc.)
2. Creates `.env` from template if missing
3. Creates `spark-defaults.conf` from template if missing
4. Downloads missing JARs
5. Runs `poetry install`
6. Checks disk space
7. Detects port conflicts

### status

Show all services status.

```bash
./lakehouse status
./lakehouse status --json
```

Human output shows colored indicators. JSON output:
```json
{
  "services": {"postgresql": true, "seaweedfs": true},
  "spark": {"4.0": {"master": true, "worker": true}, "4.1": {...}},
  "kafka": {"broker": true, "zookeeper": true},
  "all_healthy": true
}
```

### start

Start services.

```bash
./lakehouse start all              # Start Spark + Kafka
./lakehouse start spark            # Start Spark only
./lakehouse start kafka            # Start Kafka only
./lakehouse start airflow          # Start Airflow (scheduler + webserver)
./lakehouse start spark --version 4.0  # Start Spark 4.0
```

Waits for services to be healthy before returning.

### stop

Stop services.

```bash
./lakehouse stop all
./lakehouse stop spark
./lakehouse stop kafka
./lakehouse stop airflow
./lakehouse stop spark --version 4.0
```

### restart

Restart services (stop + start).

```bash
./lakehouse restart all
./lakehouse restart spark
./lakehouse restart kafka
```

### logs

View service logs (follows/tails).

```bash
./lakehouse logs spark-master
./lakehouse logs spark-worker
./lakehouse logs kafka
./lakehouse logs zookeeper
./lakehouse logs airflow-webserver
./lakehouse logs airflow-scheduler
./lakehouse logs spark-master --version 4.0
```

Press `Ctrl+C` to stop following.

### test

Run connectivity tests.

```bash
./lakehouse test
```

Tests:
1. PostgreSQL connection
2. SeaweedFS S3 endpoint
3. Kafka broker
4. Spark master

Returns exit code 0 if all pass, 1 if any fail.

### producer

Start Kafka event producer (synthetic events).

```bash
./lakehouse producer
```

Generates continuous synthetic events to Kafka topic.

### consumer

Start Spark streaming consumer.

```bash
./lakehouse consumer
./lakehouse consumer --version 4.0
```

Reads from Kafka and displays aggregations.

### testdata

Test data generation commands.

```bash
./lakehouse testdata generate              # Generate 90-day dataset
./lakehouse testdata generate --days 7     # Generate 7-day dataset
./lakehouse testdata generate --seed 42    # Reproducible generation

./lakehouse testdata load                  # Load into Iceberg tables
./lakehouse testdata stream                # Stream to Kafka
./lakehouse testdata stream --speed 60     # 60x speed (1 min = 1 hour)

./lakehouse testdata stats                 # Show dataset statistics
./lakehouse testdata clean                 # Remove generated data
```

### help

Show help message.

```bash
./lakehouse help
./lakehouse        # Also shows help
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (prerequisites, config, test failure) |

## Examples

### Daily Workflow

```bash
# Start of day
./lakehouse start all
./lakehouse test

# Work...

# End of day
./lakehouse stop all
```

### Testing with Data

```bash
# Generate small dataset
./lakehouse testdata generate --days 1

# Load to Iceberg
./lakehouse testdata load

# Stream at 100x speed
./lakehouse testdata stream --speed 100
```

### CI/CD Integration

```bash
# Machine-readable status check
if ./lakehouse status --json | jq -e '.all_healthy' > /dev/null; then
  echo "All services healthy"
else
  echo "Services unhealthy"
  exit 1
fi

# Run tests with proper exit code
./lakehouse test || exit 1
```

### Multi-Version Testing

```bash
# Start both Spark versions
./lakehouse start spark --version 4.0
./lakehouse start spark --version 4.1

# Run same job on both
docker exec spark-master /opt/spark/bin/spark-submit /scripts/job.py
docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/job.py

# Compare results...
```

## Environment Variables

The CLI reads from `.env`:
- `POSTGRES_USER` / `POSTGRES_PASSWORD` - Database credentials
- `POSTGRES_HOST` - Database host
- `S3_*` - S3/SeaweedFS settings

## Airflow Commands

```bash
# Start Airflow
./lakehouse start airflow

# Stop Airflow
./lakehouse stop airflow

# View logs
./lakehouse logs airflow-webserver
./lakehouse logs airflow-scheduler
./lakehouse logs airflow-triggerer

# Trigger a DAG manually
docker exec airflow-webserver airflow dags trigger lakehouse_medallion_pipeline

# List DAG runs
docker exec airflow-webserver airflow dags list-runs -d lakehouse_medallion_pipeline
```

See [Airflow Guide](airflow.md) for DAG details and configuration.

## See Also

- [Configuration](../getting-started/configuration.md)
- [Airflow Guide](airflow.md)
- [Troubleshooting](../troubleshooting.md)
