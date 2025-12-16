# Lakehouse-in-a-box Stack

A locally hostable open lakehouse:
- **Apache Spark 4.0.1** - Distributed compute
- **Apache Iceberg 1.10.0** - Table format with ACID transactions
- **PostgreSQL 16** - Iceberg catalog metadata
- **SeaweedFS** - S3-compatible object storage

## Architecture
```
Spark 4.0.1 (Docker)
    ↓
Iceberg 1.10.0
    ├── Metadata → PostgreSQL
    └── Data → SeaweedFS (S3)
```

## Prerequisites

- Docker & Docker Compose v2
- PostgreSQL 16 (running natively)
- SeaweedFS (running natively)
- 20GB disk space for JARs and data

## Setup

### 1. Clone and Configure
```bash
git clone <your-repo-url>
cd lakehouse-stack

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

### 2. Copy Spark Config Template
```bash
cp config/spark/spark-defaults.conf.example config/spark/spark-defaults.conf
```

### 3. Download JARs

```bash
./scripts/download-jars.sh
```

This downloads ~860MB of dependencies (exact versions required for compatibility).

### 4. Start Services
```bash
docker compose up -d
```

### 5. Run Test
```bash
./scripts/run-spark-test.sh
```

## Configuration

### Environment Variables (.env)

- `POSTGRES_USER` - PostgreSQL username
- `POSTGRES_PASSWORD` - PostgreSQL password
- `POSTGRES_HOST` - Default: localhost
- `S3_ENDPOINT` - SeaweedFS S3 endpoint
- `S3_ACCESS_KEY` - SeaweedFS credentials
- `S3_SECRET_KEY` - SeaweedFS credentials

### Spark Configuration

Edit `config/spark/spark-defaults.conf` for Spark tuning.

## Troubleshooting

### Connection Refused Errors

Ensure PostgreSQL and SeaweedFS are running on the host:
```bash
systemctl status postgresql
systemctl status seaweedfs-master
```

### JAR Version Conflicts

This stack requires **exact** versions:
- Hadoop 3.4.1 → AWS SDK v2.24.6 (not newer!)
- Spark 4.0.1 → Scala 2.13
- Iceberg 1.10.0 → Spark 4.0

## License

