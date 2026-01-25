"""
Lance + PySpark Quickstart
==========================
This script demonstrates LanceDB integration for multimodal AI workloads:
- Creating Lance tables with vector embeddings
- Writing data with embeddings
- Reading Lance data via PySpark
- Vector similarity search
- Hybrid queries (vector + metadata filters)

Prerequisites:
- lancedb Python package: pip install lancedb sentence-transformers
- lance-spark JAR: scripts/download-lance-jars.sh
"""

import os
import tempfile
import numpy as np

# LanceDB Python SDK for local operations
import lancedb
from pyspark.sql import SparkSession
from pyspark.sql import functions as f

# Configuration
LANCE_DIR = os.environ.get("LANCE_DIR", tempfile.mkdtemp(prefix="lance_demo_"))
LANCE_JAR = os.environ.get(
    "LANCE_JAR", "/opt/spark/jars/lance-spark-bundle-4.0_2.13-0.0.15.jar"
)

print("=" * 60)
print("LANCE + PYSPARK QUICKSTART")
print("=" * 60)
print(f"Lance directory: {LANCE_DIR}")

# -----------------------------------------------------------------------------
# PART 1: LanceDB Python SDK (Local Operations)
# -----------------------------------------------------------------------------
print("\n" + "-" * 60)
print("PART 1: LanceDB Python SDK")
print("-" * 60)

# 1.1 Create a LanceDB connection
print("\n[1.1] Creating LanceDB connection...")
db = lancedb.connect(LANCE_DIR)
print(f"      Connected to: {LANCE_DIR}")

# 1.2 Create sample data with embeddings
print("\n[1.2] Creating sample product data with embeddings...")

# Simulate product embeddings (in practice, use sentence-transformers or CLIP)
# Embedding dimension: 384 (common for sentence-transformers/all-MiniLM-L6-v2)
np.random.seed(42)
EMBEDDING_DIM = 384


def create_sample_embedding(text: str) -> list:
    """Create a deterministic pseudo-embedding based on text hash."""
    np.random.seed(hash(text) % (2**32))
    return np.random.randn(EMBEDDING_DIM).astype(np.float32).tolist()


products = [
    {
        "id": 1,
        "name": "Wireless Bluetooth Headphones",
        "category": "electronics",
        "price": 79.99,
        "description": "Premium noise-canceling wireless headphones with 30-hour battery",
        "vector": create_sample_embedding("wireless bluetooth headphones audio"),
    },
    {
        "id": 2,
        "name": "Running Shoes Pro",
        "category": "sports",
        "price": 129.99,
        "description": "Lightweight running shoes with advanced cushioning technology",
        "vector": create_sample_embedding("running shoes athletic footwear"),
    },
    {
        "id": 3,
        "name": "Organic Green Tea",
        "category": "food",
        "price": 12.99,
        "description": "Premium Japanese matcha green tea, 100 servings",
        "vector": create_sample_embedding("organic green tea matcha beverage"),
    },
    {
        "id": 4,
        "name": "USB-C Laptop Charger",
        "category": "electronics",
        "price": 49.99,
        "description": "65W fast charging USB-C power adapter for laptops",
        "vector": create_sample_embedding("usb laptop charger power adapter"),
    },
    {
        "id": 5,
        "name": "Yoga Mat Premium",
        "category": "sports",
        "price": 45.99,
        "description": "Non-slip eco-friendly yoga mat with carrying strap",
        "vector": create_sample_embedding("yoga mat exercise fitness"),
    },
    {
        "id": 6,
        "name": "Smart Watch Fitness",
        "category": "electronics",
        "price": 199.99,
        "description": "Fitness tracker with heart rate, GPS, and sleep monitoring",
        "vector": create_sample_embedding("smart watch fitness tracker wearable"),
    },
    {
        "id": 7,
        "name": "Protein Powder Vanilla",
        "category": "food",
        "price": 34.99,
        "description": "Whey protein powder, 2lb container, vanilla flavor",
        "vector": create_sample_embedding("protein powder supplement nutrition"),
    },
    {
        "id": 8,
        "name": "Noise Canceling Earbuds",
        "category": "electronics",
        "price": 149.99,
        "description": "True wireless earbuds with active noise cancellation",
        "vector": create_sample_embedding("wireless earbuds noise canceling audio"),
    },
]

print(f"      Created {len(products)} sample products")
print(f"      Embedding dimension: {EMBEDDING_DIM}")

# 1.3 Create Lance table
print("\n[1.3] Creating Lance table 'products'...")
table = db.create_table("products", data=products, mode="overwrite")
print(f"      Table created with {table.count_rows()} rows")

# 1.4 Basic query
print("\n[1.4] Basic query - all electronics:")
results = table.search().where("category = 'electronics'").limit(10).to_pandas()
print(results[["id", "name", "category", "price"]].to_string(index=False))

# 1.5 Vector similarity search
print("\n[1.5] Vector similarity search - 'audio devices':")
query_vector = create_sample_embedding("audio devices headphones earbuds")
results = table.search(query_vector).limit(3).to_pandas()
print("      Top 3 similar products:")
for _, row in results.iterrows():
    print(f"        - {row['name']} (distance: {row['_distance']:.4f})")

# 1.6 Hybrid search (vector + filter)
print("\n[1.6] Hybrid search - 'fitness' in electronics under $200:")
query_vector = create_sample_embedding("fitness health tracking")
results = (
    table.search(query_vector)
    .where("category = 'electronics' AND price < 200")
    .limit(3)
    .to_pandas()
)
print("      Results:")
for _, row in results.iterrows():
    print(f"        - {row['name']}: ${row['price']} (distance: {row['_distance']:.4f})")

