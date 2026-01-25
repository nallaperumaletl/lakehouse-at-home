#!/usr/bin/env python3
"""
Spark 4.0 Imperative Pipeline
=============================

Traditional PySpark pipeline using explicit function calls and write statements.
This is the "classic" approach that works with any Spark version.

Usage:
    # On Spark 4.0 cluster (requires master URL and vectorization disabled for large datasets)
    docker exec spark-master /opt/spark/bin/spark-submit \\
        --master spark://spark-master:7077 \\
        --conf spark.sql.iceberg.vectorization.enabled=false \\
        /scripts/pipeline_spark40.py

    # On Spark 4.1 cluster (also works, no special flags needed)
    docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/pipeline_spark41.py
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
)
from typing import Dict


def create_spark_session() -> SparkSession:
    """Create SparkSession with Iceberg catalog."""
    return SparkSession.builder \
        .appName("Pipeline_Spark40_Imperative") \
        .getOrCreate()


def get_table_count(spark: SparkSession, table: str) -> int:
    """Get row count from Iceberg metadata (avoids full scan)."""
    try:
        # Use Iceberg snapshot metadata for fast count
        result = spark.sql(f"SELECT COUNT(*) as cnt FROM {table}").collect()
        return result[0]['cnt']
    except Exception:
        return -1


# =============================================================================
# BRONZE LAYER - Raw Data Ingestion
# =============================================================================

def load_dim_categories(spark: SparkSession) -> None:
    """Load categories dimension table."""
    df = spark.read.parquet("/data/dimensions/categories.parquet")
    df.write.mode("overwrite").saveAsTable("iceberg.bronze.dim_categories")


def load_dim_brands(spark: SparkSession) -> None:
    """Load brands dimension table."""
    df = spark.read.parquet("/data/dimensions/brands.parquet")
    df.write.mode("overwrite").saveAsTable("iceberg.bronze.dim_brands")


def load_dim_items(spark: SparkSession) -> None:
    """Load items dimension table."""
    df = spark.read.parquet("/data/dimensions/items.parquet")
    df.write.mode("overwrite").saveAsTable("iceberg.bronze.dim_items")


def load_dim_locations(spark: SparkSession) -> None:
    """Load locations dimension table."""
    df = spark.read.parquet("/data/dimensions/locations.parquet")
    df.write.mode("overwrite").saveAsTable("iceberg.bronze.dim_locations")


def load_orders(spark: SparkSession) -> None:
    """Load order events with timestamp parsing."""
    df = spark.read.parquet("/data/events/orders_90d.parquet")
    df = df.withColumn(
        "event_timestamp",
        f.to_timestamp(f.regexp_replace("ts", "T", " "))
    )
    df.write.mode("overwrite").saveAsTable("iceberg.bronze.orders")


# =============================================================================
# SILVER LAYER - Cleaned and Enriched
# =============================================================================

def create_orders_enriched(spark: SparkSession) -> None:
    """Create enriched orders with parsed JSON and time features."""
    orders = spark.table("iceberg.bronze.orders")
    locations = spark.table("iceberg.bronze.dim_locations")

    # Filter nulls
    cleaned = orders.filter(
        f.col("event_id").isNotNull() &
        f.col("order_id").isNotNull() &
        f.col("event_timestamp").isNotNull()
    )

    # Parse JSON body
    body_schema = StructType([
        StructField("brand_id", IntegerType(), True),
        StructField("item_ids", StringType(), True),
        StructField("total", DoubleType(), True),
        StructField("lat", DoubleType(), True),
        StructField("lng", DoubleType(), True),
        StructField("driver_id", StringType(), True),
    ])

    enriched = cleaned.withColumn("body_parsed", f.from_json("body", body_schema))

    # Extract fields
    enriched = enriched.select(
        "event_id", "event_type", "event_timestamp", "ts", "ts_seconds",
        "order_id", "location_id", "sequence", "body",
        f.col("body_parsed.brand_id").alias("brand_id"),
        f.col("body_parsed.total").alias("order_total"),
        f.col("body_parsed.lat").alias("latitude"),
        f.col("body_parsed.lng").alias("longitude"),
        f.col("body_parsed.driver_id").alias("driver_id"),
    )

    # Add time features
    enriched = enriched.withColumns({
        "event_hour": f.hour("event_timestamp"),
        "event_day_of_week": f.dayofweek("event_timestamp"),
        "is_weekend": f.when(f.dayofweek("event_timestamp").isin(1, 7), True).otherwise(False),
        "event_date": f.to_date("event_timestamp"),
    })

    # Join with locations
    locations_lookup = locations.select(
        f.col("id").alias("location_id"),
        f.col("city").alias("city_name"),
    )

    enriched = enriched.join(f.broadcast(locations_lookup), on="location_id", how="left")

    enriched.write.mode("overwrite").saveAsTable("iceberg.silver.orders_enriched")


def create_order_lifecycle(spark: SparkSession) -> None:
    """Create pivoted order lifecycle with duration metrics."""
    orders = spark.table("iceberg.silver.orders_enriched")

    # Pivot events to columns
    lifecycle = orders.groupBy("order_id", "location_id", "city_name").pivot(
        "event_type",
        ["order_created", "kitchen_started", "kitchen_finished", "order_ready",
         "driver_arrived", "driver_picked_up", "delivered"]
    ).agg(f.min("event_timestamp").alias("ts"))

    # Rename columns
    lifecycle = lifecycle.select(
        "order_id", "location_id", "city_name",
        f.col("order_created").alias("created_at"),
        f.col("kitchen_started").alias("kitchen_started_at"),
        f.col("kitchen_finished").alias("kitchen_finished_at"),
        f.col("order_ready").alias("order_ready_at"),
        f.col("driver_arrived").alias("driver_arrived_at"),
        f.col("driver_picked_up").alias("pickup_at"),
        f.col("delivered").alias("delivered_at"),
    )

    # Calculate durations
    lifecycle = lifecycle.withColumns({
        "kitchen_duration_min": (f.unix_timestamp("kitchen_finished_at") - f.unix_timestamp("kitchen_started_at")) / 60,
        "delivery_duration_min": (f.unix_timestamp("delivered_at") - f.unix_timestamp("pickup_at")) / 60,
        "total_duration_min": (f.unix_timestamp("delivered_at") - f.unix_timestamp("created_at")) / 60,
    })

    # Filter to completed orders
    lifecycle = lifecycle.filter(f.col("delivered_at").isNotNull())

    lifecycle.write.mode("overwrite").saveAsTable("iceberg.silver.order_lifecycle")


# =============================================================================
# GOLD LAYER - Business Aggregations
# =============================================================================

def create_hourly_metrics(spark: SparkSession) -> None:
    """Create hourly order metrics by location."""
    orders = spark.table("iceberg.silver.orders_enriched")

    metrics = orders.filter(f.col("event_type") == "order_created").groupBy(
        "event_date", "event_hour", "location_id", "city_name"
    ).agg(
        f.count("order_id").alias("order_count"),
        f.sum("order_total").alias("total_revenue"),
        f.avg("order_total").alias("avg_order_value"),
        f.countDistinct("brand_id").alias("unique_brands"),
    )

    metrics.write.mode("overwrite").saveAsTable("iceberg.gold.hourly_metrics")


def create_delivery_performance(spark: SparkSession) -> None:
    """Create delivery performance metrics by date and location."""
    lifecycle = spark.table("iceberg.silver.order_lifecycle")

    perf = lifecycle.groupBy(
        f.to_date("created_at").alias("order_date"),
        "location_id", "city_name"
    ).agg(
        f.count("order_id").alias("completed_orders"),
        f.avg("kitchen_duration_min").alias("avg_kitchen_time_min"),
        f.avg("delivery_duration_min").alias("avg_delivery_time_min"),
        f.avg("total_duration_min").alias("avg_total_time_min"),
        f.percentile_approx("total_duration_min", 0.5).alias("median_total_time_min"),
        f.percentile_approx("total_duration_min", 0.95).alias("p95_total_time_min"),
    )

    perf.write.mode("overwrite").saveAsTable("iceberg.gold.delivery_performance")


def create_brand_summary(spark: SparkSession) -> None:
    """Create brand-level summary metrics."""
    orders = spark.table("iceberg.silver.orders_enriched")
    brands = spark.table("iceberg.bronze.dim_brands")

    brand_metrics = orders.filter(f.col("event_type") == "order_created").groupBy("brand_id").agg(
        f.count("order_id").alias("total_orders"),
        f.sum("order_total").alias("total_revenue"),
        f.avg("order_total").alias("avg_order_value"),
        f.countDistinct("location_id").alias("locations_served"),
        f.min("event_date").alias("first_order_date"),
        f.max("event_date").alias("last_order_date"),
    )

    summary = brand_metrics.join(
        brands.select(f.col("id").alias("brand_id"), "name"),
        on="brand_id", how="left"
    ).select(
        "brand_id", f.col("name").alias("brand_name"),
        "total_orders", "total_revenue", "avg_order_value",
        "locations_served", "first_order_date", "last_order_date",
    )

    summary.write.mode("overwrite").saveAsTable("iceberg.gold.brand_summary")


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

def run_pipeline() -> Dict[str, int]:
    """Run the complete pipeline in order."""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print(f"\nSpark Version: {spark.version}")
    print("=" * 60)
    print("IMPERATIVE PIPELINE (Spark 4.0 Style)")
    print("=" * 60)

    # Bronze layer - must run in order due to dependencies
    print("\n[BRONZE] Loading dimension tables...")
    bronze_tables = [
        ("iceberg.bronze.dim_categories", load_dim_categories),
        ("iceberg.bronze.dim_brands", load_dim_brands),
        ("iceberg.bronze.dim_items", load_dim_items),
        ("iceberg.bronze.dim_locations", load_dim_locations),
        ("iceberg.bronze.orders", load_orders),
    ]

    for name, func in bronze_tables:
        func(spark)
        count = get_table_count(spark, name)
        print(f"  {name}: {count:,} rows")

    # Silver layer - depends on bronze
    print("\n[SILVER] Creating enriched tables...")
    silver_tables = [
        ("iceberg.silver.orders_enriched", create_orders_enriched),
        ("iceberg.silver.order_lifecycle", create_order_lifecycle),
    ]

    for name, func in silver_tables:
        func(spark)
        count = get_table_count(spark, name)
        print(f"  {name}: {count:,} rows")

    # Gold layer - depends on silver
    print("\n[GOLD] Creating aggregation tables...")
    gold_tables = [
        ("iceberg.gold.hourly_metrics", create_hourly_metrics),
        ("iceberg.gold.delivery_performance", create_delivery_performance),
        ("iceberg.gold.brand_summary", create_brand_summary),
    ]

    for name, func in gold_tables:
        func(spark)
        count = get_table_count(spark, name)
        print(f"  {name}: {count:,} rows")

    print("\n" + "=" * 60)
    print("Pipeline complete: 10 tables created")
    print("=" * 60)

    spark.stop()
    return {}


if __name__ == "__main__":
    run_pipeline()
