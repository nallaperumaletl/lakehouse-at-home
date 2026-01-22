"""Simple SDP Demo - Order Pipeline.

Streaming table from Kafka + materialized view from Iceberg.
"""

from pyspark import pipelines as sdp
from pyspark.sql import DataFrame, SparkSession, functions as f
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

spark = SparkSession.active()


# Streaming table: ingest from Kafka
@sdp.table(name="silver.order_stream")
def order_stream() -> DataFrame:
    """Stream order events from Kafka."""
    schema = StructType([
        StructField("event_id", StringType()),
        StructField("event_type", StringType()),
        StructField("order_id", StringType()),
        StructField("location_id", IntegerType()),
        StructField("ts", StringType()),
    ])

    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "orders")
        .option("startingOffsets", "latest")
        .load()
        .select(f.from_json(f.col("value").cast("string"), schema).alias("data"))
        .select("data.*")
        .filter(f.col("event_type") == "order_created")
    )


# Materialized view: brand summary from Iceberg
@sdp.materialized_view(name="gold.brand_summary")
def brand_summary() -> DataFrame:
    """Order totals per brand from Iceberg bronze tables."""
    orders = spark.table("iceberg.bronze.orders")
    brands = spark.table("iceberg.bronze.dim_brands")

    return (
        orders
        .filter(f.col("event_type") == "order_created")
        .groupBy(f.get_json_object("body", "$.brand_id").cast("int").alias("brand_id"))
        .agg(f.count("order_id").alias("total_orders"))
        .join(brands, f.col("brand_id") == brands["id"])
        .select("brand_id", brands["name"].alias("brand_name"), "total_orders")
    )
