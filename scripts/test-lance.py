#!/usr/bin/env python3
"""
Lance Health Check and Test Script
===================================
Tests Lance functionality in the Docker environment:
1. LanceDB Python SDK operations
2. Lance + PySpark integration
3. S3 storage backend (SeaweedFS)

Exit codes:
  0 - All tests passed
  1 - Test failures

Usage:
  # Local test (without Spark cluster)
  python scripts/test-lance.py --local

  # Full test (requires running Spark cluster)
  docker exec spark-master-lance python /scripts/test-lance.py

  # Test with S3 storage
  docker exec spark-master-lance python /scripts/test-lance.py --s3
"""

import argparse
import os
import sys
import tempfile
import time

# Test results tracking
results = {"passed": 0, "failed": 0, "skipped": 0}


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n[TEST] {name}...")
            try:
                result = func(*args, **kwargs)
                print(f"  PASSED")
                results["passed"] += 1
                return result
            except Exception as e:
                print(f"  FAILED: {e}")
                results["failed"] += 1
                return None
        return wrapper
    return decorator


def skip(name, reason):
    """Mark a test as skipped."""
    print(f"\n[TEST] {name}...")
    print(f"  SKIPPED: {reason}")
    results["skipped"] += 1


# =============================================================================
# Test 1: LanceDB Python SDK
# =============================================================================
@test("LanceDB Python SDK Import")
def test_lancedb_import():
    import lancedb
    import pyarrow
    assert lancedb.__version__, "LanceDB version not available"
    print(f"  LanceDB version: {lancedb.__version__}")
    print(f"  PyArrow version: {pyarrow.__version__}")


@test("LanceDB Table Creation")
def test_lancedb_table_create(db_path):
    import lancedb
    import numpy as np

    db = lancedb.connect(db_path)

    # Create test data with embeddings
    data = [
        {"id": 1, "text": "hello world", "vector": np.random.rand(128).tolist()},
        {"id": 2, "text": "goodbye world", "vector": np.random.rand(128).tolist()},
        {"id": 3, "text": "lance test", "vector": np.random.rand(128).tolist()},
    ]

    table = db.create_table("test_table", data=data, mode="overwrite")
    assert table.count_rows() == 3, f"Expected 3 rows, got {table.count_rows()}"
    print(f"  Created table with {table.count_rows()} rows")


@test("LanceDB Vector Search")
def test_lancedb_vector_search(db_path):
    import lancedb
    import numpy as np

    db = lancedb.connect(db_path)
    table = db.open_table("test_table")

    # Search with a random vector
    query_vector = np.random.rand(128).tolist()
    results = table.search(query_vector).limit(2).to_pandas()

    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert "_distance" in results.columns, "Distance column missing"
    print(f"  Found {len(results)} results with distances: {results['_distance'].tolist()}")


@test("LanceDB Filter Query")
def test_lancedb_filter(db_path):
    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("test_table")

    results = table.search().where("id > 1").to_pandas()
    assert len(results) == 2, f"Expected 2 rows with id > 1, got {len(results)}"
    print(f"  Filtered to {len(results)} rows")


# =============================================================================
# Test 2: PySpark Integration
# =============================================================================
@test("PySpark Session Creation")
def test_spark_session(lance_jar):
    from pyspark.sql import SparkSession

    builder = SparkSession.builder.appName("LanceTest")

    if lance_jar and os.path.exists(lance_jar):
        builder = builder.config("spark.jars", lance_jar)
        print(f"  Using Lance JAR: {lance_jar}")

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    assert spark is not None, "Failed to create SparkSession"
    print(f"  Spark version: {spark.version}")

    return spark


@test("Lance DataFrame via PyArrow")
def test_lance_to_spark(db_path, spark):
    import lancedb

    db = lancedb.connect(db_path)
    table = db.open_table("test_table")

    # Convert via PyArrow (works without lance-spark JAR)
    arrow_table = table.to_arrow()
    pdf = arrow_table.to_pandas()
    pdf_no_vector = pdf.drop(columns=["vector"])

    df = spark.createDataFrame(pdf_no_vector)
    assert df.count() == 3, f"Expected 3 rows, got {df.count()}"
    print(f"  Loaded {df.count()} rows into Spark DataFrame")

    # Test SQL query
    df.createOrReplaceTempView("lance_test")
    result = spark.sql("SELECT COUNT(*) as cnt FROM lance_test").collect()
    assert result[0]["cnt"] == 3
    print("  SQL query successful")


# =============================================================================
# Test 3: S3 Storage (SeaweedFS)
# =============================================================================
@test("S3 Storage Backend")
def test_s3_storage(s3_path):
    import lancedb

    # Connect to S3-backed Lance
    db = lancedb.connect(s3_path)

    # Create test table
    import numpy as np
    data = [
        {"id": 1, "text": "s3 test", "vector": np.random.rand(64).tolist()},
    ]

    table = db.create_table("s3_test", data=data, mode="overwrite")
    assert table.count_rows() == 1
    print(f"  Created S3-backed table with {table.count_rows()} rows")

    # Verify data persists
    db2 = lancedb.connect(s3_path)
    table2 = db2.open_table("s3_test")
    assert table2.count_rows() == 1
    print("  Verified S3 persistence")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Lance Health Check")
    parser.add_argument("--local", action="store_true", help="Run local tests only")
    parser.add_argument("--s3", action="store_true", help="Test S3 storage backend")
    parser.add_argument("--s3-path", default="s3://lakehouse/lance", help="S3 path for Lance")
    args = parser.parse_args()

    print("=" * 60)
    print("LANCE HEALTH CHECK")
    print("=" * 60)

    # Create temp directory for local tests
    db_path = tempfile.mkdtemp(prefix="lance_test_")
    print(f"Test directory: {db_path}")

    # Find Lance JAR
    lance_jar = None
    jar_paths = [
        "/opt/spark/jars-extra/lance-spark-bundle-4.0_2.13-0.0.15.jar",
        os.path.join(os.path.dirname(__file__), "..", "jars", "lance-spark-bundle-4.0_2.13-0.0.15.jar"),
    ]
    for path in jar_paths:
        if os.path.exists(path):
            lance_jar = path
            break

    # Run tests
    print("\n" + "-" * 60)
    print("Part 1: LanceDB Python SDK")
    print("-" * 60)

    test_lancedb_import()
    test_lancedb_table_create(db_path)
    test_lancedb_vector_search(db_path)
    test_lancedb_filter(db_path)

    print("\n" + "-" * 60)
    print("Part 2: PySpark Integration")
    print("-" * 60)

    spark = None
    try:
        spark = test_spark_session(lance_jar)
        if spark:
            test_lance_to_spark(db_path, spark)
    except Exception as e:
        print(f"  Spark tests failed: {e}")
        results["failed"] += 1
    finally:
        if spark:
            spark.stop()

    print("\n" + "-" * 60)
    print("Part 3: S3 Storage Backend")
    print("-" * 60)

    if args.s3:
        test_s3_storage(args.s3_path)
    else:
        skip("S3 Storage Backend", "Use --s3 flag to test S3 storage")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Passed:  {results['passed']}")
    print(f"  Failed:  {results['failed']}")
    print(f"  Skipped: {results['skipped']}")
    print("=" * 60)

    # Cleanup
    import shutil
    shutil.rmtree(db_path, ignore_errors=True)

    # Exit code
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
