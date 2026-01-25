# Multi-Version Spark

Run Spark 4.0 and 4.1 simultaneously for A/B testing and migration validation.

## Overview

The lakehouse stack supports running both Spark versions at the same time, each with isolated ports and containers.

| Version | Master Port | UI Port | Worker UI | Container Names |
|---------|-------------|---------|-----------|-----------------|
| 4.0.1 | 7077 | 8080 | 8081 | spark-master, spark-worker |
| 4.1.0 | 7078 | 8082 | 8083 | spark-master-41, spark-worker-41 |

## Starting Both Versions

```bash
# Start Spark 4.0
./lakehouse start spark --version 4.0

# Start Spark 4.1
./lakehouse start spark --version 4.1

# Verify both running
./lakehouse status
```

## Version-Specific Commands

### Starting/Stopping

```bash
./lakehouse start spark --version 4.0
./lakehouse start spark --version 4.1

./lakehouse stop spark --version 4.0
./lakehouse stop spark --version 4.1
```

### Logs

```bash
./lakehouse logs spark-master --version 4.0
./lakehouse logs spark-master --version 4.1

./lakehouse logs spark-worker --version 4.0
./lakehouse logs spark-worker --version 4.1
```

### Consumer

```bash
./lakehouse consumer --version 4.0
./lakehouse consumer --version 4.1
```

## Submitting Jobs

### To Spark 4.0

```bash
# Via Docker
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://localhost:7077 \
  /scripts/my-job.py

# Local spark-submit (requires Java 17)
spark-submit --master spark://localhost:7077 scripts/my-job.py
```

### To Spark 4.1

```bash
# Via Docker
docker exec spark-master-41 /opt/spark/bin/spark-submit \
  --master spark://localhost:7078 \
  /scripts/my-job.py

# Local spark-submit (requires Java 21)
spark-submit --master spark://localhost:7078 scripts/my-job.py
```

## Version Differences

### Java Requirements

| Spark | Java Version |
|-------|--------------|
| 4.0.1 | Java 17 |
| 4.1.0 | Java 21 |

### Kafka Package Versions

| Spark | Kafka Package |
|-------|---------------|
| 4.0.1 | `org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1` |
| 4.1.0 | `org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.0` |

### API Changes

Spark 4.1 introduces some API changes from 4.0. Key differences:

```python
# Both versions - basic operations work the same
df = spark.read.parquet("path")
df.filter(df.col > 10).show()

# Check Spark version in code
print(spark.version)  # "4.0.1" or "4.1.0"
```

## A/B Testing Workflow

### 1. Prepare Test Data

```bash
./lakehouse testdata generate --days 7
./lakehouse testdata load
```

### 2. Run Job on Both Versions

```bash
# Run on 4.0
docker exec spark-master /opt/spark/bin/spark-submit \
  /scripts/examples/01-basics.py > results-4.0.txt 2>&1

# Run on 4.1
docker exec spark-master-41 /opt/spark/bin/spark-submit \
  /scripts/examples/01-basics.py > results-4.1.txt 2>&1

# Compare results
diff results-4.0.txt results-4.1.txt
```

### 3. Performance Comparison

```bash
# Time execution on 4.0
time docker exec spark-master /opt/spark/bin/spark-submit /scripts/benchmark.py

# Time execution on 4.1
time docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/benchmark.py
```

## Migration Testing

### Step 1: Run on 4.0

```bash
./lakehouse start spark --version 4.0
docker exec spark-master /opt/spark/bin/spark-submit /scripts/my-app.py
# Verify output
```

### Step 2: Run on 4.1

```bash
./lakehouse start spark --version 4.1
docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/my-app.py
# Verify output matches
```

### Step 3: Compare Iceberg Tables

Both versions write to the same Iceberg catalog, so you can verify table contents are identical.

## Docker Compose Files

| Version | File |
|---------|------|
| 4.0 | `docker-compose.yml` |
| 4.1 | `docker-compose-spark41.yml` |

Both share:
- Same config from `config/spark/spark-defaults.conf`
- Same JARs from `jars/`
- Same scripts from `scripts/`

## Resource Considerations

Running both versions requires more resources:
- **Memory**: Each cluster uses ~2-4GB
- **CPU**: Additional cores for second cluster
- **Ports**: 6 additional ports for second cluster

If resources are limited, stop one before starting the other:
```bash
./lakehouse stop spark --version 4.0
./lakehouse start spark --version 4.1
```

## See Also

- [CLI Reference](cli-reference.md)
- [Local Deployment](../deployment/local.md)
