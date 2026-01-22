# Multimodal Data Integration with LanceDB

## Overview

This document outlines the integration of LanceDB into the lakehouse-stack to enable multimodal AI capabilities alongside the existing Iceberg-based data lakehouse.

## Architecture Vision

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   Data Sources                       │
                    └─────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │                    Kafka 3.6                         │
                    │              (Streaming Ingestion)                   │
                    └─────────────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                              ▼
    ┌───────────────────────────────┐          ┌───────────────────────────────┐
    │         Iceberg 1.10          │          │           LanceDB             │
    │    (Structured/Tabular)       │          │   (Multimodal/Embeddings)     │
    ├───────────────────────────────┤          ├───────────────────────────────┤
    │ Bronze: Raw events            │          │ Images, audio, video          │
    │ Silver: Cleaned data          │          │ Text embeddings               │
    │ Gold: Aggregations            │          │ Vector indexes (IVF-PQ/HNSW)  │
    └───────────────────────────────┘          └───────────────────────────────┘
                    │                                              │
                    └──────────────────────┬──────────────────────┘
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │                  Spark 4.x                           │
                    │        (Unified Query Engine for Both)               │
                    └─────────────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                              ▼
    ┌───────────────────────────────┐          ┌───────────────────────────────┐
    │         PostgreSQL            │          │          SeaweedFS            │
    │     (Iceberg Metadata)        │          │     (S3-Compatible Data)      │
    └───────────────────────────────┘          └───────────────────────────────┘
```

## Why LanceDB + Iceberg?

| Aspect | Iceberg | LanceDB |
|--------|---------|---------|
| **Optimized For** | BI/Analytics (OLAP) | AI/ML Workloads |
| **File Format** | Parquet | Lance |
| **Random Access** | Slower (row-group structure) | 100-2000x faster |
| **Vector Search** | Not native | Built-in (sub-ms) |
| **Multimodal** | Limited blob support | Native image/audio/video |
| **ACID** | Full support | Append-optimized |
| **Time Travel** | Full support | Supported |

## Implementation Phases

### Phase 1: Local Development Setup (COMPLETE)
- [x] Add LanceDB Python dependencies to poetry
- [x] Download lance-spark JARs
- [x] Create example scripts for local Lance operations
- [x] Test basic read/write with PySpark

### Phase 2: Docker Integration (COMPLETE)
- [x] Update docker-compose with Lance-enabled Spark
- [x] Configure SeaweedFS as Lance storage backend
- [x] Add health checks for Lance operations

### Phase 3: Streaming Integration (COMPLETE)
- [x] Create Kafka → Lance pipeline for embeddings
- [x] Implement embedding generation (sentence-transformers)
- [x] Build vector index on streaming data

### Phase 4: Multimodal Examples (COMPLETE)
- [x] Image search example (CLIP embeddings)
- [x] Text semantic search (sentence embeddings)
- [x] Hybrid search (vector + Iceberg metadata join)
- [x] Unified multimodal search API

### Phase 5: Production Readiness (COMPLETE)
- [x] Concurrent write handling with file locks and thread locks
- [x] Production manager with retry logic and metrics
- [x] Monitoring and observability (Prometheus metrics, health checks)
- [x] Alerting rules for performance and storage
- [x] Production configuration templates
- [x] Documentation

## Files Created

### Phase 1
| File | Purpose |
|------|---------|
| `pyproject.toml` | Updated with lancedb, sentence-transformers, pandas |
| `scripts/download-lance-jars.sh` | Downloads lance-spark-bundle JAR |
| `scripts/05-lance-quickstart.py` | Full Lance + PySpark demo |
| `jars/lance-spark-bundle-4.0_2.13-0.0.15.jar` | Spark 4.0 Lance connector |

### Phase 2
| File | Purpose |
|------|---------|
| `config/spark/spark-defaults-lance.conf.example` | Spark config with Lance catalog |
| `docker-compose-lance.yml` | Docker Compose for Lance-enabled Spark |
| `scripts/test-lance.py` | Health check and test script |
| `data/lance/` | Persistent Lance data directory |

### Phase 3
| File | Purpose |
|------|---------|
| `scripts/embeddings.py` | Embedding generator service (sentence-transformers) |
| `scripts/kafka-lance-producer.py` | Kafka producer for product data |
| `scripts/06-kafka-to-lance.py` | Standalone Kafka → Lance streaming pipeline |
| `scripts/07-spark-lance-streaming.py` | Spark Structured Streaming to Lance |

### Phase 4
| File | Purpose |
|------|---------|
| `scripts/08-semantic-search.py` | Text semantic search demo |
| `scripts/09-image-search.py` | Image search with CLIP embeddings |
| `scripts/10-hybrid-lance-iceberg.py` | Hybrid search (vector + structured data) |
| `scripts/multimodal_search.py` | Unified multimodal search API |

### Phase 5
| File | Purpose |
|------|---------|
| `scripts/lance_manager.py` | Production manager with concurrent writes, locking, retries |
| `scripts/lance_monitoring.py` | Prometheus metrics, health checks, alerting |
| `config/lance/production.env.example` | Production environment variables |
| `config/lance/alerting-rules.yml` | Prometheus alerting rules |
| `config/lance/spark-defaults-lance-prod.conf.example` | Production Spark config |
| `docker-compose-lance-prod.yml` | Production Docker Compose with monitoring |
| `config/prometheus/prometheus.yml` | Prometheus configuration |
| `config/grafana/provisioning/` | Grafana datasources and dashboards |

## Quick Start

```bash
# 1. Download Lance JARs
./scripts/download-lance-jars.sh

