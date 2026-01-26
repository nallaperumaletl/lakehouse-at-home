# Development Workflow

This document defines the development workflow for the lakehouse-stack project.

## Golden Rule

**Always work from `develop`. Always test locally before pushing.**

```
git pull origin develop    # Start here
# ... make changes ...
# ... run local tests ...
git push origin develop    # Only after tests pass
```

## Branch Strategy

```
master ← develop ← feature branches
```

| Branch | Purpose | Who pushes |
|--------|---------|------------|
| `master` | Production releases | Merge from develop only |
| `develop` | **Primary working branch** | All development |
| `feature/*` | Isolated feature work | PRs to develop |

## Local Testing (Required Before Push)

Before pushing ANY changes to develop, run these stability tests:

### 1. Quick Validation (Always)

```bash
# Syntax and lint checks
poetry run ruff check scripts/ tests/ dags/
poetry run black --check scripts/ tests/ dags/

# Unit tests (fast)
poetry run pytest tests/ --ignore=tests/integration/ -v
```

### 2. Full Local Test (Before Significant Changes)

```bash
# All tests including integration
poetry run pytest tests/ -v

# Security checks
poetry run pytest -m security -v
pre-commit run --all-files

# CLI validation
./lakehouse setup
./lakehouse status --json
```

### 3. Service Tests (When Touching Infrastructure)

```bash
# Start services
./lakehouse start all

# Run connectivity tests
./lakehouse test

# Test Spark versions
./scripts/connectivity/test-spark-versions.sh -v 4.1 -t all

# Stop services
./lakehouse stop all
```

### 4. Airflow Tests (When Touching DAGs)

```bash
# DAG syntax validation
poetry run pytest tests/test_airflow_dags.py -v

# Build and test Airflow locally
docker compose -f docker-compose-airflow.yml build
docker compose -f docker-compose-airflow.yml up -d
# Check http://localhost:8085 loads and DAGs appear
docker compose -f docker-compose-airflow.yml down
```

## Daily Workflow

### Starting Work

```bash
# 1. Always start from develop
git checkout develop
git pull origin develop

# 2. Check current state
git status --short
./lakehouse status --json
```

### Making Changes

```bash
# 3. Make your changes
# ... edit files ...

# 4. Run local tests (REQUIRED)
poetry run pytest tests/ --ignore=tests/integration/ -v
poetry run ruff check scripts/ tests/ dags/

# 5. Commit
git add <specific files>
git commit -m "type: description"

# 6. Push only after tests pass
git push origin develop
```

### Feature Branches (For Larger Work)

```bash
# Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# Work on feature...
# Run local tests...

# Create PR to develop
gh pr create --base develop --title "feat: description"

# After PR approved and CI passes, merge
gh pr merge --squash
```

## CI/CD Pipeline

CI runs automatically on push to develop. However, **local testing catches issues faster**.

| Stage | What it checks | Run locally with |
|-------|----------------|------------------|
| Lint | Code style | `poetry run ruff check .` |
| Security | Credentials, vulnerabilities | `pre-commit run --all-files` |
| Unit Tests | Logic correctness | `poetry run pytest tests/ --ignore=tests/integration/` |
| Integration | Service connectivity | `poetry run pytest tests/integration/` |
| Build | Docker images | `docker compose build` |

## Current State (Updated: 2026-01-25)

### What's in develop

- Core infrastructure (Spark 4.0/4.1, Iceberg 1.10, Kafka 3.6)
- Airflow 3.1.6 orchestration (`dags/`, `docker-compose-airflow.yml`)
- Comprehensive CI/CD pipeline
- Integration test suite
- Scripts reorganized into `quickstarts/`, `connectivity/`, `pipelines/`, `tools/`
- Test data generation framework

### Active Feature Branches

| Branch | Purpose | Status |
|--------|---------|--------|
| `feature/unity-catalog-oss` | Unity Catalog OSS | PR #11 open |
| `documentation` | Docs improvements | Active |

### Archived/Removed

- Lance/LanceDB integration (moved to separate branch, not in develop)

## Critical Versions (Do Not Change Without Testing)

| Component | Version | Notes |
|-----------|---------|-------|
| AWS SDK v2 | 2.24.6 | Exact match for Hadoop 3.4.1 |
| Iceberg | 1.10.0 | |
| Spark | 4.0.1 / 4.1.0 | Scala 2.13 |
| Airflow | 3.1.6 | Python 3.12, breaking changes from 2.x |
| Java (Spark 4.0) | 17 | From official image |
| Java (Spark 4.1) | 21 | From official image |
| Java (Airflow) | 17 | Sufficient for scheduling |

## Files That Should Never Be Committed

| File | Why |
|------|-----|
| `.env` | Contains credentials |
| `config/spark/spark-defaults.conf` | Contains credentials |
| `*.jar` | Large binaries |
| `logs/` | Runtime artifacts |
| `.coverage` | Test artifacts |

## Troubleshooting

### Tests Fail Locally But Pass in CI

```bash
# Ensure clean state
poetry install --with dev,test
git clean -fd  # Remove untracked files (careful!)
```

### CI Fails But Tests Pass Locally

```bash
# Check you have latest develop
git pull origin develop

# Run the exact CI commands
poetry run ruff check scripts/ tests/ dags/ --config pyproject.toml
poetry run pytest tests/ -v --tb=short
```

### Merge Conflicts

```bash
# Update develop first
git checkout develop
git pull origin develop

# Rebase your feature branch
git checkout feature/my-feature
git rebase develop

# Resolve conflicts, then continue
git rebase --continue
```

## For AI Assistants

1. **Always pull develop first**: `git pull origin develop`
2. **Run tests before suggesting push**: `poetry run pytest tests/ -v`
3. **Check CI status after push**: `gh run list --limit 3`
4. **Update this doc when branch state changes significantly**
