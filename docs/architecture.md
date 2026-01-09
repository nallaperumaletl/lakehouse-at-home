# Architecture

Technical overview of the lakehouse stack components and data flow.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Applications                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Spark Jobs   │  │   Python     │  │   BI Tools           │  │
│  │ (Batch/Stream│  │   Scripts    │  │   (Superset, etc.)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼───────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Apache Spark 4.x                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Spark SQL Engine                       │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │   │
│  │  │  Catalyst  │  │  Tungsten  │  │ Adaptive Query Exec │  │   │
│  │  │  Optimizer │  │  Engine    │  │                    │  │   │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Apache Iceberg 1.10                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Table Format Layer                     │   │
│  │  • ACID Transactions    • Schema Evolution               │   │
│  │  • Time Travel          • Partition Evolution            │   │
│  │  • Hidden Partitioning  • Snapshot Isolation             │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│     PostgreSQL 16         │   │        SeaweedFS              │
│  ┌─────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │  Iceberg Catalog    │  │   │  │    S3-Compatible API    │  │
│  │  • Table metadata   │  │   │  │    • Parquet files      │  │
│  │  • Schema versions  │  │   │  │    • Manifest files     │  │
│  │  • Snapshot refs    │  │   │  │    • Data files         │  │
│  └─────────────────────┘  │   │  └─────────────────────────┘  │
└───────────────────────────┘   └───────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Apache Kafka 3.6                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Event Streaming                        │   │
│  │  • Real-time ingestion    • Topic partitioning           │   │
│  │  • Consumer groups        • Exactly-once semantics       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### Apache Spark

**Role**: Distributed compute engine for batch and streaming.

| Component | Port | Purpose |
|-----------|------|---------|
| Master | 7077/7078 | Cluster coordination |
| Workers | - | Task execution |
| Driver | 4040 | Job UI |
| History Server | 18080 | Completed job logs |

**Key Features Used**:
- Spark SQL for structured queries
- Structured Streaming for real-time
- Adaptive Query Execution for optimization

### Apache Iceberg

**Role**: Table format providing ACID transactions on object storage.

**Catalog Type**: JDBC (PostgreSQL)

```
iceberg.bronze.*   # Raw data layer
iceberg.silver.*   # Cleaned/transformed
iceberg.gold.*     # Business-ready
```

**Key Features**:
- **Snapshot isolation**: Concurrent reads/writes
- **Time travel**: Query historical data
- **Schema evolution**: Add/rename columns safely
- **Hidden partitioning**: Partition without exposing in schema

### PostgreSQL

**Role**: Metadata catalog for Iceberg tables.

Stores:
- Table definitions
- Schema versions
- Snapshot metadata
- Partition specs

### SeaweedFS

**Role**: S3-compatible object storage.

Stores:
- Parquet data files
- Iceberg manifest files
- Iceberg metadata files

**Why SeaweedFS**:
- Simple deployment (single binary)
- S3-compatible API
- No cloud dependency

### Apache Kafka

**Role**: Event streaming platform.

| Component | Port | Purpose |
|-----------|------|---------|
| Broker | 9092 | Message handling |
| Zookeeper | 2181 | Cluster coordination |

## Data Flow

### Batch Processing

```
Source Data → Spark Read → Transform → Iceberg Write → SeaweedFS
                                           ↓
                                      PostgreSQL
                                    (metadata update)
```

### Stream Processing

```
Kafka Topic → Spark Streaming → Transform → Iceberg Write
                    ↓
              Checkpointing
            (exactly-once)
```

### Query Flow

```
User Query → Spark SQL → Iceberg Catalog (PostgreSQL)
                              ↓
                        File Planning
                              ↓
                        SeaweedFS Read
                              ↓
                        Result Set
```

## Medallion Architecture

The stack follows the medallion (multi-hop) architecture:

| Layer | Namespace | Purpose |
|-------|-----------|---------|
| Bronze | `iceberg.bronze.*` | Raw ingested data |
| Silver | `iceberg.silver.*` | Cleaned, validated |
| Gold | `iceberg.gold.*` | Business aggregates |

### Example Pipeline

```python
# Bronze: Raw events
spark.read.json("kafka_events") \
    .write.format("iceberg") \
    .save("iceberg.bronze.events")

# Silver: Cleaned events
spark.read.table("iceberg.bronze.events") \
    .filter(col("event_id").isNotNull()) \
    .dropDuplicates(["event_id"]) \
    .write.format("iceberg") \
    .save("iceberg.silver.events")

# Gold: Aggregated metrics
spark.read.table("iceberg.silver.events") \
    .groupBy("date", "event_type") \
    .count() \
    .write.format("iceberg") \
    .save("iceberg.gold.daily_events")
```

## Network Architecture

```
┌─────────────────────────────────────────────┐
│              Host Network                    │
│                                              │
│  PostgreSQL ──────────────────── :5432      │
│  SeaweedFS ───────────────────── :8333      │
│  Spark Master 4.0 ────────────── :7077      │
│  Spark Master 4.1 ────────────── :7078      │
│  Spark UI 4.0 ────────────────── :8080      │
│  Spark UI 4.1 ────────────────── :8082      │
│  Kafka ───────────────────────── :9092      │
│  Zookeeper ───────────────────── :2181      │
│                                              │
└─────────────────────────────────────────────┘
```

All Docker containers use `network_mode: host`, sharing the host's network namespace.

## Storage Layout

### Iceberg Table Structure

```
s3://lakehouse/warehouse/
└── bronze.db/
    └── orders/
        ├── metadata/
        │   ├── v1.metadata.json
        │   ├── v2.metadata.json
        │   └── snap-*.avro
        └── data/
            ├── part-00000-*.parquet
            ├── part-00001-*.parquet
            └── ...
```

### Local File Structure

```
lakehouse-stack/
├── config/
│   └── spark/
│       └── spark-defaults.conf
├── data/                    # Generated test data
├── jars/                    # Spark dependencies (~860MB)
├── scripts/                 # PySpark examples
└── terraform/               # AWS infrastructure
```

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Spark | 4.0.1, 4.1.0 | Scala 2.13 |
| Iceberg | 1.10.0 | For Spark 4.x |
| Hadoop AWS | 3.4.1 | S3A filesystem |
| AWS SDK v2 | 2.24.6 | **Exact version required** |
| Kafka | 3.6.1 | - |
| PostgreSQL | 16 | - |

**Critical**: AWS SDK version must be exactly 2.24.6 for Hadoop 3.4.1 compatibility.

## See Also

- [Configuration](getting-started/configuration.md)
- [Local Deployment](deployment/local.md)
- [AWS Deployment](deployment/aws.md)
