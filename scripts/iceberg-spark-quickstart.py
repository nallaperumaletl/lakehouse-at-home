"""
Iceberg Spark Quickstart
========================
Based on the official Apache Iceberg Spark Quickstart tutorial.
https://iceberg.apache.org/spark-quickstart/

This script demonstrates key Iceberg features:
- Table creation with partitioning
- Data insertion (SQL and DataFrame API)
- Data querying
- Snapshot history
- Time travel
- Schema evolution
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

CATALOG = "iceberg"
NAMESPACE = "demo"
TABLE = "taxis"
FULL_TABLE = f"{CATALOG}.{NAMESPACE}.{TABLE}"

print("=" * 60)
print("ICEBERG SPARK QUICKSTART")
print("=" * 60)

# -----------------------------------------------------------------------------
# 1. CREATE NAMESPACE
# -----------------------------------------------------------------------------
print("\n[1] Creating namespace...")
spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")
namespaces = spark.sql(f"SHOW NAMESPACES IN {CATALOG}").collect()
print(f"    Namespaces: {[row[0] for row in namespaces]}")

# -----------------------------------------------------------------------------
# 2. CREATE TABLE (SQL method)
# -----------------------------------------------------------------------------
print("\n[2] Creating partitioned table via SQL...")
spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")
spark.sql(f"""
    CREATE TABLE {FULL_TABLE} (
        vendor_id bigint,
        trip_id bigint,
        trip_distance float,
        fare_amount double,
        store_and_fwd_flag string
    )
    PARTITIONED BY (vendor_id)
""")
print(f"    Table created: {FULL_TABLE}")

# Show table info
table_info = spark.sql(f"DESCRIBE EXTENDED {FULL_TABLE}").collect()
location = next((row[1] for row in table_info if row[0] == "Location"), "N/A")
print(f"    Location: {location}")

# -----------------------------------------------------------------------------
# 3. INSERT DATA (SQL method)
# -----------------------------------------------------------------------------
print("\n[3] Inserting data via SQL...")
spark.sql(f"""
    INSERT INTO {FULL_TABLE}
    VALUES (1, 1000371, 1.8, 15.32, 'N'),
           (2, 1000372, 2.5, 22.15, 'N'),
           (2, 1000373, 0.9, 9.01, 'N'),
           (1, 1000374, 8.4, 42.13, 'Y')
""")

# Query the data
df = spark.table(FULL_TABLE)
print(f"    Rows inserted: {df.count()}")
print("\n    Data:")
df.orderBy("trip_id").show()

# -----------------------------------------------------------------------------
# 4. INSERT DATA (DataFrame API method)
# -----------------------------------------------------------------------------
print("\n[4] Inserting more data via DataFrame API...")
schema = spark.table(FULL_TABLE).schema
data = [
    (1, 1000375, 3.2, 18.50, "N"),
    (2, 1000376, 5.1, 28.75, "Y"),
]
new_df = spark.createDataFrame(data, schema)
new_df.writeTo(FULL_TABLE).append()

row_count = spark.table(FULL_TABLE).count()
print(f"    Total rows now: {row_count}")

# -----------------------------------------------------------------------------
# 5. SNAPSHOT HISTORY
# -----------------------------------------------------------------------------
print("\n[5] Viewing snapshot history...")
history_df = spark.sql(f"SELECT * FROM {FULL_TABLE}.history")
print("    Snapshots:")
history_df.show(truncate=False)

# Get snapshot IDs for time travel demo
snapshots = history_df.orderBy("made_current_at").collect()
first_snapshot_id = snapshots[0]["snapshot_id"]
latest_snapshot_id = snapshots[-1]["snapshot_id"]
print(f"    First snapshot ID:  {first_snapshot_id}")
print(f"    Latest snapshot ID: {latest_snapshot_id}")

# -----------------------------------------------------------------------------
# 6. TIME TRAVEL
# -----------------------------------------------------------------------------
print("\n[6] Time travel query (querying first snapshot)...")
time_travel_df = spark.sql(
    f"SELECT * FROM {FULL_TABLE} VERSION AS OF {first_snapshot_id}"
)
print(f"    Rows in first snapshot: {time_travel_df.count()}")
print("\n    Data at first snapshot:")
time_travel_df.orderBy("trip_id").show()

# Compare with current state
current_count = spark.table(FULL_TABLE).count()
print(f"    Rows in current snapshot: {current_count}")

# -----------------------------------------------------------------------------
# 7. SCHEMA EVOLUTION
# -----------------------------------------------------------------------------
print("\n[7] Schema evolution - adding a column...")
spark.sql(f"ALTER TABLE {FULL_TABLE} ADD COLUMN tip_amount double")

# Show updated schema
print("    Updated schema:")
for field in spark.table(FULL_TABLE).schema.fields:
    print(f"      - {field.name}: {field.dataType.simpleString()}")

# Insert data with new column
print("\n    Inserting row with tip_amount...")
spark.sql(f"""
    INSERT INTO {FULL_TABLE}
    VALUES (1, 1000377, 2.0, 12.00, 'N', 2.50)
""")

# Show all data - old rows have NULL for tip_amount
print("\n    All data (old rows have NULL tip_amount):")
spark.table(FULL_TABLE).orderBy("trip_id").show()

# -----------------------------------------------------------------------------
# 8. METADATA TABLES
# -----------------------------------------------------------------------------
print("\n[8] Exploring Iceberg metadata tables...")

print("\n    Files:")
spark.sql(f"SELECT file_path, record_count, file_size_in_bytes FROM {FULL_TABLE}.files").show(truncate=50)

print("    Manifests:")
spark.sql(f"SELECT path, length, added_data_files_count FROM {FULL_TABLE}.manifests").show(truncate=50)

print("    Partitions:")
spark.sql(f"SELECT * FROM {FULL_TABLE}.partitions").show()

# -----------------------------------------------------------------------------
# CLEANUP
# -----------------------------------------------------------------------------
print("\n[CLEANUP] Dropping table and namespace...")
spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE}")
spark.sql(f"DROP NAMESPACE IF EXISTS {CATALOG}.{NAMESPACE}")
print("    Done!")

print("\n" + "=" * 60)
print("QUICKSTART COMPLETE")
print("=" * 60)
