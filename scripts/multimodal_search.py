"""
Unified Multimodal Search API
=============================
A unified API for multimodal search across text, images, and structured data.

This module provides a clean interface for:
- Text semantic search
- Image similarity search
- Hybrid search (vector + metadata)
- Cross-modal search (text-to-image, image-to-text)

Usage:
    from multimodal_search import MultimodalSearch

    search = MultimodalSearch("/path/to/lance")

    # Text search
    results = search.text_search("running shoes", limit=10)

    # Image search
    results = search.image_search("sunset beach", limit=10)

    # Hybrid search
    results = search.hybrid_search(
        query="comfortable shoes",
        filters={"price_max": 100, "in_stock": True}
    )
"""

import os
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

import numpy as np
import lancedb
import pandas as pd


class SearchMode(Enum):
    """Search mode enumeration."""
    TEXT = "text"
    IMAGE = "image"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """Individual search result."""
    id: str
    score: float
    content: Dict[str, Any]
    source: str  # 'lance', 'iceberg', or 'hybrid'


@dataclass
class SearchResponse:
    """Search response containing results and metadata."""
    query: str
    mode: SearchMode
    results: List[SearchResult]
    total_found: int
    filters_applied: Dict[str, Any]
    execution_time_ms: float


class MultimodalSearch:
    """
    Unified multimodal search interface.

    Provides semantic search across text, images, and structured data
    using LanceDB for vector search and optional Spark/Iceberg for
    structured data filtering.
    """

    def __init__(
        self,
        lance_path: str,
        use_mock_embeddings: bool = True,
        text_model: str = "all-MiniLM-L6-v2",
        image_model: str = "openai/clip-vit-base-patch32",
    ):
        """
        Initialize the multimodal search engine.

        Args:
            lance_path: Path to LanceDB storage
            use_mock_embeddings: Use mock embeddings for testing
            text_model: Sentence transformer model for text
            image_model: CLIP model for images
        """
        self.lance_path = lance_path
        self.use_mock = use_mock_embeddings
        self.text_model_name = text_model
        self.image_model_name = image_model

        # Lazy-loaded components
        self._db = None
        self._text_encoder = None
        self._image_encoder = None

    @property
    def db(self) -> lancedb.DBConnection:
        """Get LanceDB connection."""
        if self._db is None:
            os.makedirs(self.lance_path, exist_ok=True)
            self._db = lancedb.connect(self.lance_path)
        return self._db

    @property
    def text_encoder(self):
        """Get text embedding encoder."""
        if self._text_encoder is None:
            from embeddings import get_embedding_generator
            self._text_encoder = get_embedding_generator(use_mock=self.use_mock)
        return self._text_encoder

    @property
    def image_encoder(self):
        """Get image/CLIP embedding encoder."""
        if self._image_encoder is None:
            # Use mock CLIP encoder
            self._image_encoder = MockCLIPEncoder(dimension=512)
        return self._image_encoder

    def list_tables(self) -> List[str]:
        """List available tables in LanceDB."""
        return self.db.table_names()

    def get_table(self, name: str) -> lancedb.table.Table:
        """Get a LanceDB table by name."""
        return self.db.open_table(name)

    def text_search(
        self,
        query: str,
        table: str,
        limit: int = 10,
        filter_expr: str = None,
    ) -> SearchResponse:
        """
        Perform semantic text search.

        Args:
            query: Search query text
            table: Table name to search
            limit: Maximum results
            filter_expr: Optional SQL filter expression

        Returns:
            SearchResponse with results
        """
        import time
        start = time.time()

        # Generate query embedding
        query_vec = self.text_encoder.encode_single(query)

        # Search
        tbl = self.get_table(table)
        search = tbl.search(query_vec)

        if filter_expr:
            search = search.where(filter_expr)

        results_df = search.limit(limit).to_pandas()

        # Convert to SearchResult objects
        results = []
        for _, row in results_df.iterrows():
            result = SearchResult(
                id=str(row.get('id', row.name)),
                score=float(1 - row['_distance']),
                content={k: v for k, v in row.items() if k not in ['vector', '_distance']},
                source='lance'
            )
            results.append(result)

        execution_time = (time.time() - start) * 1000

        return SearchResponse(
            query=query,
            mode=SearchMode.TEXT,
            results=results,
            total_found=len(results),
            filters_applied={"filter_expr": filter_expr} if filter_expr else {},
            execution_time_ms=execution_time,
        )

    def image_search(
        self,
        query: str,
        table: str,
        limit: int = 10,
        filter_expr: str = None,
    ) -> SearchResponse:
        """
        Perform text-to-image search using CLIP embeddings.

        Args:
            query: Text description of desired images
            table: Table name with image embeddings
            limit: Maximum results
            filter_expr: Optional SQL filter expression

        Returns:
            SearchResponse with results
        """
        import time
        start = time.time()

        # Generate query embedding using CLIP text encoder
        query_vec = self.image_encoder.encode_text([query])[0]

        # Search
        tbl = self.get_table(table)
        search = tbl.search(query_vec.tolist())

        if filter_expr:
            search = search.where(filter_expr)

        results_df = search.limit(limit).to_pandas()

        # Convert to SearchResult objects
        results = []
        for _, row in results_df.iterrows():
            result = SearchResult(
                id=str(row.get('id', row.name)),
                score=float(1 - row['_distance']),
                content={k: v for k, v in row.items() if k not in ['vector', '_distance']},
                source='lance'
            )
            results.append(result)

        execution_time = (time.time() - start) * 1000

        return SearchResponse(
            query=query,
            mode=SearchMode.IMAGE,
            results=results,
            total_found=len(results),
            filters_applied={"filter_expr": filter_expr} if filter_expr else {},
            execution_time_ms=execution_time,
        )

    def similarity_search(
        self,
        item_id: str,
        table: str,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Find similar items based on an existing item's embedding.

        Args:
            item_id: ID of the source item
            table: Table name
            limit: Maximum results

        Returns:
            SearchResponse with similar items
        """
        import time
        start = time.time()

        tbl = self.get_table(table)

        # Get source item
        source = tbl.search().where(f"id = '{item_id}'").limit(1).to_pandas()
        if len(source) == 0:
            raise ValueError(f"Item not found: {item_id}")

        source_vec = source.iloc[0]['vector']

        # Search for similar
        results_df = tbl.search(source_vec).where(f"id != '{item_id}'").limit(limit).to_pandas()

        # Convert to SearchResult objects
        results = []
        for _, row in results_df.iterrows():
            result = SearchResult(
                id=str(row.get('id', row.name)),
                score=float(1 - row['_distance']),
                content={k: v for k, v in row.items() if k not in ['vector', '_distance']},
                source='lance'
            )
            results.append(result)

        execution_time = (time.time() - start) * 1000

        return SearchResponse(
            query=f"similar_to:{item_id}",
            mode=SearchMode.TEXT,
            results=results,
            total_found=len(results),
            filters_applied={},
            execution_time_ms=execution_time,
        )

    def hybrid_search(
        self,
        query: str,
        table: str,
        filters: Dict[str, Any] = None,
        limit: int = 10,
        vector_weight: float = 0.7,
    ) -> SearchResponse:
        """
        Perform hybrid search combining vector similarity with metadata filters.

        Args:
            query: Search query text
            table: Table name
            filters: Dict of filters (e.g., {"price_max": 100, "category": "shoes"})
            limit: Maximum results
            vector_weight: Weight for vector similarity (0-1)

        Returns:
            SearchResponse with results
        """
        import time
        start = time.time()

        filters = filters or {}

        # Generate query embedding
        query_vec = self.text_encoder.encode_single(query)

        # Build filter expression
        filter_parts = []
        for key, value in filters.items():
            if key.endswith("_max"):
                field = key[:-4]
                filter_parts.append(f"{field} <= {value}")
            elif key.endswith("_min"):
                field = key[:-4]
                filter_parts.append(f"{field} >= {value}")
            elif isinstance(value, bool):
                filter_parts.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                filter_parts.append(f"{key} = '{value}'")
            else:
                filter_parts.append(f"{key} = {value}")

        filter_expr = " AND ".join(filter_parts) if filter_parts else None

        # Search
        tbl = self.get_table(table)
        search = tbl.search(query_vec)

        if filter_expr:
            search = search.where(filter_expr)

        results_df = search.limit(limit).to_pandas()

        # Convert to SearchResult objects
        results = []
        for _, row in results_df.iterrows():
            result = SearchResult(
                id=str(row.get('id', row.name)),
                score=float(1 - row['_distance']),
                content={k: v for k, v in row.items() if k not in ['vector', '_distance']},
                source='hybrid'
            )
            results.append(result)

        execution_time = (time.time() - start) * 1000

        return SearchResponse(
            query=query,
            mode=SearchMode.HYBRID,
            results=results,
            total_found=len(results),
            filters_applied=filters,
            execution_time_ms=execution_time,
        )

    def create_index(self, table: str, metric: str = "L2", num_partitions: int = 256):
        """
        Create vector index on a table for faster search.

        Args:
            table: Table name
            metric: Distance metric ("L2", "cosine", "dot")
            num_partitions: Number of IVF partitions
        """
        tbl = self.get_table(table)
        row_count = tbl.count_rows()

        if row_count < 256:
            print(f"Skipping index: need 256+ rows, have {row_count}")
            return

        tbl.create_index(
            metric=metric,
            num_partitions=min(num_partitions, row_count // 10),
            num_sub_vectors=16,
            replace=True,
        )
        print(f"Index created on {table}")


class MockCLIPEncoder:
    """Mock CLIP encoder for testing."""

    def __init__(self, dimension: int = 512):
        self.dimension = dimension
        self.model_name = "mock-clip"

    def encode_text(self, texts: List[str]) -> np.ndarray:
        """Generate mock text embeddings."""
        embeddings = []
        for text in texts:
            np.random.seed(hash(text) % (2**32))
            vec = np.random.randn(self.dimension).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            embeddings.append(vec)
        return np.array(embeddings)

    def encode_image(self, images: List[Any]) -> np.ndarray:
        """Generate mock image embeddings."""
        embeddings = []
        for img in images:
            np.random.seed(hash(str(img)) % (2**32))
            vec = np.random.randn(self.dimension).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            embeddings.append(vec)
        return np.array(embeddings)


def print_results(response: SearchResponse):
    """Pretty print search results."""
    print(f"\nQuery: \"{response.query}\"")
    print(f"Mode: {response.mode.value}")
    print(f"Found: {response.total_found} results in {response.execution_time_ms:.1f}ms")

    if response.filters_applied:
        print(f"Filters: {response.filters_applied}")

    print("-" * 60)
    for i, result in enumerate(response.results, 1):
        print(f"\n{i}. [{result.score:.3f}] {result.id}")
        for key, value in result.content.items():
            if key in ['name', 'title', 'description', 'category']:
                if isinstance(value, str) and len(value) > 60:
                    value = value[:60] + "..."
                print(f"   {key}: {value}")


# Demo
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    print("=" * 60)
    print("MULTIMODAL SEARCH API DEMO")
    print("=" * 60)

    # Initialize
    search = MultimodalSearch("/tmp/lance_multimodal", use_mock_embeddings=True)

    # Create sample data
    print("\nCreating sample data...")

    sample_docs = [
        {"id": "doc1", "title": "Python Basics", "content": "Introduction to Python programming", "category": "programming"},
        {"id": "doc2", "title": "Data Science Guide", "content": "Machine learning and data analysis", "category": "data"},
        {"id": "doc3", "title": "Web Development", "content": "Building modern web applications", "category": "programming"},
        {"id": "doc4", "title": "Cloud Computing", "content": "AWS and cloud infrastructure", "category": "infrastructure"},
    ]

    # Add embeddings
    texts = [f"{d['title']} {d['content']}" for d in sample_docs]
    embeddings = search.text_encoder.encode(texts)

    for doc, emb in zip(sample_docs, embeddings):
        doc['vector'] = emb.tolist()

    # Create table
    table = search.db.create_table("demo_docs", data=sample_docs, mode="overwrite")
    print(f"Created table with {table.count_rows()} documents")

    # Demo searches
    print("\n" + "=" * 60)
    print("TEXT SEARCH")
    print("=" * 60)

    response = search.text_search("machine learning data", "demo_docs", limit=3)
    print_results(response)

    print("\n" + "=" * 60)
    print("FILTERED SEARCH")
    print("=" * 60)

    response = search.text_search(
        "programming tutorial",
        "demo_docs",
        limit=3,
        filter_expr="category = 'programming'"
    )
    print_results(response)

    print("\n" + "=" * 60)
    print("SIMILARITY SEARCH")
    print("=" * 60)

    response = search.similarity_search("doc1", "demo_docs", limit=3)
    print_results(response)

    print("\n" + "=" * 60)
    print("API DEMO COMPLETE")
    print("=" * 60)
