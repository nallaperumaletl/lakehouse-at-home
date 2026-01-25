# Data Pipelines Guide

This guide covers building data pipelines with the Lakehouse Stack, comparing imperative (Spark 4.0) and declarative (Spark 4.1) approaches.

## Quick Start

```bash
# Start services and load test data
./lakehouse start all
./lakehouse testdata generate --days 90
./lakehouse testdata load

# Run imperative pipeline (Spark 4.0)
docker exec spark-master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --conf spark.sql.iceberg.vectorization.enabled=false \
    /scripts/pipelines/pipeline_spark40.py

# Run declarative pipeline (Spark 4.1)
docker exec spark-master-41 /opt/spark/bin/spark-submit \
    /scripts/pipelines/pipeline_spark41.py
```

## Pipeline Scripts

| Script | Approach | Description |
|--------|----------|-------------|
| `scripts/pipelines/pipeline_spark40.py` | Imperative | Traditional PySpark with explicit function calls |
| `scripts/pipelines/pipeline_spark41.py` | Declarative | SDP-style decorators with auto dependency resolution |
| `scripts/pipelines/pipeline_sdp.py` | Production SDP | For use with `spark-pipelines` CLI |

## Workshop Notebooks

Interactive Jupyter notebooks for learning:

| Notebook | Approach |
|----------|----------|
| `notebooks/spark40_imperative_pipeline.ipynb` | Traditional PySpark |
| `notebooks/spark41_declarative_pipeline.ipynb` | Spark Declarative Pipelines |

### Running the Notebooks

Start JupyterLab using Docker:

```bash
# Start Jupyter (requires Spark to be running)
docker compose -f docker-compose-notebooks.yml up -d

# Get the access token
docker logs jupyter 2>&1 | grep token

# Open http://localhost:8889 and enter the token
```

Stop when done:

```bash
docker compose -f docker-compose-notebooks.yml down
```

**Tip:** Open both notebooks side-by-side in JupyterLab to compare approaches.

## Medallion Architecture

Both pipelines implement the medallion architecture:

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  BRONZE  │─────▶│  SILVER  │─────▶│   GOLD   │
│  (Raw)   │      │ (Cleaned)│      │(Business)│
└──────────┘      └──────────┘      └──────────┘
```

### Tables Created

| Layer | Table | Description |
|-------|-------|-------------|
| Bronze | `bronze.dim_brands` | Virtual restaurant brands |
| Bronze | `bronze.dim_locations` | Delivery markets |
| Bronze | `bronze.orders` | Raw order lifecycle events |
| Silver | `silver.orders_enriched` | Cleaned with parsed JSON |
| Silver | `silver.order_lifecycle` | One row per order with durations |
| Gold | `gold.hourly_metrics` | Hourly order aggregations |
| Gold | `gold.delivery_performance` | Delivery time statistics |
| Gold | `gold.brand_summary` | Brand-level metrics |

## Imperative vs Declarative

### Imperative Approach (Spark 4.0)

Functions explicitly read, transform, and write data:

```python
def create_orders_enriched(spark):
    orders = spark.table("iceberg.bronze.orders")
    # ... transformations ...
    enriched.write.mode("overwrite").saveAsTable("iceberg.silver.orders_enriched")

# You call functions in order
create_orders_enriched(spark)
```

**Pros:** Full control, familiar patterns, easy debugging
**Cons:** Manual dependency management, verbose

### Declarative Approach (Spark 4.1)

Functions only return DataFrames; framework handles execution:

```python
@dp.materialized_view(name="silver.orders_enriched")
def orders_enriched():
    orders = spark.table("iceberg.bronze.orders")  # Creates dependency
    # ... transformations ...
    return enriched  # No write statement!

# Framework runs everything
pipeline.run()
```

**Pros:** Auto dependency resolution, less boilerplate, CLI integration
**Cons:** Framework lock-in, less control

## Production Usage

### With Spark Declarative Pipelines CLI

```bash
# Validate without running
spark-pipelines dry-run --spec scripts/pipelines/spark-pipeline.yml

# Execute pipeline
spark-pipelines run --spec scripts/pipelines/spark-pipeline.yml
```

### Configuration File

`scripts/pipelines/spark-pipeline.yml`:

```yaml
name: lakehouse_pipeline
libraries:
  - file: pipeline_sdp.py
catalog: iceberg
database: bronze
storage: /tmp/lakehouse-checkpoint
```

## Querying Results

After running a pipeline, query the gold tables:

```python
# Top brands by revenue
spark.table("iceberg.gold.brand_summary") \
    .orderBy(desc("total_revenue")) \
    .show(10)

# Delivery performance by city
spark.table("iceberg.gold.delivery_performance") \
    .groupBy("city_name") \
    .agg(avg("avg_total_time_min").alias("avg_time")) \
    .show()
```

## Troubleshooting

### OOM on Spark 4.0

Large datasets may cause OOM with Arrow vectorization:

```bash
# Add these flags
docker exec spark-master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --conf spark.sql.iceberg.vectorization.enabled=false \
    /scripts/pipelines/pipeline_spark40.py
```

### Table Already Exists

Pipelines use `mode("overwrite")` by default. To append instead:

```python
df.write.mode("append").saveAsTable("iceberg.silver.orders_enriched")
```

### Dependency Resolution Issues

In declarative pipelines, dependencies are inferred from `spark.table()` calls. Ensure you use the full table name:

```python
# Correct - dependency detected
orders = spark.table("iceberg.bronze.orders")

# Wrong - dependency not detected
orders = spark.read.table("bronze.orders")
```

## See Also

- [Test Data Guide](test-data.md) - Generating sample data
- [Multi-Version Spark](multi-version.md) - Running 4.0 and 4.1 together
- [Streaming Guide](streaming.md) - Real-time pipelines with Kafka
