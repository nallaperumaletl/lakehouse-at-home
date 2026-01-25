# PySpark: Before and After Spark Declarative Pipelines

## Before (Imperative)

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as f

spark = SparkSession.builder.appName("OrdersPipeline").getOrCreate()

# Bronze layer
def load_orders():
    df = spark.read.parquet("/data/orders.parquet")
    df = df.withColumn("event_ts", f.to_timestamp("ts"))
    df.write.mode("overwrite").saveAsTable("bronze_orders")

# Silver layer - must call AFTER load_orders()
def enrich_orders():
    orders = spark.table("bronze_orders")
    locations = spark.table("dim_locations")

    enriched = orders.join(locations, "location_id", "left")
    enriched = enriched.withColumn("hour", f.hour("event_ts"))

    enriched.write.mode("overwrite").saveAsTable("silver_orders")

# Gold layer - must call AFTER enrich_orders()
def daily_metrics():
    orders = spark.table("silver_orders")

    metrics = orders.groupBy("order_date", "location_id").agg(
        f.count("order_id").alias("order_count"),
        f.sum("total").alias("revenue"),
    )

    metrics.write.mode("overwrite").saveAsTable("gold_daily_metrics")

# Manual execution in correct order
if __name__ == "__main__":
    load_orders()
    enrich_orders()
    daily_metrics()
    spark.stop()
```

---

## After (Spark Declarative Pipelines)

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as f

# Bronze layer
@dp.materialized_view
def bronze_orders():
    df = spark.read.parquet("/data/orders.parquet")
    return df.withColumn("event_ts", f.to_timestamp("ts"))

# Silver layer - dependencies inferred from spark.table()
@dp.materialized_view
def silver_orders():
    orders = spark.table("bronze_orders")
    locations = spark.table("dim_locations")

    enriched = orders.join(locations, "location_id", "left")
    return enriched.withColumn("hour", f.hour("event_ts"))

# Gold layer
@dp.materialized_view
def gold_daily_metrics():
    orders = spark.table("silver_orders")

    return orders.groupBy("order_date", "location_id").agg(
        f.count("order_id").alias("order_count"),
        f.sum("total").alias("revenue"),
    )

# Run with: spark-pipelines run
```

---

## Streaming with @dp.table

### Before (Imperative)

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as f

spark = SparkSession.builder.appName("StreamingPipeline").getOrCreate()

def stream_orders():
    df = (spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "orders")
        .load()
    )

    parsed = df.select(
        f.from_json(f.col("value").cast("string"), schema).alias("data")
    ).select("data.*")

    query = (parsed.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", "/checkpoints/orders")
        .toTable("bronze_orders_stream")
    )

    query.awaitTermination()

if __name__ == "__main__":
    stream_orders()
```

### After (SDP)

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as f

# @dp.table creates a streaming table with incremental processing
@dp.table
def bronze_orders_stream():
    df = (spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "orders")
        .load()
    )

    return df.select(
        f.from_json(f.col("value").cast("string"), schema).alias("data")
    ).select("data.*")

# Downstream streaming table reads incrementally
@dp.table
def silver_orders_stream():
    return (spark.readStream.table("bronze_orders_stream")
        .withColumn("processed_at", f.current_timestamp())
        .filter(f.col("order_id").isNotNull())
    )

# Run with: spark-pipelines run
```

---

## Key Differences

| Aspect | Imperative | SDP |
|--------|-----------|-----|
| Execution order | Manual | Automatic |
| Writing data | Explicit `.write()` | Framework handles it |
| Dependencies | Implicit | Inferred from `spark.table()` |
| Function returns | Nothing | DataFrame |
| Streaming | Manual `writeStream` + checkpoints | Just use `readStream`, framework handles the rest |
| Running | `python script.py` | `spark-pipelines run` |

---

## SDP Decorators

| Decorator | Use Case |
|-----------|----------|
| `@dp.materialized_view` | Batch tables, recomputed on each run |
| `@dp.table` | Streaming tables with incremental processing |
| `@dp.temporary_view` | Intermediate results, not persisted |

---

## SDP Rules

- Decorated functions **must return a DataFrame**
- Never use `collect()`, `count()`, `save()`, or `write()` inside decorated functions
- Reference other datasets with `spark.table("name")` or `spark.readStream.table("name")`
- The framework determines execution order from table references

---

## References

- [Spark Declarative Pipelines Programming Guide](https://spark.apache.org/docs/latest/declarative-pipelines-programming-guide.html)
