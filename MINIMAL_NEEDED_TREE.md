# Minimal Needed Files/Folders (Local Setup Focus)

This repo contains a full “lakehouse stack” plus optional monitoring and cloud deployment. If your goal is only local development (Spark + Iceberg, optionally Kafka, optionally notebooks/Airflow/Unity Catalog), you can focus on the items below and ignore the rest for now.

## What You Actually Need (Most Common Local Setup)

**Core idea:** the `./lakehouse` script is the entrypoint. It uses Docker Compose files and mounts `config/`, `scripts/`, `jars/`, `data/` into containers.

### Minimal working set (Spark + Iceberg config)

You will typically touch these files:

- `lakehouse` (CLI entrypoint used for `setup`, `start`, `test`, `status`)
- `.env` (copy from `.env.example` and edit credentials/endpoints)
- `config/spark/spark-defaults.conf` (Spark + Iceberg + S3/SeaweedFS settings)
- A Spark compose file:
  - `docker-compose-spark41.yml` (Spark 4.1, Java 21)
  - or `docker-compose.yml` (Spark 4.0, Java 17)
- `jars/` (Iceberg, Hadoop AWS, Postgres JDBC jars mounted into Spark)
- `scripts/` (quickstarts, pipelines, testdata generator, connectivity checks)

Also important (but you don’t edit them often):

- `pyproject.toml`, `poetry.lock` (Python deps for scripts/tests)
- `docs/getting-started/configuration.md` (explains `.env` + Spark config expectations)

### External services you need running (not “folders” in this repo)

This repo’s Spark configs assume these are reachable on your host:

- PostgreSQL (Iceberg JDBC catalog metadata)
- SeaweedFS S3 endpoint (S3-compatible object storage used by Iceberg warehouse)

Those are referenced by `.env` and `config/spark/spark-defaults.conf`, but they are not defined in the provided docker compose files in this repo.

## Tree: “Needed” (Recommended Minimal Paths)

This is the short tree worth exploring first:

```
lakehouse-at-home/
├── lakehouse
├── .env.example
├── .env                         # local only (create from .env.example)
├── pyproject.toml
├── poetry.lock
├── docker-compose.yml            # Spark 4.0 (simple)
├── docker-compose-spark41.yml    # Spark 4.1 (recommended if you have Java 21)
├── docker-compose-kafka.yml      # only if you need Kafka streaming
├── docker-compose-notebooks.yml  # only if you want Jupyter notebooks
├── config/
│   └── spark/
│       ├── spark-defaults.conf
│       ├── spark-defaults.conf.example
│       ├── spark-defaults-lance.conf.example
│       └── spark-defaults-uc.conf.example
├── jars/
│   ├── iceberg-spark-runtime-4.0_2.13-1.10.0.jar
│   ├── hadoop-aws-3.4.1.jar
│   ├── aws-java-sdk-bundle-1.12.780.jar
│   ├── bundle-2.24.6.jar
│   └── postgresql-42.7.4.jar
├── scripts/
│   ├── README.md
│   ├── quickstarts/
│   │   ├── 01-basics.py
│   │   ├── 02-transformations.py
│   │   ├── 03-streaming-basic.py
│   │   ├── 04-kafka-streaming.py
│   │   ├── iceberg-spark-quickstart.py
│   │   └── unity-catalog-demo.py
│   ├── connectivity/
│   │   ├── test-full-stack.py
│   │   ├── test-iceberg.py
│   │   ├── test-kafka.py
│   │   ├── test-seaweedfs.py
│   │   ├── test-streaming-iceberg.py
│   │   └── test-unity-catalog-live.py
│   ├── pipelines/
│   │   ├── pipeline_sdp.py
│   │   ├── pipeline_spark40.py
│   │   ├── pipeline_spark41.py
│   │   └── spark-pipeline.yml
│   ├── testdata/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── chaos.py
│   │   ├── config.py
│   │   ├── dimensions.py
│   │   ├── events.py
│   │   ├── exporter.py
│   │   └── producer.py
│   └── tools/
│       ├── download-jars.sh
│       ├── kafka-producer.py
│       └── run-spark-test.sh
└── data/                          # optional (sample/generated data used by scripts)
```

## Optional (Keep Only If You Use It)

These are useful, but you can ignore until you explicitly want that capability:

- Airflow orchestration:
  - `docker-compose-airflow.yml`
  - `dags/`
  - `docker/airflow/`
  - `config/airflow/`
- Unity Catalog (REST catalog instead of JDBC Postgres catalog):
  - `docker-compose-unity-catalog.yml`
  - `config/unity-catalog/`
- Notebooks experience:
  - `docker-compose-notebooks.yml`
  - `docker/notebooks/`
  - `notebooks/`
- Tests (good to keep, not required to run the stack):
  - `tests/`
- Documentation (keep for reference; no runtime impact):
  - `docs/`
- Dependency caches (can be deleted; will be re-downloaded):
  - `ivy-cache/`

## Safe To Ignore For Your Ask (Monitoring/Cloud Orchestration)

If you don’t want Prometheus/Grafana or any cloud provisioning, you can skip exploring these entirely:

- Monitoring:
  - `config/prometheus/`
  - `config/grafana/`
- Cloud / orchestration / Terraform:
  - `terraform/`
  - `terraform-databricks/`
  - `docs/deployment/` (AWS/Databricks deployment guides)

## “Smallest” Setup Recipes (How This Maps To Files)

Pick the smallest workflow you want, then only keep/explore the matching files:

- Spark only:
  - `lakehouse`, `.env`, `config/spark/`, `docker-compose.yml` or `docker-compose-spark41.yml`, `jars/`, `scripts/`
- Spark + Kafka streaming:
  - everything above + `docker-compose-kafka.yml`
- Spark + Notebooks:
  - everything above + `docker-compose-notebooks.yml`, `docker/notebooks/`, `notebooks/`
- Spark + Airflow:
  - everything above + `docker-compose-airflow.yml`, `dags/`, `docker/airflow/`, `config/airflow/`

