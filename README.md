# Lakehouse Stack

A fully open-source, self-hostable data lakehouse for local development and testing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| Apache Spark | 4.0 / 4.1 | Distributed compute |
| Apache Iceberg | 1.10 | ACID table format |
| Apache Kafka | 3.6 | Event streaming |
| PostgreSQL | 16 | Catalog metadata |
| SeaweedFS | - | S3-compatible storage |

## Quick Start

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
./lakehouse setup                # Validate and install dependencies
./lakehouse start all            # Start Spark + Kafka
./lakehouse stop all             # Stop all services
./lakehouse status               # Check service health
./lakehouse status --json        # Machine-readable status
./lakehouse test                 # Run connectivity tests
./lakehouse logs spark-master    # View logs
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
| [Architecture](docs/architecture.md) | System design |
| [AWS Deployment](docs/deployment/aws.md) | Cloud production setup |
| [Troubleshooting](docs/troubleshooting.md) | Common issues |

## Architecture

```
Spark 4.x ─────▶ Iceberg 1.10 ─────▶ PostgreSQL (metadata)
                      │
                      ▼
                 SeaweedFS (S3)

Kafka 3.6 ◀──── Streaming ────▶ Iceberg Tables
```

Tables follow medallion architecture:
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

## Cloud Deployment

Deploy to AWS with managed services (RDS, S3, EMR, MSK):

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

See [AWS Deployment Guide](docs/deployment/aws.md) | Estimated: $50-500/month

## Contributing

Contributions welcome! Please open an issue first to discuss changes.

## License

MIT