# 1.7 Create vector index for faster search (requires 256+ rows for PQ)
print("\n[1.7] Vector index creation...")
row_count = table.count_rows()
if row_count >= 256:
    table.create_index(
        metric="L2",
        num_partitions=256,
        num_sub_vectors=16,
    )
    print("      IVF-PQ index created")
else:
    print(f"      Skipped: PQ requires 256+ rows, have {row_count}")
    print("      (In production with more data, indexing enables sub-ms search)")

# -----------------------------------------------------------------------------
# PART 2: Lance + PySpark Integration
# -----------------------------------------------------------------------------
print("\n" + "-" * 60)
print("PART 2: Lance + PySpark Integration")
print("-" * 60)

# 2.1 Create Spark session with Lance support
print("\n[2.1] Creating Spark session with Lance support...")

# Check if we're running inside Docker with the JAR available
jar_exists = os.path.exists(LANCE_JAR)
if not jar_exists:
    # Try local jars directory
    local_jar = os.path.join(
        os.path.dirname(__file__), "..", "jars", "lance-spark-bundle-4.0_2.13-0.0.15.jar"
    )
    if os.path.exists(local_jar):
        LANCE_JAR = local_jar
        jar_exists = True

builder = SparkSession.builder.appName("LanceQuickstart")

if jar_exists:
    print(f"      Using Lance JAR: {LANCE_JAR}")
    builder = builder.config("spark.jars", LANCE_JAR)
else:
    print("      WARNING: Lance JAR not found, Spark-Lance features limited")
    print(f"      Expected at: {LANCE_JAR}")

spark = builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")
print("      Spark session created")

# 2.2 Read Lance table into Spark DataFrame
print("\n[2.2] Reading Lance table into Spark DataFrame...")
lance_path = os.path.join(LANCE_DIR, "products.lance")
df = None

# Method 1: Using lance format reader (requires lance-spark JAR)
if jar_exists:
    try:
        df = spark.read.format("lance").load(lance_path)
        print("      Loaded via lance format reader")
        print(f"      Schema: {df.schema.simpleString()}")
        print(f"      Row count: {df.count()}")
    except Exception as e:
        print(f"      Lance format reader failed: {e}")
        jar_exists = False

# Method 2: Convert via PyArrow (fallback if JAR not available or failed)
if df is None:
    print("      Falling back to PyArrow conversion...")
    # Read Lance table as PyArrow table
    arrow_table = table.to_arrow()
    # Convert to Spark DataFrame (excluding vector column for simplicity)
    pdf = arrow_table.to_pandas()
    pdf_no_vector = pdf.drop(columns=["vector"])
    df = spark.createDataFrame(pdf_no_vector)
    print(f"      Loaded via PyArrow conversion")
    print(f"      Row count: {df.count()}")

assert df is not None, "Failed to load Lance data into Spark DataFrame"

# 2.3 Spark SQL queries on Lance data
print("\n[2.3] Spark SQL queries on Lance data:")
df.createOrReplaceTempView("products")

print("\n      Category summary:")
spark.sql("""
    SELECT category, COUNT(*) as count, ROUND(AVG(price), 2) as avg_price
    FROM products
    GROUP BY category
    ORDER BY count DESC
""").show()

print("      Products over $100:")
spark.sql("""
    SELECT name, category, price
    FROM products
    WHERE price > 100
    ORDER BY price DESC
""").show()

# 2.4 DataFrame API operations
print("\n[2.4] DataFrame API operations:")
print("      Price statistics by category:")
df.groupBy("category").agg(
    f.count("*").alias("count"),
    f.round(f.min("price"), 2).alias("min_price"),
    f.round(f.max("price"), 2).alias("max_price"),
    f.round(f.avg("price"), 2).alias("avg_price"),
).orderBy("category").show()

# -----------------------------------------------------------------------------
# PART 3: Integration Pattern - Iceberg + Lance
# -----------------------------------------------------------------------------
print("\n" + "-" * 60)
print("PART 3: Architecture Pattern - Iceberg + Lance")
print("-" * 60)

print("""
Recommended architecture for production:

    Kafka (streaming)
        |
        v
    +-------------------+     +-------------------+
    |    Iceberg        |     |     LanceDB       |
    | (Structured Data) |     | (Embeddings/AI)   |
    +-------------------+     +-------------------+
    | - Transactions    |     | - Vector search   |
    | - Time travel     |     | - Multimodal      |
    | - BI/Analytics    |     | - RAG pipelines   |
    +-------------------+     +-------------------+
            |                         |
            +------------+------------+
                         |
                         v
                  Spark 4.x (Unified Queries)
                         |
            +------------+------------+
            |                         |
            v                         v
    +-------------------+     +-------------------+
    |    PostgreSQL     |     |    SeaweedFS      |
    | (Iceberg Catalog) |     | (S3 Data Store)   |
    +-------------------+     +-------------------+

Example hybrid query pattern:
1. User searches: "wireless audio under $100"
2. Generate embedding for "wireless audio"
3. Lance: Vector search -> top-k product IDs
4. Iceberg: JOIN with product details, inventory, orders
5. Return enriched results with full context
""")

# -----------------------------------------------------------------------------
# CLEANUP
# -----------------------------------------------------------------------------
print("\n[CLEANUP]")
print(f"      Lance data stored at: {LANCE_DIR}")
print("      To clean up: rm -rf {LANCE_DIR}")

spark.stop()
print("\n" + "=" * 60)
print("QUICKSTART COMPLETE")
print("=" * 60)
