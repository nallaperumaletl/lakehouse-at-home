# Architecture

Technical deep-dive into the lakehouse stack components, data flows, and design decisions.

## High-Level Overview

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                    QUERIES                                        │
│            Spark SQL  •  Time Travel  •  Dashboards  •  Reports                   │
└───────────────────────────────────────────────────────────────────────────────────┘
                                        ▲
                                        │
┌──────────────────────┐    ┌───────────────────────────────────────────────────────┐
│                      │    │                    COMPUTE: Spark 4.x                 │
│  STREAMING           │    │                                                       │
│                      │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  Kafka (:9092)       │───▶│  │   BRONZE    │─▶│   SILVER    │─▶│    GOLD     │   │
│  └─ events topic     │    │  │ (raw ingest)│  │  (cleaned)  │  │ (aggregated)│   │
│  └─ orders topic     │    │  └─────────────┘  └─────────────┘  └─────────────┘   │
│                      │    │                                                       │
│  Zookeeper (:2181)   │    │  Spark 4.0 (:7077, UI :8080)                         │
│                      │    │  Spark 4.1 (:7078, UI :8082)                         │
│  (direct to Spark,   │    └──────────────────────────┬────────────────────────────┘
│   not via catalog)   │                               │
└──────────────────────┘                               │ Iceberg API
                                                       ▼
                            ┌───────────────────────────────────────────────────────┐
                            │                 CATALOG: Iceberg Metadata             │
                            │                                                       │
                            │  PostgreSQL (:5432)          Unity Catalog (:8080)    │
                            │  └─ JDBC catalog             └─ REST catalog          │
                            │  └─ table schemas            └─ multi-engine access   │
                            │  └─ snapshots, partitions                             │
                            └──────────────────────────┬────────────────────────────┘
                                                       │
                                                       ▼
                            ┌───────────────────────────────────────────────────────┐
                            │               STORAGE: SeaweedFS (S3 API)             │
                            │                                                       │
                            │  s3://lakehouse/warehouse/                            │
                            │  ├── bronze/*.parquet                                 │
                            │  ├── silver/*.parquet                                 │
                            │  └── gold/*.parquet                                   │
                            │                                                       │
                            │  :8333 (S3-compatible object storage)                 │
                            └───────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. Kafka Feeds Directly to Spark

Kafka is **not** managed by the Iceberg catalog. It serves as an event bus that Spark Structured Streaming reads from directly:

```
Kafka Topics ──────▶ Spark Structured Streaming ──────▶ Iceberg Tables
   (events)              (direct connection)              (via catalog)
```

This is important because:
- Kafka topics have different semantics than Iceberg tables
- Kafka provides replay capability and event ordering
- Iceberg provides ACID transactions and time travel on stored data
- They serve complementary purposes (streaming vs. storage)

### 2. Catalog Manages Only Iceberg Tables

The catalog (PostgreSQL JDBC or Unity Catalog REST) stores **metadata only**:
- Table schemas and column definitions
- Partition specifications
- Snapshot history (for time travel)
- File manifests (pointers to Parquet files)

The catalog does **not** store:
- Actual data (that's in SeaweedFS)
- Kafka topic configurations
- Streaming state or checkpoints

### 3. All Data Lives in Object Storage

SeaweedFS (S3-compatible) stores all persistent data:
- Parquet data files (actual rows)
- Iceberg metadata files (JSON)
- Manifest files (Avro)
- Checkpoints (for streaming jobs)

---

## Component Deep Dive

### Apache Spark 4.x

**Role**: Distributed compute engine for both batch and streaming workloads.

#### Cluster Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Spark Cluster                            │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │   Spark Master   │    │   Spark Master   │               │
│  │   (Spark 4.0)    │    │   (Spark 4.1)    │               │
│  │   Port: 7077     │    │   Port: 7078     │               │
│  │   UI: 8080       │    │   UI: 8082       │               │
│  └────────┬─────────┘    └────────┬─────────┘               │
│           │                       │                          │
│     ┌─────┴─────┐           ┌─────┴─────┐                   │
│     ▼           ▼           ▼           ▼                   │
│  ┌──────┐   ┌──────┐    ┌──────┐   ┌──────┐                │
│  │Worker│   │Worker│    │Worker│   │Worker│                │
│  └──────┘   └──────┘    └──────┘   └──────┘                │
└─────────────────────────────────────────────────────────────┘
```

#### Key Features Used

| Feature | Purpose |
|---------|---------|
| Spark SQL | Structured queries with Iceberg extensions |
| Catalyst Optimizer | Query planning and optimization |
| Adaptive Query Execution | Runtime optimization |
| Structured Streaming | Real-time Kafka consumption |
| DataFrame API | Programmatic data manipulation |

#### Multi-Version Support

The stack supports running Spark 4.0 and 4.1 simultaneously:

| Version | Port | UI | Java | Use Case |
|---------|------|-----|------|----------|
| Spark 4.0.1 | 7077 | 8080 | 17 | Production workloads |
| Spark 4.1.0 | 7078 | 8082 | 21 | Testing new features |

---

### Apache Iceberg 1.10

**Role**: Table format providing ACID transactions on object storage.

#### How Iceberg Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Iceberg Table                             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Catalog Entry                       │   │
│  │  (PostgreSQL or Unity Catalog)                        │   │
│  │  └─ Points to: s3://lakehouse/warehouse/bronze/orders │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Metadata (metadata/*.json)               │   │
│  │  • Current snapshot ID                                │   │
│  │  • Schema (columns, types)                            │   │
│  │  • Partition spec                                     │   │
│  │  • Properties                                         │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Manifest List (snap-*.avro)              │   │
│  │  • List of manifest files for this snapshot           │   │
│  │  • Partition summaries                                │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Manifests (*.avro)                       │   │
│  │  • List of data files                                 │   │
│  │  • Column statistics (min/max/null count)            │   │
│  │  • File sizes                                         │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Data Files (data/*.parquet)              │   │
│  │  • Actual row data in Parquet format                  │   │
│  │  • Partitioned by date/hour/etc.                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Key Features

| Feature | Description |
|---------|-------------|
| **ACID Transactions** | Atomic commits, concurrent reads/writes |
| **Time Travel** | Query any historical snapshot |
| **Schema Evolution** | Add, rename, drop columns safely |
| **Partition Evolution** | Change partitioning without rewriting data |
| **Hidden Partitioning** | Partition without exposing in schema |
| **Snapshot Isolation** | Readers see consistent point-in-time view |

#### Time Travel Example

```python
# Query current data
spark.table("iceberg.bronze.orders").show()

# Query data as of specific snapshot
spark.read.option("snapshot-id", 123456789).table("iceberg.bronze.orders").show()

# Query data as of timestamp
spark.read.option("as-of-timestamp", "2025-01-15 00:00:00").table("iceberg.bronze.orders").show()

# List all snapshots
spark.sql("SELECT * FROM iceberg.bronze.orders.snapshots").show()
```

---

### Catalog Options

The stack supports two catalog implementations:

#### PostgreSQL JDBC Catalog (Default)

```
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL JDBC Catalog                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 iceberg_catalog DB                   │    │
│  │                                                      │    │
│  │  ┌─────────────────┐  ┌─────────────────────────┐   │    │
│  │  │ iceberg_tables  │  │ iceberg_namespace        │   │    │
│  │  │ ─────────────── │  │ ─────────────────────── │   │    │
│  │  │ catalog_name    │  │ catalog_name            │   │    │
│  │  │ table_namespace │  │ namespace               │   │    │
│  │  │ table_name      │  │ properties              │   │    │
│  │  │ metadata_location│  │                        │   │    │
│  │  └─────────────────┘  └─────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Connection: jdbc:postgresql://localhost:5432/iceberg_catalog│
└─────────────────────────────────────────────────────────────┘
```

**Spark Configuration:**
```properties
spark.sql.catalog.iceberg           org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.type      jdbc
spark.sql.catalog.iceberg.uri       jdbc:postgresql://localhost:5432/iceberg_catalog
spark.sql.catalog.iceberg.jdbc.user iceberg
spark.sql.catalog.iceberg.jdbc.password your_password
spark.sql.catalog.iceberg.warehouse s3a://lakehouse/warehouse
```

**Best for**: Simple setup, Spark-only environments

#### Unity Catalog OSS (Alternative)

```
┌─────────────────────────────────────────────────────────────┐
│                   Unity Catalog Server                       │
│                      (port 8080)                             │
│                                                              │
│  ┌────────────────────┐  ┌────────────────────┐             │
│  │   UC REST API      │  │  Iceberg REST API  │             │
│  │   /api/2.1/uc/     │  │  /api/2.1/uc/iceberg│            │
│  │   • catalogs       │  │  • namespaces      │             │
│  │   • schemas        │  │  • tables          │             │
│  │   • tables         │  │  • snapshots       │             │
│  └────────────────────┘  └────────────────────┘             │
│                              │                               │
│              ┌───────────────┴───────────────┐              │
│              │     Credential Vending        │              │
│              │  (S3 access via UC tokens)    │              │
│              └───────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

**Spark Configuration:**
```properties
spark.sql.catalog.iceberg           org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.catalog-impl org.apache.iceberg.rest.RESTCatalog
spark.sql.catalog.iceberg.uri       http://localhost:8080/api/2.1/unity-catalog/iceberg
spark.sql.catalog.iceberg.warehouse unity
spark.sql.catalog.iceberg.token     not_used
```

**Best for**: Multi-engine environments (DuckDB, Trino, Dremio), governance requirements

#### Comparison

| Feature | PostgreSQL JDBC | Unity Catalog |
|---------|-----------------|---------------|
| Protocol | Direct SQL | REST API |
| Client Engines | Spark only | Spark, DuckDB, Trino, Dremio |
| Auth | Database credentials | Token-based / OAuth |
| Governance | Manual | Built-in access control |
| Setup Complexity | Simpler | More flexible |
| External Access | Requires DB access | HTTP endpoint |

---

### Apache Kafka 3.6

**Role**: Event streaming platform for real-time data ingestion.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Kafka Cluster                           │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────────────────┐     │
│  │   Zookeeper     │    │        Kafka Broker          │     │
│  │   (port 2181)   │◀──▶│        (port 9092)           │     │
│  │                 │    │                              │     │
│  │  • Leader       │    │  ┌─────────────────────────┐│     │
│  │    election     │    │  │  Topic: events          ││     │
│  │  • Config       │    │  │  └─ Partition 0         ││     │
│  │    storage      │    │  │  └─ Partition 1         ││     │
│  │                 │    │  │  └─ Partition 2         ││     │
│  │                 │    │  └─────────────────────────┘│     │
│  │                 │    │                              │     │
│  │                 │    │  ┌─────────────────────────┐│     │
│  │                 │    │  │  Topic: orders          ││     │
│  │                 │    │  │  └─ Partition 0         ││     │
│  └─────────────────┘    │  └─────────────────────────┘│     │
│                         └─────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

#### Important: Kafka is NOT Catalog-Managed

Kafka topics are separate from the Iceberg catalog:

| Kafka | Iceberg |
|-------|---------|
| Event log (append-only) | Table format (mutable) |
| Replay from offset | Time travel via snapshots |
| Consumer groups | Snapshot isolation |
| Partitioned by key | Partitioned by column |
| Retention-based | Versioned forever |

**Data Flow Pattern:**
```
Producer ──▶ Kafka Topic ──▶ Spark Streaming ──▶ Iceberg Table
                                   │
                                   │ (checkpoints for
                                   │  exactly-once)
                                   ▼
                              /tmp/checkpoints/
```

---

### Apache Airflow 3.x

**Role**: Workflow orchestration for scheduled Spark jobs and Iceberg maintenance.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Airflow (port 8085)                     │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   API Server    │  │    Scheduler    │  │  Triggerer  │ │
│  │  (webserver)    │  │   (DAG runs)    │  │  (sensors)  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│           │                   │                    │        │
│           └───────────────────┴────────────────────┘        │
│                               │                              │
│                    docker exec spark-master-41               │
│                          spark-submit                        │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │   Spark Cluster     │
                    │   (runs the jobs)   │
                    └─────────────────────┘
```

#### How Airflow Executes Spark Jobs

Airflow runs in its own container and executes Spark jobs via `docker exec`:

```
Airflow Scheduler
       │
       │ BashOperator
       ▼
docker exec spark-master-41 spark-submit /scripts/pipelines/pipeline_spark41.py
       │
       │ (job runs in Spark container with Java 21)
       ▼
   Iceberg Tables
```

This pattern means:
- Airflow schedules and monitors, Spark executes
- Jobs use Spark container's JVM (Java 21 for Spark 4.1)
- Airflow container only needs Java 17 for its own operations

#### Included DAGs

| DAG | Schedule | Purpose |
|-----|----------|---------|
| `lakehouse_medallion_pipeline` | Daily | Bronze → Silver → Gold pipeline |
| `iceberg_maintenance` | Daily 3 AM | Expire snapshots, remove orphans, compact files |
| `iceberg_compact_on_demand` | Manual | On-demand table compaction |

#### Airflow 3.x Notes

Airflow 3.x has breaking changes from 2.x:
- `webserver` command → `api-server`
- `schedule_interval` → `schedule`
- Operators moved to `airflow.providers.standard.*`
- Health endpoint: `/api/v2/monitor/health`

See [Airflow Guide](guides/airflow.md) for details.

---

### SeaweedFS

**Role**: S3-compatible object storage for all persistent data.

#### Storage Layout

```
s3://lakehouse/
├── warehouse/                      # Iceberg warehouse root
│   ├── bronze/                     # Bronze layer
│   │   └── orders/
│   │       ├── metadata/
│   │       │   ├── v1.metadata.json
│   │       │   ├── v2.metadata.json
│   │       │   ├── snap-1234.avro
│   │       │   └── snap-5678.avro
│   │       └── data/
│   │           ├── date=2025-01-15/
│   │           │   ├── part-00000-*.parquet
│   │           │   └── part-00001-*.parquet
│   │           └── date=2025-01-16/
│   │               └── part-00000-*.parquet
│   ├── silver/                     # Silver layer
│   │   └── orders_cleaned/
│   │       ├── metadata/
│   │       └── data/
│   └── gold/                       # Gold layer
│       └── daily_metrics/
│           ├── metadata/
│           └── data/
└── checkpoints/                    # Streaming checkpoints
    └── orders_streaming/
        ├── offsets/
        ├── commits/
        └── state/
```

#### Why SeaweedFS?

| Feature | Benefit |
|---------|---------|
| Single binary | Easy deployment |
| S3-compatible | Works with Spark/Iceberg out of the box |
| No cloud dependency | Fully local development |
| Scalable | Add volumes as needed |
| Fast | Optimized for small files |

---

## Data Flows

### Batch Processing Flow

```
┌──────────────┐    ┌─────────────────────────────────────────────────────┐
│              │    │                   Spark Driver                       │
│  Source      │    │                                                      │
│  Files       │───▶│  1. spark.read.parquet("/data/orders/*.parquet")    │
│  (CSV/JSON/  │    │                                                      │
│   Parquet)   │    │  2. df.filter(...).withColumn(...)                  │
│              │    │                                                      │
└──────────────┘    │  3. df.writeTo("iceberg.bronze.orders").append()    │
                    │                    │                                 │
                    └────────────────────┼─────────────────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              Iceberg Commit                          │
                    │                                                      │
                    │  4. Write Parquet files to SeaweedFS                │
                    │  5. Create manifest files                           │
                    │  6. Update catalog metadata (atomic commit)         │
                    │                                                      │
                    └─────────────────────────────────────────────────────┘
```

### Streaming Flow

```
┌──────────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│              │    │              │    │      Spark Structured Streaming │
│  Producers   │───▶│    Kafka     │───▶│                                 │
│  (events)    │    │   Broker     │    │  1. readStream.format("kafka")  │
│              │    │              │    │     .option("subscribe","orders")│
└──────────────┘    └──────────────┘    │                                 │
                                        │  2. Parse JSON, transform       │
                                        │                                 │
                                        │  3. writeStream.format("iceberg")│
                                        │     .option("checkpointLocation")│
                                        │                                 │
                                        └────────────────┬────────────────┘
                                                         │
                         ┌───────────────────────────────┼────────────────┐
                         │                               │                │
                         ▼                               ▼                ▼
                    ┌─────────┐                   ┌─────────────┐  ┌───────────┐
                    │Checkpoint│                  │  Iceberg    │  │ SeaweedFS │
                    │  Files   │                  │  Catalog    │  │  (data)   │
                    └─────────┘                   └─────────────┘  └───────────┘
```

### Query Flow

```
┌──────────────┐
│  User Query  │
│              │
│  SELECT *    │
│  FROM orders │
│  WHERE ...   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                      Spark SQL Engine                         │
│                                                               │
│  1. Parse SQL                                                 │
│  2. Look up table in Iceberg catalog (PostgreSQL/Unity)      │
│  3. Get current snapshot metadata                             │
│  4. Read manifest files (file pruning based on predicates)   │
│  5. Generate scan plan (partition pruning)                   │
│                                                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Distributed Scan                           │
│                                                               │
│  6. Workers read Parquet files from SeaweedFS in parallel    │
│  7. Apply column pruning (read only needed columns)          │
│  8. Apply row-level filters                                   │
│  9. Aggregate results                                         │
│                                                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │   Results   │
                        └─────────────┘
```

---

## Medallion Architecture

The stack follows the medallion (multi-hop) architecture pattern:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     BRONZE      │    │     SILVER      │    │      GOLD       │
│  (Raw Ingest)   │───▶│   (Cleaned)     │───▶│  (Aggregated)   │
│                 │    │                 │    │                 │
│ • Raw events    │    │ • Deduplicated  │    │ • Daily metrics │
│ • All columns   │    │ • Validated     │    │ • Aggregations  │
│ • No transforms │    │ • Type-casted   │    │ • Joined data   │
│                 │    │ • Standardized  │    │ • Business KPIs │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
iceberg.bronze.*        iceberg.silver.*       iceberg.gold.*
```

### Layer Details

| Layer | Namespace | Purpose | Consumers |
|-------|-----------|---------|-----------|
| Bronze | `iceberg.bronze.*` | Raw data preservation | Data engineers |
| Silver | `iceberg.silver.*` | Cleaned, validated data | Analysts, data scientists |
| Gold | `iceberg.gold.*` | Business-ready aggregates | BI tools, dashboards |

### Example Pipeline

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as f

spark = SparkSession.builder.appName("MedallionPipeline").getOrCreate()

# ============================================================
# BRONZE: Raw ingestion (preserve everything)
# ============================================================
bronze_df = spark.read.json("/data/raw/orders/")
bronze_df.writeTo("iceberg.bronze.orders").createOrReplace()

# ============================================================
# SILVER: Clean and validate
# ============================================================
silver_df = spark.table("iceberg.bronze.orders") \
    .filter(f.col("order_id").isNotNull()) \
    .dropDuplicates(["order_id"]) \
    .withColumn("total", f.col("total").cast("decimal(10,2)")) \
    .withColumn("created_at", f.to_timestamp("created_at"))

silver_df.writeTo("iceberg.silver.orders").createOrReplace()

# ============================================================
# GOLD: Aggregate for business use
# ============================================================
gold_df = spark.table("iceberg.silver.orders") \
    .groupBy(f.date_trunc("day", "created_at").alias("date")) \
    .agg(
        f.count("*").alias("order_count"),
        f.sum("total").alias("revenue"),
        f.avg("total").alias("avg_order_value")
    )

gold_df.writeTo("iceberg.gold.daily_sales").createOrReplace()
```

---

## Network Architecture

All services use `network_mode: host` for simplicity:

```
┌─────────────────────────────────────────────────────────────┐
│                     Host Network                             │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   Services                           │    │
│  │                                                      │    │
│  │  PostgreSQL ─────────────────────────────── :5432   │    │
│  │  SeaweedFS ──────────────────────────────── :8333   │    │
│  │  Spark Master 4.0 ───────────────────────── :7077   │    │
│  │  Spark Master 4.1 ───────────────────────── :7078   │    │
│  │  Spark UI 4.0 ───────────────────────────── :8080   │    │
│  │  Spark UI 4.1 ───────────────────────────── :8082   │    │
│  │  Kafka ──────────────────────────────────── :9092   │    │
│  │  Zookeeper ──────────────────────────────── :2181   │    │
│  │  Airflow (optional) ─────────────────────── :8085   │    │
│  │  Unity Catalog (optional) ───────────────── :8080   │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Note: Unity Catalog and Spark 4.0 UI both use :8080.       │
│  Run only one at a time, or reconfigure ports.              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Version Compatibility Matrix

Critical version combinations for stability:

| Component | Version | Notes |
|-----------|---------|-------|
| Spark | 4.0.1 / 4.1.0 | Scala 2.13 builds |
| Iceberg | 1.10.0 | `iceberg-spark-runtime-4.0_2.13` |
| Hadoop AWS | 3.4.1 | S3A filesystem |
| AWS SDK v2 | **2.24.6** | **Exact version required** |
| Kafka | 3.6.1 | Confluent images |
| PostgreSQL | 16 | Iceberg catalog |
| Airflow | 3.1.6 | Python 3.12, Java 17 |
| Unity Catalog | 0.3.1 | Optional REST catalog |

**Critical**: AWS SDK version must be exactly 2.24.6 for Hadoop 3.4.1 compatibility. Other versions cause S3A authentication failures.

---

## Local File Structure

```
lakehouse-stack/
├── config/
│   ├── spark/
│   │   ├── spark-defaults.conf       # Active config (from .example)
│   │   ├── spark-defaults.conf.example
│   │   └── spark-defaults-uc.conf.example
│   ├── airflow/
│   │   └── setup_connections.sh       # Airflow connection setup
│   └── unity-catalog/
│       └── server.properties          # Unity Catalog config
├── dags/                              # Airflow DAG definitions
│   ├── lakehouse_medallion_pipeline.py
│   └── iceberg_maintenance.py
├── data/                              # Generated test data
├── docker/
│   └── airflow/
│       └── Dockerfile                 # Custom Airflow image
├── docker-compose.yml                 # Spark 4.0
├── docker-compose-spark41.yml         # Spark 4.1
├── docker-compose-kafka.yml           # Kafka + Zookeeper
├── docker-compose-airflow.yml         # Airflow orchestration
├── docker-compose-unity-catalog.yml   # Unity Catalog OSS
├── jars/                              # Spark dependencies (~860MB)
│   ├── iceberg-spark-runtime-*.jar
│   ├── hadoop-aws-*.jar
│   ├── aws-java-sdk-bundle-*.jar
│   └── postgresql-*.jar
├── scripts/                           # PySpark examples
├── tests/                             # pytest suite
```

---

## See Also

- [Configuration Guide](getting-started/configuration.md)
- [Streaming Guide](guides/streaming.md)
- [Airflow Guide](guides/airflow.md)
- [Unity Catalog Guide](guides/unity-catalog.md)
- [Multi-Version Spark](guides/multi-version.md)
