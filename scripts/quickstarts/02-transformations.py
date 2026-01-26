"""
Spark Transformations Deep Dive
===============================

Learn narrow vs wide transformations and when shuffles occur.

This script demonstrates:
- Narrow transformations (filter, map, withColumn) - no shuffle
- Wide transformations (groupBy, join, distinct) - shuffle required
- Execution plans showing shuffle boundaries
- Aggregations and window functions

Prerequisites:
    - Spark cluster running: ./lakehouse start spark
    - PostgreSQL and SeaweedFS running

Usage:
    docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/quickstarts/02-transformations.py
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("02-Transformations").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

CATALOG = "iceberg"
NAMESPACE = "quickstart"

print("=" * 60)
print("SPARK TRANSFORMATIONS DEEP DIVE")
print("=" * 60)

# -----------------------------------------------------------------------------
# SETUP - Create sample tables
# -----------------------------------------------------------------------------
print("\n[SETUP] Creating sample tables...")

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")

# Orders table
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{NAMESPACE}.orders")
spark.sql(f"""
    CREATE TABLE {CATALOG}.{NAMESPACE}.orders (
        order_id INT,
        customer_id INT,
        product STRING,
        amount DOUBLE,
        order_date DATE
    )
""")
spark.sql(f"""
    INSERT INTO {CATALOG}.{NAMESPACE}.orders VALUES
    (1, 101, 'Laptop', 999.99, DATE '2024-01-15'),
    (2, 102, 'Mouse', 29.99, DATE '2024-01-15'),
    (3, 101, 'Keyboard', 79.99, DATE '2024-01-16'),
    (4, 103, 'Monitor', 399.99, DATE '2024-01-16'),
    (5, 102, 'Mouse', 29.99, DATE '2024-01-17'),
    (6, 101, 'Webcam', 89.99, DATE '2024-01-17'),
    (7, 104, 'Laptop', 999.99, DATE '2024-01-18'),
    (8, 103, 'Keyboard', 79.99, DATE '2024-01-18')
""")

# Customers table
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{NAMESPACE}.customers")
spark.sql(f"""
    CREATE TABLE {CATALOG}.{NAMESPACE}.customers (
        customer_id INT,
        name STRING,
        city STRING
    )
""")
spark.sql(f"""
    INSERT INTO {CATALOG}.{NAMESPACE}.customers VALUES
    (101, 'Alice', 'Seattle'),
    (102, 'Bob', 'Portland'),
    (103, 'Charlie', 'Seattle'),
    (104, 'Diana', 'San Francisco')
""")

orders = spark.table(f"{CATALOG}.{NAMESPACE}.orders")
customers = spark.table(f"{CATALOG}.{NAMESPACE}.customers")

print("    Created: orders (8 rows), customers (4 rows)")

# -----------------------------------------------------------------------------
# 1. NARROW TRANSFORMATIONS - No shuffle, partition-local
# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print("[1] NARROW TRANSFORMATIONS (no shuffle)")
print("=" * 60)

print("\n    Narrow: filter, withColumn, select")
print("    These operate within each partition - no data movement")

narrow_result = orders \
    .filter(f.col("amount") > 50) \
    .withColumn("amount_with_tax", f.col("amount") * 1.1) \
    .select("order_id", "product", "amount", "amount_with_tax")

print("\n    Execution Plan (notice: no Exchange/Shuffle):")
narrow_result.explain()

print("\n    Result:")
narrow_result.show()

# -----------------------------------------------------------------------------
# 2. WIDE TRANSFORMATIONS - Shuffle required
# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print("[2] WIDE TRANSFORMATIONS (shuffle required)")
print("=" * 60)

print("\n    Wide: groupBy, join, distinct, repartition")
print("    These require moving data between partitions")

# GroupBy - requires shuffle
print("\n    --- GroupBy Aggregation ---")
grouped = orders.groupBy("customer_id").agg(
    f.count("*").alias("order_count"),
    f.sum("amount").alias("total_spent"),
    f.avg("amount").alias("avg_order")
)

print("    Execution Plan (notice: Exchange = shuffle):")
grouped.explain()

print("\n    Result:")
grouped.show()

# -----------------------------------------------------------------------------
# 3. JOINS - Different join strategies
# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print("[3] JOINS")
print("=" * 60)

# Regular join (shuffle both sides)
print("\n    --- Regular Join (SortMergeJoin) ---")
joined = orders.join(customers, on="customer_id", how="inner")
print("    Plan shows shuffle on both sides:")
joined.explain()

# Broadcast join (small table broadcast, no shuffle)
print("\n    --- Broadcast Join (no shuffle for small table) ---")
broadcast_joined = orders.join(f.broadcast(customers), on="customer_id", how="inner")
print("    Plan shows BroadcastHashJoin:")
broadcast_joined.explain()

print("\n    Result (same for both):")
joined.select("order_id", "name", "city", "product", "amount").show()

# -----------------------------------------------------------------------------
# 4. AGGREGATIONS
# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print("[4] AGGREGATIONS")
print("=" * 60)

print("\n    --- By Product ---")
orders.groupBy("product").agg(
    f.count("*").alias("times_ordered"),
    f.sum("amount").alias("total_revenue")
).orderBy(f.desc("total_revenue")).show()

print("\n    --- By Date ---")
orders.groupBy("order_date").agg(
    f.count("*").alias("orders"),
    f.sum("amount").alias("daily_revenue")
).orderBy("order_date").show()

# -----------------------------------------------------------------------------
# 5. WINDOW FUNCTIONS
# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print("[5] WINDOW FUNCTIONS")
print("=" * 60)

print("\n    Running total per customer:")
window_spec = Window.partitionBy("customer_id").orderBy("order_date")

windowed = orders.withColumn(
    "running_total", f.sum("amount").over(window_spec)
).withColumn(
    "order_rank", f.row_number().over(window_spec)
)

windowed.select(
    "customer_id", "order_date", "product", "amount",
    "running_total", "order_rank"
).orderBy("customer_id", "order_date").show()

# -----------------------------------------------------------------------------
# CLEANUP
# -----------------------------------------------------------------------------
print("\n[CLEANUP] Dropping tables and namespace...")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{NAMESPACE}.orders")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{NAMESPACE}.customers")
spark.sql(f"DROP NAMESPACE IF EXISTS {CATALOG}.{NAMESPACE}")
print("    Done!")

print("\n" + "=" * 60)
print("TRANSFORMATIONS COMPLETE - Next: 03-streaming-basic.py")
print("=" * 60)
