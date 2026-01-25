"""
Integration Tests for LanceDB Components
========================================
Tests for Lance manager, monitoring, multimodal search, and streaming pipelines.

Usage:
    pytest tests/test_lance_integration.py -v
    pytest tests/test_lance_integration.py -v -k "test_manager"
"""

import os
import sys
import time
import tempfile
import shutil
import threading
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_lance_dir():
    """Create temporary directory for Lance data."""
    temp_dir = tempfile.mkdtemp(prefix="lance_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_lock_dir():
    """Create temporary directory for locks."""
    temp_dir = tempfile.mkdtemp(prefix="lance_locks_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_records():
    """Generate sample records with embeddings."""
    np.random.seed(42)
    return [
        {
            "id": f"record_{i}",
            "text": f"Sample text {i}",
            "category": f"cat_{i % 3}",
            "vector": np.random.randn(384).astype(np.float32).tolist(),
        }
        for i in range(10)
    ]


@pytest.fixture
def large_sample_records():
    """Generate larger sample for index testing (256+ rows required)."""
    np.random.seed(42)
    return [
        {
            "id": f"record_{i}",
            "text": f"Sample text {i}",
            "category": f"cat_{i % 5}",
            "vector": np.random.randn(384).astype(np.float32).tolist(),
        }
        for i in range(300)
    ]


# =============================================================================
# LanceDB Basic Tests
# =============================================================================


class TestLanceDBBasic:
    """Basic LanceDB functionality tests."""

    def test_lancedb_import(self):
        """Test that LanceDB can be imported."""
        import lancedb

        assert lancedb is not None

    def test_lancedb_connect(self, temp_lance_dir):
        """Test LanceDB connection."""
        import lancedb

        db = lancedb.connect(temp_lance_dir)
        assert db is not None
        assert len(db.table_names()) == 0

    def test_create_table(self, temp_lance_dir, sample_records):
        """Test table creation."""
        import lancedb

        db = lancedb.connect(temp_lance_dir)
        table = db.create_table("test_table", data=sample_records)

        assert table is not None
        assert table.count_rows() == len(sample_records)
        assert "test_table" in db.table_names()

    def test_vector_search(self, temp_lance_dir, sample_records):
        """Test vector search functionality."""
        import lancedb

        db = lancedb.connect(temp_lance_dir)
        table = db.create_table("search_test", data=sample_records)

        # Search with first record's vector
        query_vec = sample_records[0]["vector"]
        results = table.search(query_vec).limit(5).to_pandas()

        assert len(results) == 5
        assert "_distance" in results.columns
        # First result should be the query itself (distance ~0)
        assert results.iloc[0]["_distance"] < 0.01

    def test_filtered_search(self, temp_lance_dir, sample_records):
        """Test filtered vector search."""
        import lancedb

        db = lancedb.connect(temp_lance_dir)
        table = db.create_table("filter_test", data=sample_records)

        query_vec = sample_records[0]["vector"]
        results = (
            table.search(query_vec).where("category = 'cat_0'").limit(10).to_pandas()
        )

        assert len(results) > 0
        assert all(r == "cat_0" for r in results["category"])

    def test_append_data(self, temp_lance_dir, sample_records):
        """Test appending data to existing table."""
        import lancedb

        db = lancedb.connect(temp_lance_dir)
        table = db.create_table("append_test", data=sample_records[:5])
        initial_count = table.count_rows()

        table.add(sample_records[5:])
        assert table.count_rows() == initial_count + len(sample_records[5:])


# =============================================================================
# Lance Manager Tests
# =============================================================================


class TestLanceManager:
    """Tests for LanceManager production utilities."""

    def test_manager_init(self, temp_lance_dir, temp_lock_dir):
        """Test manager initialization."""
        from lance_manager import LanceManager

        manager = LanceManager(
            lance_path=temp_lance_dir,
            lock_dir=temp_lock_dir,
        )

        assert manager.lance_path == temp_lance_dir
        assert manager.lock_dir == temp_lock_dir
        assert manager.db is not None

    def test_create_table(self, temp_lance_dir, temp_lock_dir, sample_records):
        """Test table creation through manager."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)

        table = manager.create_table("manager_test", sample_records)
        assert table.count_rows() == len(sample_records)

    def test_append_with_locking(self, temp_lance_dir, temp_lock_dir, sample_records):
        """Test append with locking enabled."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        manager.create_table("lock_test", sample_records[:5])

        # Append with lock
        rows = manager.append("lock_test", sample_records[5:], use_lock=True)
        assert rows == len(sample_records[5:])

        # Verify total
        table = manager.get_table("lock_test")
        assert table.count_rows() == len(sample_records)

    def test_concurrent_writes(self, temp_lance_dir, temp_lock_dir):
        """Test concurrent write handling."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)

        # Create initial table
        initial_records = [
            {"id": "init", "text": "initial", "vector": [0.0] * 384}
        ]
        manager.create_table("concurrent_test", initial_records)

        results = []
        errors = []

        def write_records(writer_id: int):
            try:
                records = [
                    {
                        "id": f"writer_{writer_id}_{i}",
                        "text": f"text from writer {writer_id}",
                        "vector": [float(writer_id)] * 384,
                    }
                    for i in range(5)
                ]
                rows = manager.append("concurrent_test", records, use_lock=True)
                results.append(rows)
            except Exception as e:
                errors.append(str(e))

        # Launch concurrent writers
        threads = [threading.Thread(target=write_records, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All writes should succeed
        assert len(errors) == 0
        assert len(results) == 3
        assert all(r == 5 for r in results)

        # Verify total rows
        table = manager.get_table("concurrent_test")
        assert table.count_rows() == 1 + (3 * 5)  # initial + 3 writers * 5 records

    def test_metrics_tracking(self, temp_lance_dir, temp_lock_dir, sample_records):
        """Test metrics are tracked correctly."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        manager.create_table("metrics_test", sample_records)

        manager.append("metrics_test", sample_records, use_lock=True)

        metrics = manager.get_metrics()
        assert metrics["write_count"] >= 1
        assert metrics["error_count"] == 0

    def test_compaction(self, temp_lance_dir, temp_lock_dir, sample_records):
        """Test table compaction."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        manager.create_table("compact_test", sample_records)

        # Add more data in batches to create fragments
        for i in range(3):
            records = [
                {"id": f"batch_{i}_{j}", "text": f"batch {i}", "vector": [0.0] * 384}
                for j in range(5)
            ]
            manager.append("compact_test", records, use_lock=False)

        # Compact
        result = manager.compact("compact_test")
        assert result is not None

    def test_index_creation(self, temp_lance_dir, temp_lock_dir, large_sample_records):
        """Test vector index creation."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        manager.create_table("index_test", large_sample_records)

        # Create index (requires 256+ rows)
        result = manager.create_index("index_test", metric="L2")
        assert result is True

    def test_index_skip_small_table(self, temp_lance_dir, temp_lock_dir, sample_records):
        """Test index creation is skipped for small tables."""
        from lance_manager import LanceManager

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        manager.create_table("small_test", sample_records)

        # Should skip (< 256 rows)
        result = manager.create_index("small_test", metric="L2")
        assert result is False


# =============================================================================
# Lance Monitoring Tests
# =============================================================================


class TestLanceMonitoring:
    """Tests for LanceMonitor observability utilities."""

    def test_monitor_init(self, temp_lance_dir):
        """Test monitor initialization."""
        from lance_monitoring import LanceMonitor

        monitor = LanceMonitor(temp_lance_dir)
        assert monitor.lance_path == temp_lance_dir

    def test_record_query(self, temp_lance_dir, sample_records):
        """Test query metrics recording."""
        import lancedb
        from lance_monitoring import LanceMonitor

        # Create table first
        db = lancedb.connect(temp_lance_dir)
        db.create_table("query_metrics_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        monitor.record_query("query_metrics_test", latency_ms=15.5, result_count=10)

        stats = monitor.get_table_stats("query_metrics_test")
        assert stats["query_count"] == 1

    def test_record_write(self, temp_lance_dir, sample_records):
        """Test write metrics recording."""
        import lancedb
        from lance_monitoring import LanceMonitor

        db = lancedb.connect(temp_lance_dir)
        db.create_table("write_metrics_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        monitor.record_write("write_metrics_test", rows=100, latency_ms=250.0, success=True)

        stats = monitor.get_table_stats("write_metrics_test")
        assert stats["write_count"] == 1
        assert stats["rows_written"] == 100

    def test_health_check_healthy(self, temp_lance_dir, sample_records):
        """Test health check returns healthy status."""
        import lancedb
        from lance_monitoring import LanceMonitor

        db = lancedb.connect(temp_lance_dir)
        db.create_table("health_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        health = monitor.health_check()

        assert health["status"] == "healthy"
        assert "tables" in health
        assert "disk_usage_bytes" in health

    def test_prometheus_metrics_format(self, temp_lance_dir, sample_records):
        """Test Prometheus metrics export format."""
        import lancedb
        from lance_monitoring import LanceMonitor

        db = lancedb.connect(temp_lance_dir)
        db.create_table("prom_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        monitor.record_query("prom_test", latency_ms=10.0, result_count=5)

        metrics = monitor.get_prometheus_metrics()

        assert "lance_table_count" in metrics
        assert "lance_queries_total" in metrics
        assert "# HELP" in metrics
        assert "# TYPE" in metrics

    def test_dashboard_data(self, temp_lance_dir, sample_records):
        """Test dashboard data generation."""
        import lancedb
        from lance_monitoring import LanceMonitor

        db = lancedb.connect(temp_lance_dir)
        db.create_table("dashboard_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        dashboard = monitor.get_dashboard_data()

        assert "summary" in dashboard
        assert "tables" in dashboard
        assert "query_latency" in dashboard

    def test_alert_evaluation(self, temp_lance_dir, sample_records):
        """Test alert evaluation."""
        import lancedb
        from lance_monitoring import LanceMonitor

        db = lancedb.connect(temp_lance_dir)
        db.create_table("alert_test", data=sample_records)

        monitor = LanceMonitor(temp_lance_dir)
        # Record slow query to trigger alert
        monitor.record_query("alert_test", latency_ms=2000.0, result_count=1)

        alerts = monitor.evaluate_alerts()
        # Should have high latency alert
        assert any("latency" in str(a).lower() for a in alerts)


# =============================================================================
# Multimodal Search Tests
# =============================================================================


class TestMultimodalSearch:
    """Tests for unified multimodal search API."""

    def test_search_init(self, temp_lance_dir):
        """Test multimodal search initialization."""
        from multimodal_search import MultimodalSearch

        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)
        assert search.lance_path == temp_lance_dir
        assert search.use_mock is True

    def test_text_search(self, temp_lance_dir):
        """Test text semantic search."""
        from multimodal_search import MultimodalSearch

        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)

        # Create sample data
        docs = [
            {"id": "1", "title": "Python Guide", "content": "Learn Python programming"},
            {"id": "2", "title": "Data Science", "content": "Machine learning basics"},
            {"id": "3", "title": "Web Dev", "content": "Building web applications"},
        ]

        texts = [f"{d['title']} {d['content']}" for d in docs]
        embeddings = search.text_encoder.encode(texts)
        for doc, emb in zip(docs, embeddings):
            doc["vector"] = emb.tolist()

        search.db.create_table("text_search_test", data=docs, mode="overwrite")

        # Search
        response = search.text_search("machine learning", "text_search_test", limit=3)

        assert response.mode.value == "text"
        assert len(response.results) <= 3
        assert response.execution_time_ms > 0

    def test_hybrid_search(self, temp_lance_dir):
        """Test hybrid search with filters."""
        from multimodal_search import MultimodalSearch

        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)

        # Create sample data with metadata
        products = [
            {"id": "1", "name": "Running Shoe", "price": 99.99, "in_stock": True},
            {"id": "2", "name": "Hiking Boot", "price": 149.99, "in_stock": True},
            {"id": "3", "name": "Sandal", "price": 49.99, "in_stock": False},
        ]

        texts = [p["name"] for p in products]
        embeddings = search.text_encoder.encode(texts)
        for prod, emb in zip(products, embeddings):
            prod["vector"] = emb.tolist()

        search.db.create_table("hybrid_test", data=products, mode="overwrite")

        # Hybrid search with price filter
        response = search.hybrid_search(
            "comfortable shoes",
            "hybrid_test",
            filters={"price_max": 100, "in_stock": True},
            limit=3,
        )

        assert response.mode.value == "hybrid"
        assert response.filters_applied == {"price_max": 100, "in_stock": True}

    def test_similarity_search(self, temp_lance_dir):
        """Test item-to-item similarity search."""
        from multimodal_search import MultimodalSearch

        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)

        # Create sample data
        items = [
            {"id": "item1", "name": "Blue Shirt", "category": "clothing"},
            {"id": "item2", "name": "Red Shirt", "category": "clothing"},
            {"id": "item3", "name": "Blue Pants", "category": "clothing"},
        ]

        texts = [i["name"] for i in items]
        embeddings = search.text_encoder.encode(texts)
        for item, emb in zip(items, embeddings):
            item["vector"] = emb.tolist()

        search.db.create_table("similarity_test", data=items, mode="overwrite")

        # Find similar to item1
        response = search.similarity_search("item1", "similarity_test", limit=2)

        assert len(response.results) == 2
        assert all(r.id != "item1" for r in response.results)


# =============================================================================
# Embeddings Tests
# =============================================================================


class TestEmbeddings:
    """Tests for embedding generation."""

    def test_mock_embedding_generator(self):
        """Test mock embedding generator."""
        from embeddings import get_embedding_generator

        gen = get_embedding_generator(use_mock=True)

        assert gen.model_name == "mock-embeddings"
        assert gen.dimension == 384

    def test_mock_encode_single(self):
        """Test single text encoding."""
        from embeddings import get_embedding_generator

        gen = get_embedding_generator(use_mock=True)
        vec = gen.encode_single("test text")

        assert len(vec) == 384
        assert isinstance(vec, np.ndarray)
        # Normalized vector
        assert abs(np.linalg.norm(vec) - 1.0) < 0.01

    def test_mock_encode_batch(self):
        """Test batch text encoding."""
        from embeddings import get_embedding_generator

        gen = get_embedding_generator(use_mock=True)
        texts = ["text one", "text two", "text three"]
        vecs = gen.encode(texts)

        assert vecs.shape == (3, 384)

    def test_deterministic_mock_embeddings(self):
        """Test that mock embeddings are deterministic."""
        from embeddings import get_embedding_generator

        gen = get_embedding_generator(use_mock=True)

        vec1 = gen.encode_single("test")
        vec2 = gen.encode_single("test")

        np.testing.assert_array_almost_equal(vec1, vec2)

    def test_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings."""
        from embeddings import get_embedding_generator

        gen = get_embedding_generator(use_mock=True)

        vec1 = gen.encode_single("hello world")
        vec2 = gen.encode_single("goodbye universe")

        # Should not be equal
        assert not np.allclose(vec1, vec2)


# =============================================================================
# End-to-End Tests
# =============================================================================


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline(self, temp_lance_dir, temp_lock_dir):
        """Test full write → search pipeline."""
        from lance_manager import LanceManager
        from lance_monitoring import LanceMonitor
        from multimodal_search import MultimodalSearch

        # Initialize components
        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        monitor = LanceMonitor(temp_lance_dir)
        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)

        # Create data with embeddings
        products = [
            {"id": "p1", "name": "Running Shoes", "price": 89.99},
            {"id": "p2", "name": "Training Shoes", "price": 79.99},
            {"id": "p3", "name": "Hiking Boots", "price": 129.99},
        ]

        texts = [p["name"] for p in products]
        embeddings = search.text_encoder.encode(texts)
        for prod, emb in zip(products, embeddings):
            prod["vector"] = emb.tolist()

        # Write through manager
        manager.create_table("e2e_products", products)
        monitor.record_write("e2e_products", rows=3, latency_ms=100, success=True)

        # Search
        response = search.text_search("running", "e2e_products", limit=3)
        monitor.record_query(
            "e2e_products", latency_ms=response.execution_time_ms, result_count=len(response.results)
        )

        # Verify
        assert len(response.results) > 0
        health = monitor.health_check()
        assert health["status"] == "healthy"

        # Metrics
        metrics = monitor.get_prometheus_metrics()
        assert "lance_queries_total" in metrics

    def test_concurrent_read_write(self, temp_lance_dir, temp_lock_dir):
        """Test concurrent reads and writes."""
        from lance_manager import LanceManager
        from multimodal_search import MultimodalSearch

        manager = LanceManager(lance_path=temp_lance_dir, lock_dir=temp_lock_dir)
        search = MultimodalSearch(temp_lance_dir, use_mock_embeddings=True)

        # Initial data
        initial = [
            {"id": f"init_{i}", "text": f"initial {i}", "vector": [0.1] * 384}
            for i in range(10)
        ]
        manager.create_table("concurrent_rw", initial)

        read_results = []
        write_results = []
        errors = []

        def reader():
            try:
                for _ in range(5):
                    response = search.text_search("initial", "concurrent_rw", limit=5)
                    read_results.append(len(response.results))
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"reader: {e}")

        def writer():
            try:
                for i in range(3):
                    records = [
                        {"id": f"new_{i}_{j}", "text": f"new {i}", "vector": [0.2] * 384}
                        for j in range(5)
                    ]
                    manager.append("concurrent_rw", records, use_lock=True)
                    write_results.append(5)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"writer: {e}")

        # Launch concurrent operations
        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)

        reader_thread.start()
        writer_thread.start()

        reader_thread.join()
        writer_thread.join()

        # Verify no errors
        assert len(errors) == 0
        assert len(read_results) == 5
        assert len(write_results) == 3


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
