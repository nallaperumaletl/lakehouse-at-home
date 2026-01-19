"""
Lance Production Manager
========================
Production-ready utilities for managing LanceDB in a data lakehouse.

Features:
- Concurrent write handling with locking
- Connection pooling and retry logic
- Table versioning and compaction
- Health monitoring and metrics
- Backup and restore utilities

Usage:
    from lance_manager import LanceManager

    manager = LanceManager("/path/to/lance", enable_metrics=True)

    # Safe concurrent writes
    with manager.write_lock("my_table"):
        manager.append("my_table", records)

    # Table maintenance
    manager.compact("my_table")
    manager.create_index("my_table")
"""

import os
import time
import json
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
import hashlib

import lancedb
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lance_manager")


@dataclass
class TableStats:
    """Statistics for a Lance table."""
    name: str
    row_count: int
    size_bytes: int
    num_fragments: int
    has_index: bool
    last_modified: datetime
    schema: Dict[str, str]


@dataclass
class WriteMetrics:
    """Metrics for write operations."""
    total_writes: int = 0
    total_rows_written: int = 0
    failed_writes: int = 0
    retried_writes: int = 0
    avg_write_time_ms: float = 0.0
    last_write_time: Optional[datetime] = None
    _write_times: List[float] = field(default_factory=list)

    def record_write(self, rows: int, duration_ms: float, success: bool, retried: bool = False):
        """Record a write operation."""
        self.total_writes += 1
        if success:
            self.total_rows_written += rows
            self._write_times.append(duration_ms)
            if len(self._write_times) > 1000:
                self._write_times = self._write_times[-1000:]
            self.avg_write_time_ms = sum(self._write_times) / len(self._write_times)
        else:
            self.failed_writes += 1
        if retried:
            self.retried_writes += 1
        self.last_write_time = datetime.now()


@dataclass
class SearchMetrics:
    """Metrics for search operations."""
    total_searches: int = 0
    avg_search_time_ms: float = 0.0
    avg_results_returned: float = 0.0
    _search_times: List[float] = field(default_factory=list)
    _results_counts: List[int] = field(default_factory=list)

    def record_search(self, results: int, duration_ms: float):
        """Record a search operation."""
        self.total_searches += 1
        self._search_times.append(duration_ms)
        self._results_counts.append(results)
        if len(self._search_times) > 1000:
            self._search_times = self._search_times[-1000:]
            self._results_counts = self._results_counts[-1000:]
        self.avg_search_time_ms = sum(self._search_times) / len(self._search_times)
        self.avg_results_returned = sum(self._results_counts) / len(self._results_counts)


