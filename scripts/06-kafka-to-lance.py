"""
Kafka to Lance Streaming Pipeline
==================================
Streams data from Kafka, generates embeddings, and stores in LanceDB.

Architecture:
    Kafka (products topic) --> Embedding Generator --> LanceDB

This pipeline demonstrates:
1. Consuming JSON messages from Kafka
2. Generating text embeddings using sentence-transformers
3. Writing vectors to LanceDB for similarity search
4. Micro-batch processing for efficiency

Usage:
    # Start the producer first
    python scripts/kafka-lance-producer.py

    # Then run this pipeline
    python scripts/06-kafka-to-lance.py

    # Or via spark-submit
    spark-submit --jars jars/lance-spark-bundle-4.0_2.13-0.0.15.jar \
        scripts/06-kafka-to-lance.py
"""

import os
import sys
import json
import time
import signal
from datetime import datetime

import numpy as np
import lancedb

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from embeddings import get_embedding_generator, MockEmbeddingGenerator

# Configuration
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "products")
LANCE_PATH = os.environ.get("LANCE_PATH", "/tmp/lance_streaming")
TABLE_NAME = "product_embeddings"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
USE_MOCK = os.environ.get("USE_MOCK_EMBEDDINGS", "true").lower() == "true"

# Graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    print("\nShutdown requested...")
    shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def create_lance_table(db, embedding_dim: int):
    """Create or get the Lance table for product embeddings."""
    try:
        table = db.open_table(TABLE_NAME)
        print(f"Opened existing table: {TABLE_NAME}")
        return table
    except Exception:
        # Create new table with schema
        print(f"Creating new table: {TABLE_NAME}")
        initial_data = [
            {
                "id": "init",
                "name": "placeholder",
                "description": "placeholder",
                "category": "init",
                "price": 0.0,
                "timestamp": datetime.now().isoformat(),
                "vector": [0.0] * embedding_dim,
            }
        ]
        table = db.create_table(TABLE_NAME, data=initial_data, mode="overwrite")
        return table


def process_batch(messages: list, embedding_gen, table) -> int:
    """
    Process a batch of messages: generate embeddings and write to Lance.

    Args:
        messages: List of product dictionaries
        embedding_gen: Embedding generator instance
        table: LanceDB table

    Returns:
        Number of records written
    """
    if not messages:
        return 0

    # Extract text for embedding (combine name and description)
    texts = [
        f"{msg.get('name', '')} {msg.get('description', '')}" for msg in messages
    ]

    # Generate embeddings
    embeddings = embedding_gen.encode(texts)

    # Prepare records for Lance
    records = []
    for msg, embedding in zip(messages, embeddings):
        record = {
            "id": msg.get("id", str(time.time_ns())),
            "name": msg.get("name", ""),
            "description": msg.get("description", ""),
            "category": msg.get("category", ""),
            "price": float(msg.get("price", 0.0)),
            "timestamp": msg.get("timestamp", datetime.now().isoformat()),
            "vector": embedding.tolist(),
        }
        records.append(record)

    # Write to Lance
    table.add(records)

    return len(records)


def run_streaming_pipeline():
    """Main streaming pipeline."""
    print("=" * 60)
    print("KAFKA TO LANCE STREAMING PIPELINE")
    print("=" * 60)
    print(f"Kafka: {KAFKA_BOOTSTRAP}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Lance: {LANCE_PATH}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Mock embeddings: {USE_MOCK}")
    print("=" * 60)

    # Initialize embedding generator
    print("\n[1] Initializing embedding generator...")
    if USE_MOCK:
        embedding_gen = MockEmbeddingGenerator(dimension=384)
        print("    Using mock embeddings (fast, for testing)")
    else:
        embedding_gen = get_embedding_generator()
        print(f"    Using model: {embedding_gen.model_name}")
    embedding_dim = embedding_gen.dimension

    # Connect to LanceDB
    print("\n[2] Connecting to LanceDB...")
    os.makedirs(LANCE_PATH, exist_ok=True)
    db = lancedb.connect(LANCE_PATH)
    table = create_lance_table(db, embedding_dim)
    print(f"    Table ready: {TABLE_NAME}")

    # Connect to Kafka
    print("\n[3] Connecting to Kafka...")
    try:
        from kafka import KafkaConsumer

        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id="lance-embedding-consumer",
            consumer_timeout_ms=1000,  # 1 second timeout for batching
        )
        print(f"    Connected to topic: {KAFKA_TOPIC}")
    except Exception as e:
        print(f"    Failed to connect to Kafka: {e}")
        print("    Running in demo mode with sample data...")
        consumer = None

    # Streaming loop
    print("\n[4] Starting streaming loop...")
    print("    Press Ctrl+C to stop\n")

    total_processed = 0
    batch = []
    last_stats_time = time.time()

    try:
        while not shutdown_requested:
            if consumer:
                # Real Kafka consumer
                try:
                    for message in consumer:
                        batch.append(message.value)

                        if len(batch) >= BATCH_SIZE:
                            count = process_batch(batch, embedding_gen, table)
                            total_processed += count
                            print(
                                f"    Processed batch: {count} records "
                                f"(total: {total_processed})"
                            )
                            batch = []

                        if shutdown_requested:
                            break
                except StopIteration:
                    # Timeout reached, process partial batch
                    if batch:
                        count = process_batch(batch, embedding_gen, table)
                        total_processed += count
                        print(
                            f"    Processed partial batch: {count} records "
                            f"(total: {total_processed})"
                        )
                        batch = []
            else:
                # Demo mode - generate sample data
                sample_products = [
                    {
                        "id": f"demo_{int(time.time() * 1000)}_{i}",
                        "name": f"Demo Product {i}",
                        "description": f"This is a sample product for testing the streaming pipeline",
                        "category": "demo",
                        "price": 19.99 + i,
                        "timestamp": datetime.now().isoformat(),
                    }
                    for i in range(BATCH_SIZE)
                ]
                count = process_batch(sample_products, embedding_gen, table)
                total_processed += count
                print(f"    [DEMO] Processed batch: {count} records (total: {total_processed})")
                time.sleep(2)  # Slow down demo mode

            # Print stats every 30 seconds
            if time.time() - last_stats_time > 30:
                print(f"\n    === Stats: {total_processed} total records ===\n")
                last_stats_time = time.time()

    except Exception as e:
        print(f"\nError in streaming loop: {e}")
        raise
    finally:
        # Process remaining batch
        if batch:
            count = process_batch(batch, embedding_gen, table)
            total_processed += count
            print(f"    Processed final batch: {count} records")

        if consumer:
            consumer.close()

    # Final stats
    print("\n" + "=" * 60)
    print("PIPELINE STOPPED")
    print("=" * 60)
    print(f"Total records processed: {total_processed}")
    print(f"Lance data at: {LANCE_PATH}")

    # Verify data
    print("\n[5] Verifying Lance data...")
    table = db.open_table(TABLE_NAME)
    row_count = table.count_rows()
    print(f"    Total rows in table: {row_count}")

    # Sample query
    if row_count > 1:
        print("\n    Sample vector search:")
        query_text = "demo product testing"
        query_vec = embedding_gen.encode_single(query_text)
        results = table.search(query_vec).limit(3).to_pandas()
        for _, row in results.iterrows():
            print(f"      - {row['name']}: {row['_distance']:.4f}")


if __name__ == "__main__":
    run_streaming_pipeline()
