"""
Spark + Iceberg Basics
======================

Learn fundamental Spark operations with Iceberg tables.

This script demonstrates:
- Creating tables
- Basic transformations (filter, withColumn, select)
- Viewing execution plans
- Querying Iceberg metadata

Prerequisites:
    - Spark cluster running: ./lakehouse start spark
    - PostgreSQL and SeaweedFS running

Usage:
    docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/quickstarts/01-basics.py
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as f

spark = SparkSession.builder.appName("01-Basics").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

CATALOG = "iceberg"
NAMESPACE = "quickstart"
TABLE = "products"
FULL_TABLE = f"{CATALOG}.{NAMESPACE}.{TABLE}"

print("=" * 60)
print("SPARK + ICEBERG BASICS")
print("=" * 60)

# -----------------------------------------------------------------------------
# 1. SETUP - Create namespace and table
# -----------------------------------------------------------------------------
print("\n[1] Setting up namespace and table...")
spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")
spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")

# Create table with sample data
spark.sql(f"""
    CREATE TABLE {FULL_TABLE} (
        id INT,
        name STRING,
        category STRING,
        price DOUBLE,
        in_stock BOOLEAN
    )
""")

# Insert sample data
spark.sql(f"""
    INSERT INTO {FULL_TABLE} VALUES
    (1, 'Laptop', 'Electronics', 999.99, true),
    (2, 'Mouse', 'Electronics', 29.99, true),
    (3, 'Desk Chair', 'Furniture', 249.99, false),
    (4, 'Monitor', 'Electronics', 399.99, true),
    (5, 'Notebook', 'Office', 4.99, true),
    (6, 'Pen Set', 'Office', 12.99, true),
    (7, 'Standing Desk', 'Furniture', 599.99, false)
""")

print(f"    Created table: {FULL_TABLE}")

# -----------------------------------------------------------------------------
# 2. READ - Load table as DataFrame
# -----------------------------------------------------------------------------
print("\n[2] Reading table as DataFrame...")
df = spark.table(FULL_TABLE)
print(f"    Rows: {df.count()}")
print("\n    All data:")
df.show()

# -----------------------------------------------------------------------------
# 3. FILTER - Select specific rows
# -----------------------------------------------------------------------------
print("\n[3] Filter: Electronics only...")
electronics = df.filter(f.col("category") == "Electronics")
electronics.show()

print("    Filter: In stock items over $100...")
expensive_available = df.filter(
    (f.col("in_stock") == True) & (f.col("price") > 100)
)
expensive_available.show()

# -----------------------------------------------------------------------------
# 4. WITHCOLUMN - Add computed columns
# -----------------------------------------------------------------------------
print("\n[4] Add computed columns...")
with_tax = df.withColumn("price_with_tax", f.col("price") * 1.10)
with_tax = with_tax.withColumn("price_doubled", f.col("price") * 2)
with_tax.select("name", "price", "price_with_tax", "price_doubled").show()

# -----------------------------------------------------------------------------
# 5. SELECT - Choose specific columns
# -----------------------------------------------------------------------------
print("\n[5] Select specific columns...")
df.select("name", "category", "price").show()

# -----------------------------------------------------------------------------
# 6. EXECUTION PLAN - Understand how Spark processes queries
# -----------------------------------------------------------------------------
print("\n[6] View execution plan...")
query = df.filter(f.col("price") > 100).select("name", "price")
print("    Query: df.filter(price > 100).select(name, price)")
print("\n    Execution Plan:")
query.explain()

# -----------------------------------------------------------------------------
# 7. ICEBERG METADATA - Query table information
# -----------------------------------------------------------------------------
print("\n[7] Iceberg table metadata...")

print("\n    Table type:")
table_type = spark.catalog.getTable(FULL_TABLE).tableType
print(f"    {table_type}")

print("\n    Table properties:")
spark.sql(f"DESCRIBE EXTENDED {FULL_TABLE}").show(100, truncate=False)

print("\n    Snapshots (version history):")
spark.sql(f"SELECT * FROM {FULL_TABLE}.snapshots").show(truncate=False)

# -----------------------------------------------------------------------------
# CLEANUP
# -----------------------------------------------------------------------------
print("\n[CLEANUP] Dropping table and namespace...")
spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")
spark.sql(f"DROP NAMESPACE IF EXISTS {CATALOG}.{NAMESPACE}")
print("    Done!")

print("\n" + "=" * 60)
print("BASICS COMPLETE - Next: 02-transformations.py")
print("=" * 60)
