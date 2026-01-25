"""
Semantic Text Search with LanceDB
=================================
Demonstrates semantic search capabilities using sentence embeddings.

Features:
- Document ingestion with automatic embedding generation
- Semantic similarity search (find documents by meaning, not keywords)
- Hybrid search (semantic + metadata filters)
- Full-text search comparison

Use Cases:
- Documentation search
- FAQ/Support ticket matching
- Product search by description
- Content recommendation

Usage:
    python scripts/08-semantic-search.py
"""

import os
import sys
import time
from typing import List, Dict, Any

import numpy as np
import lancedb
import pandas as pd

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))
from embeddings import get_embedding_generator

# Configuration
LANCE_PATH = os.environ.get("LANCE_PATH", "/tmp/lance_semantic_search")
USE_MOCK = os.environ.get("USE_MOCK_EMBEDDINGS", "false").lower() == "true"


# =============================================================================
# Sample Data: Technical Documentation
# =============================================================================
DOCUMENTS = [
    # Python
    {
        "id": "py-001",
        "title": "Python List Comprehensions",
        "content": "List comprehensions provide a concise way to create lists in Python. They consist of brackets containing an expression followed by a for clause, then zero or more for or if clauses.",
        "category": "python",
        "tags": ["basics", "lists", "syntax"],
    },
    {
        "id": "py-002",
        "title": "Python Decorators",
        "content": "Decorators are a powerful feature in Python that allows you to modify the behavior of functions or classes. They use the @symbol and are placed above function definitions.",
        "category": "python",
        "tags": ["advanced", "functions", "metaprogramming"],
    },
    {
        "id": "py-003",
        "title": "Python Async/Await",
        "content": "Async and await keywords enable asynchronous programming in Python. They allow you to write concurrent code that can handle many operations without blocking.",
        "category": "python",
        "tags": ["advanced", "concurrency", "async"],
    },
    # Data Engineering
    {
        "id": "de-001",
        "title": "Apache Spark Basics",
        "content": "Apache Spark is a unified analytics engine for large-scale data processing. It provides high-level APIs in Java, Scala, Python and R, and an optimized engine for general execution graphs.",
        "category": "data-engineering",
        "tags": ["spark", "big-data", "distributed"],
    },
    {
        "id": "de-002",
        "title": "Data Lake Architecture",
        "content": "A data lake is a centralized repository that allows you to store all your structured and unstructured data at any scale. You can store data as-is without having to structure it first.",
        "category": "data-engineering",
        "tags": ["architecture", "storage", "big-data"],
    },
    {
        "id": "de-003",
        "title": "Apache Iceberg Tables",
        "content": "Apache Iceberg is an open table format for huge analytic datasets. It provides reliable transactions, schema evolution, and time travel capabilities for data lakes.",
        "category": "data-engineering",
        "tags": ["iceberg", "tables", "lakehouse"],
    },
    # Machine Learning
    {
        "id": "ml-001",
        "title": "Neural Network Fundamentals",
        "content": "Neural networks are computing systems inspired by biological neural networks. They consist of layers of interconnected nodes that process information using connectionist approaches.",
        "category": "machine-learning",
        "tags": ["deep-learning", "neural-networks", "basics"],
    },
    {
        "id": "ml-002",
        "title": "Vector Embeddings",
        "content": "Vector embeddings are dense numerical representations of data like text, images, or audio. They capture semantic meaning and enable similarity search and machine learning operations.",
        "category": "machine-learning",
        "tags": ["embeddings", "nlp", "vectors"],
    },
    {
        "id": "ml-003",
        "title": "RAG Pipeline Design",
        "content": "Retrieval-Augmented Generation combines information retrieval with text generation. It retrieves relevant documents from a knowledge base and uses them to generate accurate responses.",
        "category": "machine-learning",
        "tags": ["rag", "llm", "retrieval"],
    },
    # DevOps
    {
        "id": "do-001",
        "title": "Docker Containers",
        "content": "Docker containers package applications with their dependencies into standardized units. They provide consistency across development, testing, and production environments.",
        "category": "devops",
        "tags": ["docker", "containers", "deployment"],
    },
    {
        "id": "do-002",
        "title": "Kubernetes Orchestration",
        "content": "Kubernetes is a container orchestration platform that automates deployment, scaling, and management of containerized applications across clusters of hosts.",
        "category": "devops",
        "tags": ["kubernetes", "orchestration", "scaling"],
    },
    {
        "id": "do-003",
        "title": "CI/CD Pipelines",
        "content": "Continuous Integration and Continuous Deployment pipelines automate the process of building, testing, and deploying code changes to production environments.",
        "category": "devops",
        "tags": ["ci-cd", "automation", "deployment"],
    },
]


def create_document_table(db, embedding_gen) -> lancedb.table.Table:
    """Create and populate the documents table with embeddings."""
    print("\n[1] Creating document embeddings...")

    # Generate embeddings for all documents
    texts = [f"{doc['title']} {doc['content']}" for doc in DOCUMENTS]
    embeddings = embedding_gen.encode(texts, show_progress=True)

    # Prepare records
    records = []
    for doc, embedding in zip(DOCUMENTS, embeddings):
        record = {
            **doc,
            "tags": ",".join(doc["tags"]),  # Convert list to string for Lance
            "vector": embedding.tolist(),
        }
        records.append(record)

    # Create table
    table = db.create_table("documents", data=records, mode="overwrite")
    print(f"    Created table with {table.count_rows()} documents")

    return table


