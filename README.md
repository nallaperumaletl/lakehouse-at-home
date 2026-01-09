# Lakehouse-in-a-box Stack

A fully open-source, self-hostable data lakehouse for local development and testing of OSS data workflows.

## Stack

- **Apache Spark 4.0.1 / 4.1.0** - Distributed compute engine (supports both versions simultaneously)
- **Apache Iceberg 1.10.0** - Table format with ACID transactions
- **Apache Kafka 3.6.1** - Event streaming platform
- **PostgreSQL 16** - Iceberg catalog metadata
- **SeaweedFS** - S3-compatible object storage

## Architecture

```
Spark 4.1 (Master/Workers)
    ↓
Iceberg 1.10 (Table Format)
    ├── Metadata → PostgreSQL
    └── Data → SeaweedFS (S3)
    ↓
Kafka 3.6.1 (Streaming)
```

## Prerequisites

- Docker & Docker Compose v2
- PostgreSQL 16 (running natively on host)
- SeaweedFS (running natively on host)
- Python 3.10+ with Poetry
- 20GB disk space for JARs and data

> **New to setup?** See [SETUP.md](SETUP.md) for detailed OS-specific installation instructions.

### PostgreSQL Setup

```bash
# Ubuntu/Debian
sudo apt install postgresql-16 postgresql-client-16
sudo systemctl start postgresql

# macOS
brew install postgresql@16
brew services start postgresql@16

# Create database and user
createuser -P lakehouse              # Set a password
createdb -O lakehouse iceberg_catalog
```

### SeaweedFS Setup

```bash
# Download from https://github.com/seaweedfs/seaweedfs/releases
# Or install via package manager:

# macOS
brew install seaweedfs

# Start with S3 API enabled
weed server -s3 -dir=/var/lib/seaweedfs &
```

SeaweedFS provides S3-compatible storage on port 8333. No bucket creation needed - they are created automatically.

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/lisancao/lakehouse-at-home.git
cd lakehouse-at-home

# Run automated setup (validates prereqs, downloads JARs, installs deps)
./lakehouse setup
```

The setup command will:
- Check all prerequisites (Docker, Poetry, etc.)
- Create `.env` and `spark-defaults.conf` from examples
- Download required JARs (~860MB)
- Install Python dependencies
- Validate configuration

### 2. Configure Credentials

```bash
# Edit with your PostgreSQL and S3 credentials
nano .env
nano config/spark/spark-defaults.conf
```

### 3. Start Services

```bash
./lakehouse start all
```

### 4. Verify Setup

```bash
./lakehouse test
```

## Usage

### CLI Commands

```bash
./lakehouse setup                               # Validate environment and install deps
./lakehouse status                              # Check all services status
./lakehouse start [spark|kafka|all]             # Start services
./lakehouse stop [spark|kafka|all]              # Stop services
./lakehouse restart [spark|kafka|all]           # Restart services
./lakehouse logs [spark-master|spark-worker|kafka|zookeeper]  # View logs
./lakehouse test                                # Run connectivity tests
./lakehouse producer                            # Start Kafka event producer
./lakehouse consumer                            # Start Spark streaming consumer

# Version flag (default: 4.1)
./lakehouse start spark --version 4.0           # Start Spark 4.0
./lakehouse start spark --version 4.1           # Start Spark 4.1
./lakehouse consumer --version 4.0              # Run consumer on Spark 4.0
```

### Test Data Generation

Generate realistic food delivery order data (inspired by [Casper's Kitchens](https://github.com/databricks-solutions/caspers-kitchens)) for testing batch and streaming workflows.

```bash
# Generate 90-day dataset (~3.7M orders, ~100M events, ~7GB)
./lakehouse testdata generate

# Load into Iceberg tables
./lakehouse testdata load

# Stream to Kafka at 60x speed (1 real min = 1 simulated hour)
./lakehouse testdata stream --speed 60

# View statistics
./lakehouse testdata stats

