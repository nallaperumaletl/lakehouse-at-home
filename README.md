# Lakehouse at Home

A fully open-source, self-hostable data lakehouse for local development and testing of modern data workflows. Run production-grade infrastructure on your laptop with Apache Spark, Iceberg, and Kafka - no cloud account required. Includes a realistic data generation framework to test batch and streaming pipelines.

[![CI](https://github.com/lisancao/lakehouse-at-home/actions/workflows/ci.yml/badge.svg)](https://github.com/lisancao/lakehouse-at-home/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/lisancao/lakehouse-at-home)](https://github.com/lisancao/lakehouse-at-home/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/lisancao/lakehouse-at-home)](https://github.com/lisancao/lakehouse-at-home/issues)
[![Spark](https://img.shields.io/badge/Spark-4.0%20%7C%204.1-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Iceberg](https://img.shields.io/badge/Iceberg-1.10-blue)](https://iceberg.apache.org/)

**Why Lakehouse at Home?**
- **Learn** data engineering with real tools, not toy examples
- **Develop** and test Spark jobs locally before deploying to production
- **Experiment** with Iceberg table formats, streaming pipelines, and medallion architecture
- **Deploy** (optional) to your cloud provider when ready using included Terraform templates

## Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| Apache Spark | 4.0 / 4.1 | Distributed compute |
| Apache Iceberg | 1.10 | ACID table format |
| Apache Kafka | 3.6 | Event streaming |
| PostgreSQL | 16 | Catalog metadata |
| SeaweedFS | - | S3-compatible storage |
| Unity Catalog | 0.3.1 | REST catalog (optional) |

## Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk | 20 GB | 50 GB |
| CPU | 4 cores | 8 cores |

**Software**: Docker, Java 17+ (21 for Spark 4.1), Python 3.10+, Poetry

## Getting Started

### AI-Assisted Setup

Using Claude Code, Cursor, or another AI coding assistant? Point it at this repo:

```
Clone https://github.com/lisancao/lakehouse-at-home and follow CLAUDE.md to set up locally.
```

The agent will use `CLAUDE.md` for context and `./lakehouse setup` to validate prerequisites.

### Manual Setup

```bash
# Clone
git clone https://github.com/lisancao/lakehouse-at-home.git
cd lakehouse-at-home

# Setup (validates prereqs, downloads JARs, installs deps)
./lakehouse setup

# Configure credentials
nano .env
nano config/spark/spark-defaults.conf

# Start
./lakehouse start all

# Verify
./lakehouse test
```

See [Installation Guide](docs/getting-started/installation.md) for detailed OS-specific setup.

## CLI

```bash
# Setup & validation
./lakehouse setup                # Validate prereqs, download JARs, install deps
./lakehouse check-config         # Validate credential consistency
./lakehouse preflight            # Test service connectivity

# Service management
./lakehouse start all            # Start Spark + Kafka
./lakehouse stop all             # Stop all services
./lakehouse status               # Check service health
./lakehouse status --json        # Machine-readable status
./lakehouse test                 # Run connectivity tests
./lakehouse logs spark-master    # View logs

# Unity Catalog (optional)
./lakehouse start unity-catalog  # Start Unity Catalog REST server
./lakehouse stop unity-catalog   # Stop Unity Catalog
```

See [CLI Reference](docs/guides/cli-reference.md) for all commands.

## Test Data

Generate realistic order data for testing:

```bash
./lakehouse testdata generate --days 7    # Generate 7 days
./lakehouse testdata load                 # Load to Iceberg
./lakehouse testdata stream --speed 60    # Stream to Kafka
```

See [Test Data Guide](docs/guides/test-data.md) for details.

## Documentation

| Guide | Description |
|-------|-------------|
| [Quickstart](docs/getting-started/quickstart.md) | 5-minute setup |
| [Installation](docs/getting-started/installation.md) | macOS, Ubuntu, Windows guides |
| [Configuration](docs/getting-started/configuration.md) | Environment and Spark config |
| [CLI Reference](docs/guides/cli-reference.md) | All commands |
| [Streaming](docs/guides/streaming.md) | Kafka + Spark streaming |
| [Multi-Version Spark](docs/guides/multi-version.md) | Run 4.0 and 4.1 together |
| [Unity Catalog](docs/guides/unity-catalog.md) | REST catalog setup & migration |
| [Architecture](docs/architecture.md) | System design |
| [AWS Deployment](docs/deployment/aws.md) | Cloud production setup |
| [Databricks Deployment](docs/deployment/databricks.md) | Managed Spark platform |
| [Troubleshooting](docs/troubleshooting.md) | Common issues |
| [Security](SECURITY.md) | Security guidelines for contributors |

## Architecture

```
                              ┌─────────────────────┐
                              │  PostgreSQL (JDBC)  │
                              │    OR               │
Spark 4.x ────▶ Iceberg 1.10 ─┤  Unity Catalog      │
                              │    (REST API)       │
                              └─────────────────────┘
                    │
                    ▼
               SeaweedFS (S3)

Kafka 3.6 ◀──── Streaming ────▶ Iceberg Tables
```

**Catalog Options:**
- **PostgreSQL JDBC** (default): Direct SQL, Spark-only
- **Unity Catalog OSS** (optional): REST API, works with DuckDB, Trino, Dremio

**Medallion Architecture:**
- `iceberg.bronze.*` - Raw data
- `iceberg.silver.*` - Cleaned/transformed
- `iceberg.gold.*` - Business-ready

## Ports

| Service | Port | UI |
|---------|------|-----|
| PostgreSQL | 5432 | - |
| SeaweedFS | 8333 | - |
| Spark 4.0 | 7077 | http://localhost:8080 |
| Spark 4.1 | 7078 | http://localhost:8082 |
| Kafka | 9092 | - |
| Unity Catalog | 8080 | REST API |

## Cloud Deployment

### AWS (EMR + S3 + RDS)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

See [AWS Deployment Guide](docs/deployment/aws.md) | Estimated: $50-500/month

### Databricks

```bash
cd terraform-databricks
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

See [Databricks Deployment Guide](docs/deployment/databricks.md) | Estimated: $100-800/month

## Testing

```bash
# Install test dependencies
poetry install --with dev,test

# Run all tests
poetry run pytest tests/ -v

# Run specific test categories
poetry run pytest tests/ --ignore=tests/integration/  # Unit tests
poetry run pytest tests/integration/ -v               # Integration tests
poetry run pytest -m security -v                      # Security tests

# Multi-version Spark testing
./scripts/test-spark-versions.sh -v 4.0 -v 4.1 -t all
```

## Security

See [SECURITY.md](SECURITY.md) for security guidelines.

```bash
# Install pre-commit hooks
pre-commit install

# Run security checks
pre-commit run --all-files
poetry run pytest -m security -v
```

## Contributing

Contributions welcome! Please:
1. Open an issue first to discuss changes
2. Install pre-commit hooks: `pre-commit install`
3. Run tests before submitting: `poetry run pytest tests/`
4. See [SECURITY.md](SECURITY.md) for security requirements

## License

MIT
