#!/usr/bin/env python3
"""
Unity Catalog OSS Demo Script

This script demonstrates using Unity Catalog as the Iceberg REST Catalog
instead of the PostgreSQL JDBC catalog.

Prerequisites:
    1. Start Unity Catalog: ./lakehouse start unity-catalog
    2. Configure Spark: cp config/spark/spark-defaults-uc.conf.example config/spark/spark-defaults.conf
    3. Start Spark: ./lakehouse start spark

Usage:
    # Run via spark-submit
    docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/unity_catalog_demo.py

    # Or run locally (requires local Spark with UC config)
    python scripts/unity_catalog_demo.py
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import StructType, StructField, StringType, DecimalType
from decimal import Decimal
import sys


def create_spark_session():
    """Create SparkSession configured for Unity Catalog."""

    # Check if we're in a cluster environment (SparkSession may already exist)
    try:
        existing = SparkSession.getActiveSession()
        if existing:
            print("Using existing SparkSession")
            return existing
    except Exception:
        pass

    # Create new session with Unity Catalog config
    return SparkSession.builder \
        .appName("Unity Catalog Demo") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.iceberg.catalog-impl", "org.apache.iceberg.rest.RESTCatalog") \
        .config("spark.sql.catalog.iceberg.uri", "http://localhost:8080/api/2.1/unity-catalog/iceberg") \
        .config("spark.sql.catalog.iceberg.warehouse", "unity") \
        .config("spark.sql.catalog.iceberg.token", "not_used") \
        .getOrCreate()


def setup_schemas(spark):
    """Create medallion architecture schemas."""
    print("\n" + "="*60)
    print("Setting up Medallion Architecture Schemas")
    print("="*60)

    schemas = ["bronze", "silver", "gold"]
    for schema in schemas:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS iceberg.{schema}")
        print(f"  Created schema: iceberg.{schema}")

    # List schemas
    print("\nSchemas in catalog:")
    spark.sql("SHOW SCHEMAS IN iceberg").show()


def create_sample_table(spark):
    """Create and populate a sample orders table."""
    print("\n" + "="*60)
    print("Creating Sample Orders Table")
    print("="*60)

    # Drop if exists
    spark.sql("DROP TABLE IF EXISTS iceberg.bronze.demo_orders")

    # Create table
    spark.sql("""
        CREATE TABLE iceberg.bronze.demo_orders (
            order_id STRING,
            customer_id STRING,
            product_name STRING,
            quantity INT,
            unit_price DECIMAL(10,2),
            total DECIMAL(10,2),
            order_date DATE,
            created_at TIMESTAMP
        ) USING ICEBERG
        PARTITIONED BY (days(order_date))
    """)
    print("  Created table: iceberg.bronze.demo_orders")

    # Insert sample data
    sample_data = [
        ("ORD-001", "CUST-101", "Laptop", 1, Decimal("999.99"), Decimal("999.99"), "2024-01-15"),
        ("ORD-002", "CUST-102", "Mouse", 2, Decimal("29.99"), Decimal("59.98"), "2024-01-15"),
        ("ORD-003", "CUST-101", "Keyboard", 1, Decimal("79.99"), Decimal("79.99"), "2024-01-16"),
        ("ORD-004", "CUST-103", "Monitor", 2, Decimal("299.99"), Decimal("599.98"), "2024-01-16"),
        ("ORD-005", "CUST-102", "USB Cable", 5, Decimal("9.99"), Decimal("49.95"), "2024-01-17"),
    ]

    schema = StructType([
        StructField("order_id", StringType(), False),
        StructField("customer_id", StringType(), False),
        StructField("product_name", StringType(), False),
        StructField("quantity", StringType(), False),  # Will be cast
        StructField("unit_price", DecimalType(10, 2), False),
        StructField("total", DecimalType(10, 2), False),
        StructField("order_date", StringType(), False),  # Will be cast
    ])

    df = spark.createDataFrame(
        [(o[0], o[1], o[2], str(o[3]), o[4], o[5], o[6]) for o in sample_data],
        schema
    ).withColumn("quantity", f.col("quantity").cast("int")) \
     .withColumn("order_date", f.to_date("order_date")) \
     .withColumn("created_at", f.current_timestamp())

    df.writeTo("iceberg.bronze.demo_orders").append()
    print(f"  Inserted {len(sample_data)} sample orders")

    # Show data
    print("\nSample data:")
    spark.table("iceberg.bronze.demo_orders").show()


def demonstrate_iceberg_features(spark):
    """Demonstrate Iceberg-specific features."""
    print("\n" + "="*60)
    print("Iceberg Features Demo")
    print("="*60)

    # 1. Table history
    print("\n1. Table History (snapshots):")
    spark.sql("SELECT * FROM iceberg.bronze.demo_orders.history").show(truncate=False)

    # 2. Table metadata
    print("\n2. Table Metadata:")
    spark.sql("SELECT * FROM iceberg.bronze.demo_orders.metadata_log_entries").show(truncate=False)

    # 3. Schema evolution - add a column
    print("\n3. Schema Evolution - Adding 'status' column:")
    spark.sql("ALTER TABLE iceberg.bronze.demo_orders ADD COLUMN status STRING")
    spark.sql("DESCRIBE iceberg.bronze.demo_orders").show()

    # 4. Update with new column
    print("\n4. Update records with status:")
    spark.sql("""
        UPDATE iceberg.bronze.demo_orders
        SET status = 'completed'
        WHERE order_id IN ('ORD-001', 'ORD-002', 'ORD-003')
    """)
    spark.sql("""
        UPDATE iceberg.bronze.demo_orders
        SET status = 'pending'
        WHERE status IS NULL
    """)
    spark.table("iceberg.bronze.demo_orders").show()

    # 5. Partitions
    print("\n5. Table Partitions:")
    spark.sql("SELECT * FROM iceberg.bronze.demo_orders.partitions").show()


def create_silver_aggregation(spark):
    """Create a silver layer aggregation."""
    print("\n" + "="*60)
    print("Silver Layer - Customer Summary")
    print("="*60)

    spark.sql("DROP TABLE IF EXISTS iceberg.silver.customer_summary")

    spark.sql("""
        CREATE TABLE iceberg.silver.customer_summary
        USING ICEBERG
        AS
        SELECT
            customer_id,
            COUNT(*) as total_orders,
            SUM(total) as total_spent,
            AVG(total) as avg_order_value,
            MIN(order_date) as first_order,
            MAX(order_date) as last_order
        FROM iceberg.bronze.demo_orders
        GROUP BY customer_id
    """)

    print("Created silver table: iceberg.silver.customer_summary")
    spark.table("iceberg.silver.customer_summary").show()


def list_all_tables(spark):
    """List all tables in all schemas."""
    print("\n" + "="*60)
    print("All Tables in Unity Catalog")
    print("="*60)

    for schema in ["bronze", "silver", "gold"]:
        print(f"\nTables in iceberg.{schema}:")
        spark.sql(f"SHOW TABLES IN iceberg.{schema}").show()


def cleanup(spark):
    """Clean up demo tables."""
    print("\n" + "="*60)
    print("Cleanup")
    print("="*60)

    spark.sql("DROP TABLE IF EXISTS iceberg.bronze.demo_orders")
    spark.sql("DROP TABLE IF EXISTS iceberg.silver.customer_summary")
    print("  Dropped demo tables")


def main():
    print("="*60)
    print("Unity Catalog OSS Demo")
    print("="*60)

    # Parse args
    do_cleanup = "--cleanup" in sys.argv

    try:
        spark = create_spark_session()

        # Run demo
        setup_schemas(spark)
        create_sample_table(spark)
        demonstrate_iceberg_features(spark)
        create_silver_aggregation(spark)
        list_all_tables(spark)

        if do_cleanup:
            cleanup(spark)

        print("\n" + "="*60)
        print("Demo completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("  - Query tables: spark.table('iceberg.bronze.demo_orders').show()")
        print("  - View in DuckDB: See docs/guides/unity-catalog.md")
        print("  - Clean up: python scripts/unity_catalog_demo.py --cleanup")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("  1. Is Unity Catalog running? ./lakehouse start unity-catalog")
        print("  2. Is Spark configured? Check config/spark/spark-defaults.conf")
        print("  3. Check logs: ./lakehouse logs unity-catalog")
        sys.exit(1)


if __name__ == "__main__":
    main()