# 2. Install Python dependencies
poetry install

# 3. Run local test
poetry run python scripts/test-lance.py --local

# 4. Run quickstart demo
poetry run python scripts/05-lance-quickstart.py

# 5. Start Lance-enabled Spark cluster
docker compose -f docker-compose-lance.yml up -d

# 6. Run in Docker
docker exec spark-master-lance /opt/spark/bin/spark-submit \
  --jars /opt/spark/jars-extra/lance-spark-bundle-4.0_2.13-0.0.15.jar \
  /scripts/05-lance-quickstart.py
```

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Spark | 4.0.1 / 4.1.0 | Scala 2.13 |
| LanceDB Python | 0.26.1 | Installed |
| lance-spark | 0.0.15 | Spark 4.0 bundle |
| Python | 3.10+ | Match existing stack |
| PyArrow | 16+ | Required by Lance |

## Production Deployment

### Quick Start (Production)

```bash
# 1. Copy and configure environment
cp config/lance/production.env.example .env.lance
vim .env.lance  # Update credentials

# 2. Copy Spark configuration
cp config/lance/spark-defaults-lance-prod.conf.example config/spark/spark-defaults.conf
vim config/spark/spark-defaults.conf  # Update credentials

# 3. Download JARs
./scripts/download-lance-jars.sh

# 4. Create data directories
mkdir -p data/lance data/spark-events

# 5. Start production stack
docker compose -f docker-compose-lance-prod.yml up -d

# 6. Verify health
curl http://localhost:9090/health
curl http://localhost:8084  # Spark UI
```

### Monitoring Endpoints

| Endpoint | Port | Purpose |
|----------|------|---------|
| Lance Metrics | 9090 | `/metrics` - Prometheus metrics |
| Lance Health | 9090 | `/health` - Health check JSON |
| Prometheus | 9091 | Metrics aggregation |
| Grafana | 3000 | Dashboards (admin/admin) |
| Spark Master UI | 8084 | Cluster overview |
| Spark Workers | 8085-8087 | Worker status |

### Using the Production Manager

```python
from lance_manager import LanceManager

# Initialize with production settings
manager = LanceManager(
    lance_path="/opt/lance-data",
    lock_dir="/tmp/lance_locks",
    max_retries=3,
)

# Thread-safe writes with automatic locking
records = [{"id": "1", "text": "example", "vector": [...]}]
rows_written = manager.append("my_table", records)

# Metrics tracking
metrics = manager.get_metrics()
print(f"Writes: {metrics['write_count']}, Errors: {metrics['error_count']}")

# Create vector index for faster search
manager.create_index("my_table", metric="cosine")

# Compaction for maintenance
manager.compact("my_table")
```

### Using the Monitoring API

```python
from lance_monitoring import LanceMonitor

# Initialize monitor
monitor = LanceMonitor("/opt/lance-data")

# Record operations
monitor.record_query("products", latency_ms=15.2, result_count=10)
monitor.record_write("products", rows=100, latency_ms=250, success=True)

# Health check
health = monitor.health_check()
print(f"Status: {health['status']}")  # healthy/degraded/unhealthy

# Get Prometheus metrics
metrics = monitor.get_prometheus_metrics()

# Start metrics HTTP server
monitor.start_http_server(port=9090)
```

### Alerting

Key alerts configured in `config/lance/alerting-rules.yml`:

| Alert | Threshold | Severity |
|-------|-----------|----------|
| High Query Latency | P99 > 1000ms | Warning |
| Critical Query Latency | P99 > 5000ms | Critical |
| Write Errors | > 5% error rate | Warning |
| High Disk Usage | > 85% | Warning |
| Critical Disk Usage | > 95% | Critical |
| Missing Index | > 256 rows, no index | Warning |
| Kafka Consumer Lag | > 10k messages | Warning |

### Scaling Considerations

1. **Horizontal Scaling**: Add more Spark workers by copying the worker service definition
2. **Memory Tuning**: Adjust `SPARK_WORKER_MEMORY` based on embedding dimensions
3. **Index Tuning**: Increase `num_partitions` for larger datasets
4. **Compaction**: Schedule regular compaction for write-heavy workloads

### Storage Layout

```
data/
├── lance/                    # LanceDB tables
│   ├── products/            # Product embeddings
│   │   ├── data/           # Lance data files
│   │   └── _versions/      # Version history
│   └── images/             # Image embeddings
└── spark-events/            # Spark event logs
```
