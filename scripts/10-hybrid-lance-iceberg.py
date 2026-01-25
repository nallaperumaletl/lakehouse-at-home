"""
Hybrid Search: Lance + Iceberg Integration
==========================================
Demonstrates combining LanceDB vector search with Iceberg structured data
for powerful hybrid queries.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                      User Query                              │
    │            "Find running shoes under $100"                   │
    └─────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
    ┌───────────────────────┐     ┌───────────────────────┐
    │   LanceDB (Vectors)   │     │   Iceberg (Metadata)   │
    │  "running shoes" →    │     │   price < 100          │
    │   embedding search    │     │   in_stock = true      │
    └───────────────────────┘     └───────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    PySpark Join                              │
    │         Combine vector similarity with business rules        │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    Ranked Results                            │
    │      Products matching semantic intent AND business rules    │
    └─────────────────────────────────────────────────────────────┘

Use Cases:
- E-commerce: semantic product search with inventory/price filters
- Document search: find relevant docs with access control
- Recommendation: similar items with business constraints

Usage:
    python scripts/10-hybrid-lance-iceberg.py
"""

import os
import sys
from datetime import datetime, timedelta
import random

import numpy as np
import lancedb
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, BooleanType, TimestampType

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))
from embeddings import get_embedding_generator

# Configuration
LANCE_PATH = os.environ.get("LANCE_PATH", "/tmp/lance_hybrid")
USE_MOCK = os.environ.get("USE_MOCK_EMBEDDINGS", "true").lower() == "true"


# =============================================================================
# Sample Product Catalog
# =============================================================================
PRODUCTS = [
    # Running & Sports
    {"id": "P001", "name": "ProRunner Elite", "description": "Lightweight running shoes with responsive cushioning and breathable mesh upper for marathon training", "category": "footwear", "subcategory": "running"},
    {"id": "P002", "name": "TrailBlazer X", "description": "Rugged trail running shoes with aggressive tread pattern and rock protection plate", "category": "footwear", "subcategory": "running"},
    {"id": "P003", "name": "SpeedLite Racer", "description": "Competition racing flats with carbon fiber plate for maximum speed", "category": "footwear", "subcategory": "running"},
    {"id": "P004", "name": "ComfortRun Daily", "description": "Everyday running shoes with plush cushioning for comfortable long runs", "category": "footwear", "subcategory": "running"},

    # Training
    {"id": "P005", "name": "GymFlex Training", "description": "Versatile cross-training shoes for weightlifting and HIIT workouts", "category": "footwear", "subcategory": "training"},
    {"id": "P006", "name": "PowerLift Pro", "description": "Stable weightlifting shoes with raised heel and solid base", "category": "footwear", "subcategory": "training"},

    # Casual
    {"id": "P007", "name": "StreetStyle Sneaker", "description": "Casual lifestyle sneakers with retro design and all-day comfort", "category": "footwear", "subcategory": "casual"},
    {"id": "P008", "name": "Urban Walker", "description": "Comfortable walking shoes for city exploration and daily wear", "category": "footwear", "subcategory": "casual"},

    # Apparel
    {"id": "P009", "name": "DryFit Running Shirt", "description": "Moisture-wicking running shirt with reflective elements for visibility", "category": "apparel", "subcategory": "tops"},
    {"id": "P010", "name": "FlexMove Shorts", "description": "Lightweight running shorts with built-in liner and zip pocket", "category": "apparel", "subcategory": "bottoms"},
    {"id": "P011", "name": "ThermoRun Jacket", "description": "Insulated running jacket for cold weather training with wind protection", "category": "apparel", "subcategory": "outerwear"},
    {"id": "P012", "name": "CompressionTight Pro", "description": "Performance compression tights for muscle support and recovery", "category": "apparel", "subcategory": "bottoms"},

    # Accessories
    {"id": "P013", "name": "HydroFlask Runner", "description": "Handheld water bottle with adjustable strap for hydration on the run", "category": "accessories", "subcategory": "hydration"},
    {"id": "P014", "name": "GPS Sports Watch", "description": "Advanced GPS watch with heart rate monitoring and training metrics", "category": "accessories", "subcategory": "electronics"},
    {"id": "P015", "name": "WirelessBuds Sport", "description": "Sweat-proof wireless earbuds with secure fit for intense workouts", "category": "accessories", "subcategory": "electronics"},
]


def generate_inventory_data():
    """Generate simulated inventory/business data (would be in Iceberg in production)."""
    random.seed(42)
    now = datetime.now()

    inventory = []
    for product in PRODUCTS:
        inventory.append({
            "product_id": product["id"],
            "price": round(random.uniform(29.99, 199.99), 2),
            "sale_price": round(random.uniform(19.99, 149.99), 2) if random.random() > 0.6 else None,
            "in_stock": random.random() > 0.2,
            "stock_quantity": random.randint(0, 100),
            "rating": round(random.uniform(3.5, 5.0), 1),
            "review_count": random.randint(10, 500),
            "last_restocked": now - timedelta(days=random.randint(1, 30)),
            "is_new": random.random() > 0.7,
            "is_bestseller": random.random() > 0.8,
        })

    return inventory


