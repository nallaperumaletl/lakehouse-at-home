# Lakehouse Stack Documentation

Welcome to the Lakehouse Stack documentation. This guide covers everything you need to set up, run, and deploy a fully open-source data lakehouse.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Quickstart](getting-started/quickstart.md) | Get up and running in 5 minutes |
| [Installation](getting-started/installation.md) | Detailed setup for macOS, Ubuntu, Windows |
| [Data Pipelines](guides/pipelines.md) | Build medallion pipelines (imperative vs declarative) |
| [CLI Reference](guides/cli-reference.md) | All available commands |
| [AWS Deployment](deployment/aws.md) | Deploy to production on AWS |
| [Databricks Deployment](deployment/databricks.md) | Deploy to Databricks |

## What is Lakehouse Stack?

A self-hostable data lakehouse combining:

- **Apache Spark 4.x** - Distributed compute engine
- **Apache Iceberg 1.10** - ACID table format
- **Apache Kafka 3.6** - Event streaming
- **PostgreSQL 16** - Catalog metadata
- **SeaweedFS** - S3-compatible storage

## Documentation Structure

```
docs/
├── getting-started/
│   ├── quickstart.md       # 5-minute setup
│   ├── installation.md     # OS-specific install guides
│   └── configuration.md    # Environment and Spark config
├── guides/
│   ├── cli-reference.md    # All CLI commands
│   ├── pipelines.md        # Data pipelines (imperative vs declarative)
│   ├── test-data.md        # Generating test data
│   ├── streaming.md        # Kafka streaming examples
│   └── multi-version.md    # Running Spark 4.0 and 4.1
├── deployment/
│   ├── local.md            # Local development setup
│   ├── aws.md              # AWS production deployment
│   └── databricks.md       # Databricks deployment
├── architecture.md         # System design and data flow
└── troubleshooting.md      # Common issues and solutions
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/lisancao/lakehouse-at-home/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lisancao/lakehouse-at-home/discussions)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on contributing to this project.