# Clean up generated data
./lakehouse testdata clean
```

**Generated Tables (Medallion Architecture):**

| Table | Description | Records |
|-------|-------------|---------|
| `iceberg.bronze.dim_brands` | Ghost kitchen brands | 20 |
| `iceberg.bronze.dim_items` | Menu items | 160 |
| `iceberg.bronze.dim_categories` | Food categories | 10 |
| `iceberg.bronze.dim_locations` | Delivery cities | 4 |
| `iceberg.bronze.orders` | Order lifecycle events | ~100M |

**Event Types (Order Lifecycle):**
```
order_created → kitchen_started → kitchen_finished → order_ready →
driver_arrived → driver_picked_up → driver_ping (multiple) → delivered
```

### Example Scripts

| Script | Description |
|--------|-------------|
| `scripts/01-basics.py` | Basic Spark table operations |
| `scripts/02-transformations.py` | Narrow & wide transformations |
| `scripts/03-streaming-basic.py` | Streaming with rate source |
| `scripts/04-kafka-streaming.py` | Kafka streaming with windowed aggregations |
| `scripts/kafka-producer.py` | Synthetic event generator |
| `scripts/test-kafka.py` | Simple Kafka consumer (used by `./lakehouse consumer`) |
| `scripts/test-iceberg.py` | Iceberg catalog connectivity test |

### Kafka Streaming Example

```bash
# Terminal 1: Start producer
./lakehouse producer

# Terminal 2: Simple consumer (via CLI)
./lakehouse consumer

# Alternative: Advanced windowed aggregations
docker exec spark-master-41 /opt/spark/bin/spark-submit \
  --master local[2] /scripts/04-kafka-streaming.py
```

## Configuration

### Environment Variables (.env)

```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET
ICEBERG_CATALOG_URI, ICEBERG_WAREHOUSE
```

### Spark Configuration

Edit `config/spark/spark-defaults.conf` for Spark tuning and credentials.

## Multi-Version Spark Testing

Run Spark 4.0 and 4.1 simultaneously for A/B testing and migration validation.

### Port Assignments

| Version | Compose File | Master Port | UI Port | Worker UI |
|---------|--------------|-------------|---------|-----------|
| 4.0.1 | `docker-compose.yml` | 7077 | 8080 | 8081 |
| 4.1.0 | `docker-compose-spark41.yml` | 7078 | 8082 | 8083 |

### Running Both Versions

```bash
# Start both Spark versions
./lakehouse start spark --version 4.0
./lakehouse start spark --version 4.1

# Check status (shows both)
./lakehouse status

# Submit jobs to specific version
spark-submit --master spark://localhost:7077 script.py  # Spark 4.0
spark-submit --master spark://localhost:7078 script.py  # Spark 4.1

# Stop specific version
./lakehouse stop spark --version 4.0
```

## Table Naming Convention (Medallion)

- `iceberg.bronze.*` - Raw data
- `iceberg.silver.*` - Cleaned/transformed
- `iceberg.gold.*` - Business-ready

## Critical Version Locks

This stack requires **exact** versions for compatibility:

| Component | Version | Notes |
|-----------|---------|-------|
| Spark | 4.0.1 | Scala 2.13, Java 17 |
| Spark | 4.1.0 | Scala 2.13, Java 21 |
| Iceberg | 1.10.0 | For Spark 4.x |
| Hadoop AWS | 3.4.1 | - |
| AWS SDK v2 | 2.24.6 | **Exact match required** |
| Kafka | 3.6.1 | - |
| commons-pool2 | 2.12.0 | For Kafka streaming |

## Troubleshooting

### Connection Refused

Ensure PostgreSQL and SeaweedFS are running on the host:
```bash
systemctl status postgresql
systemctl status seaweedfs-master
```

### Kafka Not Connecting

Verify Zookeeper is healthy before Kafka:
```bash
docker logs zookeeper
docker logs kafka
```

### Spark UI

| Version | Master UI | Worker UI |
|---------|-----------|-----------|
| 4.0 | http://localhost:8080 | http://localhost:8081 |
| 4.1 | http://localhost:8082 | http://localhost:8083 |

- Application UI: http://localhost:4040 (active job)

## License

MIT