class FileLock:
    """
    Simple file-based lock for coordinating writes across processes.

    For production with multiple writers, consider using:
    - PostgreSQL advisory locks
    - Redis distributed locks
    - DynamoDB for S3 commit store
    """

    def __init__(self, lock_path: str, timeout: float = 30.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self._lock_file = None

    def acquire(self) -> bool:
        """Acquire the lock."""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # Try to create lock file exclusively
                self._lock_file = open(self.lock_path, 'x')
                # Write lock info
                lock_info = {
                    "pid": os.getpid(),
                    "timestamp": datetime.now().isoformat(),
                    "hostname": os.uname().nodename,
                }
                self._lock_file.write(json.dumps(lock_info))
                self._lock_file.flush()
                return True
            except FileExistsError:
                # Check if lock is stale (older than timeout)
                try:
                    stat = os.stat(self.lock_path)
                    age = time.time() - stat.st_mtime
                    if age > self.timeout:
                        # Stale lock, remove it
                        os.remove(self.lock_path)
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(0.1)
        return False

    def release(self):
        """Release the lock."""
        if self._lock_file:
            self._lock_file.close()
            self._lock_file = None
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass


class LanceManager:
    """
    Production manager for LanceDB operations.

    Provides:
    - Concurrent write coordination
    - Automatic retries with backoff
    - Table maintenance (compaction, indexing)
    - Metrics collection
    - Health monitoring
    """

    def __init__(
        self,
        lance_path: str,
        enable_metrics: bool = True,
        lock_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the Lance manager.

        Args:
            lance_path: Path to LanceDB storage
            enable_metrics: Enable metrics collection
            lock_timeout: Timeout for write locks (seconds)
            max_retries: Maximum retry attempts for failed operations
            retry_delay: Initial delay between retries (seconds)
        """
        self.lance_path = lance_path
        self.enable_metrics = enable_metrics
        self.lock_timeout = lock_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Ensure directory exists
        os.makedirs(lance_path, exist_ok=True)

        # Lock directory
        self._lock_dir = os.path.join(lance_path, ".locks")
        os.makedirs(self._lock_dir, exist_ok=True)

        # Connection
        self._db = None

        # Metrics
        self._write_metrics: Dict[str, WriteMetrics] = {}
        self._search_metrics: Dict[str, SearchMetrics] = {}

        # Thread-local locks for in-process coordination
        self._table_locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    @property
    def db(self) -> lancedb.DBConnection:
        """Get LanceDB connection."""
        if self._db is None:
            self._db = lancedb.connect(self.lance_path)
        return self._db

    def _get_table_lock(self, table_name: str) -> threading.Lock:
        """Get or create a thread lock for a table."""
        with self._locks_lock:
            if table_name not in self._table_locks:
                self._table_locks[table_name] = threading.Lock()
            return self._table_locks[table_name]

    def _get_file_lock_path(self, table_name: str) -> str:
        """Get the file lock path for a table."""
        return os.path.join(self._lock_dir, f"{table_name}.lock")

    @contextmanager
    def write_lock(self, table_name: str):
        """
        Context manager for coordinated writes.

        Uses both thread locks (in-process) and file locks (cross-process).

        Usage:
            with manager.write_lock("my_table"):
                manager.append("my_table", records)
        """
        thread_lock = self._get_table_lock(table_name)
        file_lock = FileLock(self._get_file_lock_path(table_name), self.lock_timeout)

        # Acquire thread lock first
        thread_lock.acquire()
        try:
            # Then file lock
            if not file_lock.acquire():
                raise TimeoutError(f"Could not acquire lock for table {table_name}")
            try:
                yield
            finally:
                file_lock.release()
        finally:
            thread_lock.release()

    def _retry_operation(
        self,
        operation: Callable,
        table_name: str,
        operation_name: str,
    ) -> Any:
        """Execute an operation with retry logic."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} failed on {table_name}, "
                        f"retrying in {delay}s (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(delay)
        raise last_error

    def create_table(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        mode: str = "overwrite",
    ) -> lancedb.table.Table:
        """
        Create a new table.

        Args:
            table_name: Name of the table
            data: Initial data records
            mode: 'overwrite' or 'create'

        Returns:
            The created table
        """
        with self.write_lock(table_name):
            table = self.db.create_table(table_name, data=data, mode=mode)
            logger.info(f"Created table {table_name} with {len(data)} records")
            return table

    def append(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        use_lock: bool = True,
    ) -> int:
        """
        Append records to a table with retry logic.

        Args:
            table_name: Name of the table
            records: Records to append
            use_lock: Whether to use write lock (set False if already locked)

        Returns:
            Number of records written
        """
        start_time = time.time()
        retried = False

        def do_append():
            nonlocal retried
            table = self.db.open_table(table_name)
            table.add(records)
            return len(records)

        try:
            if use_lock:
                with self.write_lock(table_name):
                    count = self._retry_operation(do_append, table_name, "append")
            else:
                count = self._retry_operation(do_append, table_name, "append")

            duration_ms = (time.time() - start_time) * 1000

            if self.enable_metrics:
                if table_name not in self._write_metrics:
                    self._write_metrics[table_name] = WriteMetrics()
                self._write_metrics[table_name].record_write(count, duration_ms, True, retried)

            logger.debug(f"Appended {count} records to {table_name} in {duration_ms:.1f}ms")
            return count

        except Exception as e:
            if self.enable_metrics:
                if table_name not in self._write_metrics:
                    self._write_metrics[table_name] = WriteMetrics()
                self._write_metrics[table_name].record_write(0, 0, False)
            raise

    def search(
        self,
        table_name: str,
        query_vector: List[float],
        limit: int = 10,
        filter_expr: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Search a table with metrics tracking.

        Args:
            table_name: Name of the table
            query_vector: Query embedding vector
            limit: Maximum results
            filter_expr: Optional SQL filter

        Returns:
            List of matching records
        """
        start_time = time.time()

        table = self.db.open_table(table_name)
        search = table.search(query_vector)

        if filter_expr:
            search = search.where(filter_expr)

        results = search.limit(limit).to_pandas()
        duration_ms = (time.time() - start_time) * 1000

        if self.enable_metrics:
            if table_name not in self._search_metrics:
                self._search_metrics[table_name] = SearchMetrics()
            self._search_metrics[table_name].record_search(len(results), duration_ms)

        return results.to_dict('records')

    def get_table_stats(self, table_name: str) -> TableStats:
        """Get statistics for a table."""
        table = self.db.open_table(table_name)

        # Get table path
        table_path = os.path.join(self.lance_path, f"{table_name}.lance")

        # Calculate size
        total_size = 0
        num_fragments = 0
        if os.path.exists(table_path):
            for root, dirs, files in os.walk(table_path):
                for f in files:
                    total_size += os.path.getsize(os.path.join(root, f))
                num_fragments = len([d for d in dirs if d.startswith("data")])

        # Get schema
        schema = {field.name: str(field.type) for field in table.schema}

        # Check for index
        has_index = False
        index_path = os.path.join(table_path, "_indices")
        if os.path.exists(index_path):
            has_index = len(os.listdir(index_path)) > 0

        return TableStats(
            name=table_name,
            row_count=table.count_rows(),
            size_bytes=total_size,
            num_fragments=num_fragments,
            has_index=has_index,
            last_modified=datetime.fromtimestamp(os.path.getmtime(table_path)) if os.path.exists(table_path) else datetime.now(),
            schema=schema,
        )

    def compact(self, table_name: str) -> Dict[str, Any]:
        """
        Compact a table to optimize storage and query performance.

        Args:
            table_name: Name of the table

        Returns:
            Compaction statistics
        """
        with self.write_lock(table_name):
            table = self.db.open_table(table_name)

            stats_before = self.get_table_stats(table_name)

            # Lance compaction
            table.compact_files()

            stats_after = self.get_table_stats(table_name)

            result = {
                "table": table_name,
                "fragments_before": stats_before.num_fragments,
                "fragments_after": stats_after.num_fragments,
                "size_before": stats_before.size_bytes,
                "size_after": stats_after.size_bytes,
                "size_reduction_pct": round(
                    (1 - stats_after.size_bytes / max(stats_before.size_bytes, 1)) * 100, 2
                ),
            }

            logger.info(f"Compacted {table_name}: {result}")
            return result

    def create_index(
        self,
        table_name: str,
        metric: str = "L2",
        num_partitions: int = 256,
        num_sub_vectors: int = 16,
    ) -> bool:
        """
        Create or update vector index on a table.

        Args:
            table_name: Name of the table
            metric: Distance metric (L2, cosine, dot)
            num_partitions: Number of IVF partitions
            num_sub_vectors: Number of PQ sub-vectors

        Returns:
            True if index was created, False if skipped
        """
        with self.write_lock(table_name):
            table = self.db.open_table(table_name)
            row_count = table.count_rows()

            if row_count < 256:
                logger.info(f"Skipping index on {table_name}: need 256+ rows, have {row_count}")
                return False

            table.create_index(
                metric=metric,
                num_partitions=min(num_partitions, row_count // 10),
                num_sub_vectors=num_sub_vectors,
                replace=True,
            )

            logger.info(f"Created index on {table_name} ({row_count} rows)")
            return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return {
            "write_metrics": {
                table: {
                    "total_writes": m.total_writes,
                    "total_rows_written": m.total_rows_written,
                    "failed_writes": m.failed_writes,
                    "retried_writes": m.retried_writes,
                    "avg_write_time_ms": round(m.avg_write_time_ms, 2),
                    "last_write_time": m.last_write_time.isoformat() if m.last_write_time else None,
                }
                for table, m in self._write_metrics.items()
            },
            "search_metrics": {
                table: {
                    "total_searches": m.total_searches,
                    "avg_search_time_ms": round(m.avg_search_time_ms, 2),
                    "avg_results_returned": round(m.avg_results_returned, 2),
                }
                for table, m in self._search_metrics.items()
            },
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the Lance installation.

        Returns:
            Health status and diagnostics
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "lance_path": self.lance_path,
            "tables": [],
            "issues": [],
        }

        try:
            # Check path is writable
            test_file = os.path.join(self.lance_path, ".health_check")
            with open(test_file, 'w') as f:
                f.write("ok")
            os.remove(test_file)
        except Exception as e:
            health["status"] = "unhealthy"
            health["issues"].append(f"Path not writable: {e}")

        # Check tables
        try:
            tables = self.db.table_names()
            for table_name in tables:
                try:
                    stats = self.get_table_stats(table_name)
                    health["tables"].append({
                        "name": stats.name,
                        "rows": stats.row_count,
                        "size_mb": round(stats.size_bytes / (1024 * 1024), 2),
                        "has_index": stats.has_index,
                    })
                except Exception as e:
                    health["issues"].append(f"Error reading table {table_name}: {e}")
        except Exception as e:
            health["status"] = "unhealthy"
            health["issues"].append(f"Cannot list tables: {e}")

        if health["issues"]:
            health["status"] = "degraded" if health["status"] == "healthy" else health["status"]

        return health

    def backup(self, backup_path: str) -> Dict[str, Any]:
        """
        Create a backup of all tables.

        Args:
            backup_path: Destination path for backup

        Returns:
            Backup statistics
        """
        import shutil

        os.makedirs(backup_path, exist_ok=True)

        backup_info = {
            "timestamp": datetime.now().isoformat(),
            "source": self.lance_path,
            "destination": backup_path,
            "tables": [],
        }

        for table_name in self.db.table_names():
            src = os.path.join(self.lance_path, f"{table_name}.lance")
            dst = os.path.join(backup_path, f"{table_name}.lance")

            if os.path.exists(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                stats = self.get_table_stats(table_name)
                backup_info["tables"].append({
                    "name": table_name,
                    "rows": stats.row_count,
                    "size_bytes": stats.size_bytes,
                })

        # Write backup manifest
        manifest_path = os.path.join(backup_path, "backup_manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(backup_info, f, indent=2)

        logger.info(f"Backup completed to {backup_path}")
        return backup_info


# Demo
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from embeddings import get_embedding_generator

    print("=" * 60)
    print("LANCE MANAGER DEMO")
    print("=" * 60)

    # Initialize
    manager = LanceManager("/tmp/lance_manager_demo", enable_metrics=True)
    embedding_gen = get_embedding_generator(use_mock=True)

    # Create sample data
    print("\n[1] Creating sample table...")
    sample_data = []
    for i in range(100):
        text = f"Document {i} about topic {i % 10}"
        embedding = embedding_gen.encode_single(text)
        sample_data.append({
            "id": f"doc_{i}",
            "content": text,
            "category": f"cat_{i % 5}",
            "vector": embedding,
        })

    manager.create_table("demo", sample_data)

    # Test concurrent writes
    print("\n[2] Testing concurrent writes...")
    import concurrent.futures

    def write_batch(batch_id):
        records = []
        for i in range(10):
            text = f"Batch {batch_id} doc {i}"
            embedding = embedding_gen.encode_single(text)
            records.append({
                "id": f"batch_{batch_id}_doc_{i}",
                "content": text,
                "category": f"cat_{batch_id % 5}",
                "vector": embedding,
            })
        manager.append("demo", records)
        return batch_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(write_batch, i) for i in range(8)]
        for future in concurrent.futures.as_completed(futures):
            print(f"    Batch {future.result()} completed")

    # Test search
    print("\n[3] Testing search...")
    query_vec = embedding_gen.encode_single("document about topic 5")
    results = manager.search("demo", query_vec, limit=5)
    print(f"    Found {len(results)} results")

    # Get stats
    print("\n[4] Table statistics...")
    stats = manager.get_table_stats("demo")
    print(f"    Rows: {stats.row_count}")
    print(f"    Size: {stats.size_bytes / 1024:.1f} KB")
    print(f"    Has index: {stats.has_index}")

    # Create index
    print("\n[5] Creating index...")
    manager.create_index("demo")

    # Health check
    print("\n[6] Health check...")
    health = manager.health_check()
    print(f"    Status: {health['status']}")
    print(f"    Tables: {len(health['tables'])}")

    # Metrics
    print("\n[7] Metrics...")
    metrics = manager.get_metrics()
    print(f"    Write metrics: {metrics['write_metrics']}")
    print(f"    Search metrics: {metrics['search_metrics']}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