def create_lance_table(db, embedding_gen):
    """Create Lance table with product embeddings."""
    print("\n[1] Creating Lance product embeddings...")

    # Generate embeddings
    texts = [f"{p['name']} {p['description']}" for p in PRODUCTS]
    embeddings = embedding_gen.encode(texts)

    # Create records
    records = []
    for product, embedding in zip(PRODUCTS, embeddings):
        records.append({
            "product_id": product["id"],
            "name": product["name"],
            "description": product["description"],
            "category": product["category"],
            "subcategory": product["subcategory"],
            "vector": embedding.tolist(),
        })

    table = db.create_table("products", data=records, mode="overwrite")
    print(f"    Lance table created: {table.count_rows()} products")
    return table


def create_spark_inventory(spark, inventory_data):
    """Create Spark DataFrame for inventory (simulating Iceberg table)."""
    print("\n[2] Creating Spark inventory DataFrame...")

    # Convert to Spark DataFrame
    pdf = pd.DataFrame(inventory_data)
    df = spark.createDataFrame(pdf)

    # Register as temp view (in production, this would be an Iceberg table)
    df.createOrReplaceTempView("inventory")

    print(f"    Inventory DataFrame created: {df.count()} records")
    return df


def hybrid_search(
    lance_table,
    spark,
    query: str,
    embedding_gen,
    filters: dict = None,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Perform hybrid search combining vector similarity with business filters.

    Args:
        lance_table: LanceDB table with product embeddings
        spark: SparkSession
        query: Search query text
        embedding_gen: Embedding generator
        filters: Dict of business filters (price_max, in_stock, etc.)
        limit: Number of results

    Returns:
        DataFrame with combined results
    """
    filters = filters or {}

    # Step 1: Vector search in Lance
    query_vec = embedding_gen.encode_single(query)
    lance_results = lance_table.search(query_vec).limit(limit * 2).to_pandas()

    # Add similarity score
    lance_results['similarity'] = 1 - lance_results['_distance']

    # Step 2: Create Spark DataFrame from Lance results
    lance_df = spark.createDataFrame(
        lance_results[['product_id', 'name', 'description', 'category', 'subcategory', 'similarity']]
    )

    # Step 3: Join with inventory data
    joined = lance_df.join(
        spark.table("inventory"),
        lance_df.product_id == spark.table("inventory").product_id,
        "inner"
    ).drop(spark.table("inventory").product_id)

    # Step 4: Apply business filters
    if filters.get("price_max"):
        joined = joined.filter(
            f.coalesce(f.col("sale_price"), f.col("price")) <= filters["price_max"]
        )

    if filters.get("in_stock"):
        joined = joined.filter(f.col("in_stock") == True)

    if filters.get("min_rating"):
        joined = joined.filter(f.col("rating") >= filters["min_rating"])

    if filters.get("category"):
        joined = joined.filter(f.col("category") == filters["category"])

    if filters.get("is_new"):
        joined = joined.filter(f.col("is_new") == True)

    if filters.get("is_bestseller"):
        joined = joined.filter(f.col("is_bestseller") == True)

    # Step 5: Rank by combined score (similarity + business metrics)
    ranked = joined.withColumn(
        "score",
        f.col("similarity") * 0.7 +  # Semantic relevance
        (f.col("rating") / 5.0) * 0.2 +  # Rating boost
        f.when(f.col("is_bestseller"), 0.1).otherwise(0)  # Bestseller boost
    ).orderBy(f.col("score").desc())

    return ranked.limit(limit).toPandas()


def demo_basic_hybrid(lance_table, spark, embedding_gen):
    """Demonstrate basic hybrid search."""
    print("\n" + "=" * 60)
    print("BASIC HYBRID SEARCH")
    print("=" * 60)

    query = "comfortable shoes for long distance running"
    print(f"\nQuery: \"{query}\"")
    print("Filters: in_stock=True, price_max=150")

    results = hybrid_search(
        lance_table, spark, query, embedding_gen,
        filters={"in_stock": True, "price_max": 150},
        limit=5
    )

    print("\nResults:")
    print("-" * 80)
    for _, row in results.iterrows():
        price = row['sale_price'] if pd.notna(row['sale_price']) else row['price']
        print(f"  [{row['score']:.3f}] {row['name']}")
        print(f"          ${price:.2f} | Rating: {row['rating']} | Stock: {row['stock_quantity']}")
        print(f"          {row['description'][:60]}...")
        print()


def demo_filtered_search(lance_table, spark, embedding_gen):
    """Demonstrate search with various filters."""
    print("\n" + "=" * 60)
    print("FILTERED HYBRID SEARCH")
    print("=" * 60)

    scenarios = [
        {
            "name": "Budget Running Gear",
            "query": "running equipment for beginners",
            "filters": {"price_max": 75, "in_stock": True},
        },
        {
            "name": "Top-Rated Products",
            "query": "best workout clothes",
            "filters": {"min_rating": 4.5, "in_stock": True},
        },
        {
            "name": "New Arrivals",
            "query": "latest sports shoes",
            "filters": {"is_new": True},
        },
        {
            "name": "Bestsellers Only",
            "query": "popular fitness accessories",
            "filters": {"is_bestseller": True},
        },
    ]

    for scenario in scenarios:
        print(f"\n{'─' * 60}")
        print(f"Scenario: {scenario['name']}")
        print(f"Query: \"{scenario['query']}\"")
        print(f"Filters: {scenario['filters']}")
        print("─" * 60)

        results = hybrid_search(
            lance_table, spark, scenario['query'], embedding_gen,
            filters=scenario['filters'],
            limit=3
        )

        if len(results) == 0:
            print("  No results match the criteria")
            continue

        for _, row in results.iterrows():
            price = row['sale_price'] if pd.notna(row['sale_price']) else row['price']
            badges = []
            if row.get('is_new'):
                badges.append("NEW")
            if row.get('is_bestseller'):
                badges.append("BESTSELLER")
            badge_str = f" [{', '.join(badges)}]" if badges else ""

            print(f"  [{row['score']:.3f}] {row['name']}{badge_str}")
            print(f"          ${price:.2f} | {row['rating']}★ ({row['review_count']} reviews)")


def demo_comparison(lance_table, spark, embedding_gen):
    """Compare vector-only vs hybrid search."""
    print("\n" + "=" * 60)
    print("VECTOR-ONLY vs HYBRID SEARCH")
    print("=" * 60)

    query = "shoes for training"

    # Vector-only search
    print(f"\nQuery: \"{query}\"")
    print("\n[Vector-Only Search (no filters)]")

    query_vec = embedding_gen.encode_single(query)
    vector_results = lance_table.search(query_vec).limit(5).to_pandas()

    for _, row in vector_results.iterrows():
        sim = 1 - row['_distance']
        print(f"  [{sim:.3f}] {row['name']}")

    # Hybrid search
    print("\n[Hybrid Search (in_stock + price < $100)]")

    hybrid_results = hybrid_search(
        lance_table, spark, query, embedding_gen,
        filters={"in_stock": True, "price_max": 100},
        limit=5
    )

    for _, row in hybrid_results.iterrows():
        price = row['sale_price'] if pd.notna(row['sale_price']) else row['price']
        stock_status = "✓" if row['in_stock'] else "✗"
        print(f"  [{row['score']:.3f}] {row['name']} | ${price:.2f} | Stock: {stock_status}")


def demo_analytics_query(spark):
    """Show how to combine search with analytics."""
    print("\n" + "=" * 60)
    print("SEARCH + ANALYTICS")
    print("=" * 60)
    print("Combining search results with business analytics")

    # Category summary
    print("\n[Inventory Summary by Category]")
    spark.sql("""
        SELECT
            p.category,
            COUNT(*) as product_count,
            ROUND(AVG(i.price), 2) as avg_price,
            ROUND(AVG(i.rating), 2) as avg_rating,
            SUM(CASE WHEN i.in_stock THEN 1 ELSE 0 END) as in_stock_count
        FROM inventory i
        JOIN (SELECT DISTINCT product_id, category FROM products_view) p
            ON i.product_id = p.product_id
        GROUP BY p.category
        ORDER BY product_count DESC
    """).show()


def main():
    print("=" * 60)
    print("HYBRID SEARCH: LANCE + ICEBERG")
    print("=" * 60)
    print(f"Lance path: {LANCE_PATH}")
    print(f"Mock embeddings: {USE_MOCK}")

    # Initialize Lance
    os.makedirs(LANCE_PATH, exist_ok=True)
    db = lancedb.connect(LANCE_PATH)

    # Initialize embedding generator
    embedding_gen = get_embedding_generator(use_mock=USE_MOCK)
    print(f"Embedding model: {embedding_gen.model_name}")

    # Create Lance table
    lance_table = create_lance_table(db, embedding_gen)

    # Initialize Spark
    print("\n[3] Initializing Spark...")
    spark = SparkSession.builder.appName("HybridSearch").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    # Generate and load inventory data
    inventory_data = generate_inventory_data()
    create_spark_inventory(spark, inventory_data)

    # Create products view for analytics
    products_pdf = pd.DataFrame([
        {"product_id": p["id"], "category": p["category"], "subcategory": p["subcategory"]}
        for p in PRODUCTS
    ])
    spark.createDataFrame(products_pdf).createOrReplaceTempView("products_view")

    # Run demos
    demo_basic_hybrid(lance_table, spark, embedding_gen)
    demo_filtered_search(lance_table, spark, embedding_gen)
    demo_comparison(lance_table, spark, embedding_gen)
    demo_analytics_query(spark)

    # Cleanup
    spark.stop()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"Data stored at: {LANCE_PATH}")
    print("\nIn production, the inventory data would be stored in Iceberg tables")
    print("with full ACID transactions, time travel, and schema evolution.")


if __name__ == "__main__":
    main()
