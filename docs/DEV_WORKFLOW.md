# Development Workflow for Claude Assistants

This document provides context for AI assistants working on the lakehouse-stack project.

## Branch Strategy

```
master ← develop ← feature branches
```

- **`master`**: Production releases only
- **`develop`**: Integration branch, all features merge here first
- **`feature/*`**: Individual feature work, PRs target `develop`

## Current Branch State (Updated: 2026-01-19)

### Branch Relationships

```
master/develop (ab72f29) - Base
    │
    ├── iceberg-spark (5393014) - Iceberg tutorials, SDP docs
    │       │
    │       └── feature/integration-testing (4b376e5) - CI/CD, tests [PR #14]
    │
    ├── multimodal (ad65f11) - Pipeline transforms, Lance scripts
    │
    ├── feature/unity-catalog-oss (d6303f8) - Unity Catalog integration
    │
    └── feature/airflow-orchestration (0639417) - Airflow + Unity Catalog
```

### Branch Contents

| Branch | Purpose | Key Files |
|--------|---------|-----------|
| `feature/integration-testing` | CI/CD, pytest, poetry | `.github/workflows/ci.yml`, `tests/integration/`, `pyproject.toml` |
| `iceberg-spark` | Iceberg tutorials | `scripts/04-iceberg-spark-quickstart.py`, `docs/guides/` |
| `multimodal` | Pipeline tests | `tests/test_pipeline_transformations.py` |
| `feature/unity-catalog-oss` | Unity Catalog | `docker-compose-unity-catalog.yml`, `docs/guides/unity-catalog.md` |
| `feature/airflow-orchestration` | Airflow DAGs | `dags/`, `docker-compose-airflow.yml` |

### Uncommitted Work

Lance/multimodal files exist in working directory but are **not committed**:
- `config/lance/`, `config/grafana/`, `config/prometheus/`
- `docker-compose-lance.yml`, `docker-compose-lance-prod.yml`
- `scripts/05-lance-quickstart.py` through `scripts/10-hybrid-lance-iceberg.py`
- `tests/test_lance_integration.py`

**Action needed**: Commit these to a `feature/lance-multimodal` branch.

## Integration Plan

### Phase Status

| Phase | Description | Status | PR |
|-------|-------------|--------|-----|
| 0-1 | Foundation hardening, CI/CD, tests | Done | #14 |
| 2 | Unity Catalog OSS | Pending | - |
| 3 | Lance + multimodal | Pending | - |
| 4 | Airflow orchestration | Pending | - |

### Merge Order (Dependencies)

```
1. feature/integration-testing → develop (no deps)
2. feature/unity-catalog-oss → develop (needs Phase 1)
3. feature/lance-multimodal → develop (needs Phase 1)
4. feature/airflow-orchestration → develop (needs Phase 2)
```

## Commands Reference

### Check Branch State

```bash
# List all branches
git branch -a

# Compare branch to develop
git log --oneline develop..BRANCH_NAME

# View diff stats
git diff --stat develop...BRANCH_NAME

# Check uncommitted files
git status --short
```

### Testing

```bash
# Install dependencies
poetry install

# Run unit tests
poetry run pytest tests/ --ignore=tests/integration/

# Run integration tests (requires Docker)
poetry run pytest tests/integration/ -v

# Multi-version Spark tests
./scripts/test-spark-versions.sh -v 4.1 -t all

# Lint/format
poetry run ruff check scripts/ tests/
poetry run black --check scripts/ tests/
```

### PR Workflow

```bash
# Create PR to develop
gh pr create --base develop --title "feat: description" --body "..."

# Check PR status
gh pr list

# View PR checks
gh pr checks PR_NUMBER
```

### Service Management

```bash
# Start all services
./lakehouse start all

# Check status
./lakehouse status --json

# Run connectivity tests
./lakehouse test

# View logs
./lakehouse logs spark-master-41
```

## For Claude Assistants

### Before Starting Work

1. Check current branch: `git branch --show-current`
2. Check for uncommitted changes: `git status --short`
3. Pull latest: `git fetch origin`
4. Review this file for current integration status

### When Creating New Features

1. Branch from `develop`: `git checkout -b feature/NAME develop`
2. Make changes with tests
3. Run `poetry run pytest tests/`
4. Create PR to `develop` (not `master`)

### When Merging Branches

1. Check dependencies in "Merge Order" above
2. Ensure target branch's dependencies are merged first
3. Run full test suite after merge
4. Update this file with new branch state

### Critical Files

| File | Purpose | Caution |
|------|---------|---------|
| `lakehouse` | CLI script | Main user interface |
| `config/spark/spark-defaults.conf` | Spark config | Contains credentials |
| `scripts/download-jars.sh` | JAR downloads | Version-sensitive |
| `.github/workflows/ci.yml` | CI pipeline | Affects all PRs |

### Version Constraints (Do Not Change)

- AWS SDK v2: **2.24.6** (exact match for Hadoop 3.4.1)
- Iceberg: **1.10.0**
- Spark: **4.0.1** or **4.1.0** (Scala 2.13)

## Updating This Document

When branch state changes significantly:
1. Update "Branch Relationships" diagram
2. Update "Branch Contents" table
3. Update "Phase Status" table
4. Commit: `git commit -m "docs: update DEV_WORKFLOW branch state"`