def semantic_search(
    table: lancedb.table.Table,
    query: str,
    embedding_gen,
    limit: int = 5,
    filter_expr: str = None,
) -> pd.DataFrame:
    """
    Perform semantic search on documents.

    Args:
        table: LanceDB table
        query: Search query text
        embedding_gen: Embedding generator
        limit: Number of results to return
        filter_expr: Optional SQL filter expression

    Returns:
        DataFrame with search results
    """
    # Generate query embedding
    query_vec = embedding_gen.encode_single(query)

    # Build search
    search = table.search(query_vec)

    if filter_expr:
        search = search.where(filter_expr)

    # Execute and return
    results = search.limit(limit).to_pandas()
    return results


def demo_semantic_search(table, embedding_gen):
    """Demonstrate semantic search capabilities."""
    print("\n" + "=" * 60)
    print("SEMANTIC SEARCH DEMO")
    print("=" * 60)

    queries = [
        # Direct matches
        ("How do I create lists in Python?", None),
        ("What is Apache Spark used for?", None),

        # Semantic matches (different words, same meaning)
        ("concurrent programming patterns", None),
        ("machine learning model training", None),

        # With category filter
        ("data storage solutions", "category = 'data-engineering'"),
        ("deployment automation", "category = 'devops'"),

        # Cross-domain queries
        ("how to scale applications", None),
        ("working with big datasets", None),
    ]

    for query, filter_expr in queries:
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")
        if filter_expr:
            print(f"Filter: {filter_expr}")
        print("─" * 60)

        results = semantic_search(table, query, embedding_gen, limit=3, filter_expr=filter_expr)

        for idx, row in results.iterrows():
            score = 1 - row['_distance']  # Convert distance to similarity
            print(f"\n  [{score:.3f}] {row['title']}")
            print(f"          Category: {row['category']}")
            print(f"          {row['content'][:80]}...")


def demo_keyword_vs_semantic(table, embedding_gen):
    """Compare keyword search vs semantic search."""
    print("\n" + "=" * 60)
    print("KEYWORD vs SEMANTIC SEARCH")
    print("=" * 60)

    # Query that benefits from semantic understanding
    query = "how to handle multiple tasks at once"

    print(f"\nQuery: \"{query}\"")
    print("\n[Keyword search would look for: 'multiple', 'tasks', 'once']")
    print("[Semantic search understands: concurrency, parallelism, async]")

    results = semantic_search(table, query, embedding_gen, limit=3)

    print("\nSemantic Search Results:")
    for idx, row in results.iterrows():
        score = 1 - row['_distance']
        print(f"  [{score:.3f}] {row['title']} ({row['category']})")

    # Another example
    query2 = "storing information for analytics"
    print(f"\n{'─' * 40}")
    print(f"Query: \"{query2}\"")

    results2 = semantic_search(table, query2, embedding_gen, limit=3)

    print("\nSemantic Search Results:")
    for idx, row in results2.iterrows():
        score = 1 - row['_distance']
        print(f"  [{score:.3f}] {row['title']} ({row['category']})")


def demo_similarity_clustering(table, embedding_gen):
    """Show document similarity and clustering."""
    print("\n" + "=" * 60)
    print("DOCUMENT SIMILARITY")
    print("=" * 60)

    # Find similar documents to a specific one
    seed_doc = "Apache Iceberg Tables"
    print(f"\nDocuments similar to: \"{seed_doc}\"")

    # Get the seed document's embedding
    seed_results = table.search().where(f"title = '{seed_doc}'").limit(1).to_pandas()
    if len(seed_results) == 0:
        print("  Seed document not found")
        return

    seed_vector = seed_results.iloc[0]['vector']

    # Search for similar (excluding the seed)
    results = table.search(seed_vector).where(f"title != '{seed_doc}'").limit(5).to_pandas()

    print("\nMost similar documents:")
    for idx, row in results.iterrows():
        score = 1 - row['_distance']
        print(f"  [{score:.3f}] {row['title']}")
        print(f"          Category: {row['category']}")


def demo_batch_search(table, embedding_gen):
    """Demonstrate batch search for multiple queries."""
    print("\n" + "=" * 60)
    print("BATCH SEARCH (Multiple Queries)")
    print("=" * 60)

    queries = [
        "Python syntax basics",
        "distributed computing",
        "container deployment",
    ]

    print(f"\nProcessing {len(queries)} queries in batch...")

    # Generate embeddings for all queries at once
    query_embeddings = embedding_gen.encode(queries)

    # Search for each
    for query, query_vec in zip(queries, query_embeddings):
        print(f"\n  Query: \"{query}\"")
        results = table.search(query_vec.tolist()).limit(2).to_pandas()
        for idx, row in results.iterrows():
            score = 1 - row['_distance']
            print(f"    [{score:.3f}] {row['title']}")


def main():
    print("=" * 60)
    print("SEMANTIC TEXT SEARCH WITH LANCEDB")
    print("=" * 60)
    print(f"Lance path: {LANCE_PATH}")
    print(f"Mock embeddings: {USE_MOCK}")

    # Initialize
    os.makedirs(LANCE_PATH, exist_ok=True)
    db = lancedb.connect(LANCE_PATH)

    # Get embedding generator
    embedding_gen = get_embedding_generator(use_mock=USE_MOCK)
    print(f"Embedding model: {embedding_gen.model_name}")
    print(f"Embedding dimension: {embedding_gen.dimension}")

    # Create document table
    table = create_document_table(db, embedding_gen)

    # Run demos
    demo_semantic_search(table, embedding_gen)
    demo_keyword_vs_semantic(table, embedding_gen)
    demo_similarity_clustering(table, embedding_gen)
    demo_batch_search(table, embedding_gen)

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"Data stored at: {LANCE_PATH}")


if __name__ == "__main__":
    main()
