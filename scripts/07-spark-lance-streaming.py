"""
Spark Structured Streaming to Lance Pipeline
=============================================
Uses Spark Structured Streaming to consume from Kafka, generate embeddings,
and write to LanceDB with vector indexing.

Architecture:
    Kafka --> Spark Streaming --> foreachBatch --> Embedding + Lance Write

Features:
- Distributed processing via Spark
- Micro-batch embedding generation
- Automatic vector indexing when threshold reached
- Checkpoint-based exactly-once semantics

Usage:
    # Via spark-submit
    spark-submit --jars jars/spark-sql-kafka-0-10_2.13-4.1.0.jar,jars/lance-spark-bundle-4.0_2.13-0.0.15.jar \
        scripts/07-spark-lance-streaming.py

    # In Docker
    docker exec spark-master-41 /opt/spark/bin/spark-submit \
        --jars /opt/spark/jars-extra/spark-sql-kafka-0-10_2.13-4.1.0.jar \
        /scripts/07-spark-lance-streaming.py
"""

import os
import sys
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    ArrayType,
    FloatType,
)

import lancedb
import numpy as np

# Configuration
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "products")
LANCE_PATH = os.environ.get("LANCE_PATH", "/tmp/lance_spark_streaming")
TABLE_NAME = "product_embeddings"
CHECKPOINT_PATH = os.environ.get("CHECKPOINT_PATH", "/tmp/lance_checkpoint")
INDEX_THRESHOLD = int(os.environ.get("INDEX_THRESHOLD", "256"))  # Rows before indexing
EMBEDDING_DIM = 384

# Global Lance connection (reused across batches)
_lance_db = None
_lance_table = None
_embedding_gen = None
_total_rows = 0


def get_lance_table():
    """Get or create the Lance table."""
    global _lance_db, _lance_table

    if _lance_table is None:
        os.makedirs(LANCE_PATH, exist_ok=True)
        _lance_db = lancedb.connect(LANCE_PATH)

        try:
            _lance_table = _lance_db.open_table(TABLE_NAME)
            print(f"Opened existing Lance table: {TABLE_NAME}")
        except Exception:
            print(f"Creating new Lance table: {TABLE_NAME}")
            initial_data = [
                {
                    "id": "init",
                    "name": "placeholder",
                    "description": "placeholder",
                    "category": "init",
                    "price": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "vector": [0.0] * EMBEDDING_DIM,
                }
            ]
            _lance_table = _lance_db.create_table(
                TABLE_NAME, data=initial_data, mode="overwrite"
            )

    return _lance_table


def get_embedding_generator():
    """Get or create the embedding generator."""
    global _embedding_gen

    if _embedding_gen is None:
        from embeddings import get_embedding_generator as _get_gen

        use_mock = os.environ.get("USE_MOCK_EMBEDDINGS", "true").lower() == "true"
        _embedding_gen = _get_gen(use_mock=use_mock)
        print(f"Embedding generator: {_embedding_gen.model_name}")

    return _embedding_gen


def process_batch(batch_df, batch_id):
    """
    Process a micro-batch from Spark Streaming.

    This function is called for each micro-batch and:
    1. Converts Spark DataFrame to Pandas
    2. Generates embeddings for text fields
    3. Writes to LanceDB
    4. Triggers indexing if threshold reached
    """
    global _total_rows

    if batch_df.isEmpty():
        return

    print(f"\n[Batch {batch_id}] Processing {batch_df.count()} records...")

    # Convert to Pandas
    pdf = batch_df.toPandas()

    # Get embedding generator
    embedding_gen = get_embedding_generator()

    # Generate embeddings from name + description
    texts = (pdf["name"].fillna("") + " " + pdf["description"].fillna("")).tolist()
    embeddings = embedding_gen.encode(texts)

    # Prepare records for Lance
    records = []
    for idx, row in pdf.iterrows():
        record = {
            "id": row.get("id", f"batch_{batch_id}_{idx}"),
            "name": row.get("name", ""),
            "description": row.get("description", ""),
            "category": row.get("category", ""),
            "price": float(row.get("price", 0.0)),
            "timestamp": row.get("timestamp", datetime.now().isoformat()),
            "vector": embeddings[idx].tolist(),
        }
        records.append(record)

    # Write to Lance
    table = get_lance_table()
    table.add(records)
    _total_rows += len(records)

    print(f"[Batch {batch_id}] Wrote {len(records)} records (total: {_total_rows})")

    # Check if we should create/update index
    if _total_rows >= INDEX_THRESHOLD and _total_rows % INDEX_THRESHOLD < len(records):
        try:
            print(f"[Batch {batch_id}] Creating vector index...")
            table.create_index(
                metric="L2",
                num_partitions=min(256, _total_rows // 10),
                num_sub_vectors=16,
                replace=True,
            )
            print(f"[Batch {batch_id}] Index created/updated")
        except Exception as e:
            print(f"[Batch {batch_id}] Index creation skipped: {e}")


def main():
    print("=" * 60)
    print("SPARK STRUCTURED STREAMING TO LANCE")
    print("=" * 60)
    print(f"Kafka: {KAFKA_BOOTSTRAP}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Lance: {LANCE_PATH}")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    print(f"Index threshold: {INDEX_THRESHOLD}")
    print("=" * 60)

    # Create Spark session
    spark = (
        SparkSession.builder.appName("SparkLanceStreaming")
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # Define schema for Kafka messages
    schema = StructType(
        [
            StructField("id", StringType(), True),
            StructField("name", StringType(), True),
            StructField("description", StringType(), True),
            StructField("category", StringType(), True),
            StructField("price", DoubleType(), True),
            StructField("timestamp", StringType(), True),
        ]
    )

    # Read from Kafka
    print("\n[1] Connecting to Kafka...")
    kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # Parse JSON
    print("[2] Setting up stream processing...")
    parsed_df = kafka_df.select(
        f.from_json(f.col("value").cast("string"), schema).alias("data")
    ).select("data.*")

    # Start streaming query with foreachBatch
    print("[3] Starting streaming query...")
    print("    Press Ctrl+C to stop\n")

    query = (
        parsed_df.writeStream.foreachBatch(process_batch)
        .option("checkpointLocation", CHECKPOINT_PATH)
        .trigger(processingTime="5 seconds")
        .start()
    )

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n\nStopping streaming query...")
        query.stop()

    # Final stats
    print("\n" + "=" * 60)
    print("STREAMING STOPPED")
    print("=" * 60)
    print(f"Total records processed: {_total_rows}")

    # Verify data
    table = get_lance_table()
    row_count = table.count_rows()
    print(f"Total rows in Lance table: {row_count}")

    # Sample search
    if row_count > 1:
        print("\nSample vector search:")
        embedding_gen = get_embedding_generator()
        query_vec = embedding_gen.encode_single("wireless headphones audio")
        results = table.search(query_vec).limit(3).to_pandas()
        for _, row in results.iterrows():
            print(f"  - {row['name']}: {row['_distance']:.4f}")

    spark.stop()


if __name__ == "__main__":
    main()
