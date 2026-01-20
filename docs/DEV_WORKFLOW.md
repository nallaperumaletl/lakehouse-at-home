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
master/develop (dadf981) - In sync
    │
    │   [MERGED] Phase 0-1: CI/CD, testing, security
    │
    ├── feature/lance-multimodal (b4eba29) - Lance/LanceDB integration
    │
    ├── feature/unity-catalog-oss (385eeac) - Unity Catalog [PR #11]
    │       └── Rebased on develop, integration tests added
    │
    └── feature/airflow-orchestration (0639417) - Airflow + Unity Catalog
```

### Branch Contents

| Branch | Purpose | Status | Key Files |
|--------|---------|--------|-----------|
| `master/develop` | Main branches (synced) | Active | All core infrastructure |
| `feature/lance-multimodal` | Lance vector DB | Ready for PR | `docker-compose-lance.yml`, `scripts/05-10*.py` |
| `feature/unity-catalog-oss` | Unity Catalog | **PR #11 Open** | `docker-compose-unity-catalog.yml`, `docs/guides/unity-catalog.md`, `tests/integration/test_unity_catalog.py` |
| `feature/airflow-orchestration` | Airflow DAGs | Blocked (needs UC) | `dags/`, `docker-compose-airflow.yml` |

### What's in master/develop

After Phase 0-1 merge:
- Comprehensive CI/CD pipeline (`.github/workflows/ci.yml`)
- Integration test suite (`tests/integration/`)
- Security infrastructure (`SECURITY.md`, `.pre-commit-config.yaml`, `tests/test_security.py`)
- Enhanced CLI with preflight checks (`lakehouse`)
- JAR download with retry logic (`scripts/download-jars.sh`)
- Multi-version Spark testing (`scripts/test-spark-versions.sh`)
- Schema migrations (`schemas/`)

### Pending in feature/unity-catalog-oss (PR #11)

- Unity Catalog OSS deployment (`docker-compose-unity-catalog.yml`)
- Spark REST catalog configuration (`config/spark/spark-defaults-uc.conf.example`)
- Unity Catalog guide (`docs/guides/unity-catalog.md`)
- Demo script (`scripts/unity_catalog_demo.py`)
- Integration tests (`tests/integration/test_unity_catalog.py` - 17 tests)

## Integration Plan

### Phase Status

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 0-1 | Foundation hardening, CI/CD, tests, security | **DONE** | Merged to master |
| 2 | Unity Catalog OSS | **PR OPEN** | PR #11, rebased with tests |
| 3 | Lance + multimodal | Ready | Can PR now (parallel with Phase 2) |
| 4 | Airflow orchestration | Blocked | Needs Phase 2 first |

### Merge Order (Dependencies)

```
[DONE] 1. Phase 0-1 → develop → master
[PR #11] 2. feature/unity-catalog-oss → develop (17 tests, rebased)
[READY] 3. feature/lance-multimodal → develop (no blocking deps)
[BLOCKED] 4. feature/airflow-orchestration → develop (needs Phase 2)
```

## Security Requirements

Before merging any PR:

1. **Run pre-commit hooks**: `pre-commit run --all-files`
2. **Run security tests**: `poetry run pytest -m security -v`
3. **Check for secrets**: No hardcoded credentials
4. **Verify CI passes**: All stages green

See `SECURITY.md` for full guidelines.

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

# Check CI status
gh run list --limit 5
```

### Testing

```bash
# Install dependencies
poetry install --with dev,test

# Run all tests
poetry run pytest tests/ -v

# Run by category
poetry run pytest tests/ --ignore=tests/integration/  # Unit only
poetry run pytest tests/integration/ -v               # Integration only
poetry run pytest -m security -v                      # Security only

# Multi-version Spark tests
./scripts/test-spark-versions.sh -v 4.1 -t all

# Lint/format
poetry run ruff check scripts/ tests/ --fix
poetry run black scripts/ tests/

# Security checks
pre-commit run --all-files
```

### PR Workflow

```bash
# Create PR to develop
gh pr create --base develop --title "feat: description"

# Check PR status
gh pr list
gh pr checks PR_NUMBER

# Merge PR (after approval)
gh pr merge PR_NUMBER --squash
```

### Service Management

```bash
# Setup (first time)
./lakehouse setup

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
2. Pull latest: `git pull origin develop`
3. Check for uncommitted changes: `git status --short`
4. Review this file for current integration status
5. Read `SECURITY.md` for security guidelines

### When Creating New Features

1. Branch from `develop`: `git checkout -b feature/NAME develop`
2. Install pre-commit hooks: `pre-commit install`
3. Make changes with tests
4. Run `poetry run pytest tests/`
5. Run `pre-commit run --all-files`
6. Create PR to `develop` (not `master`)

### When Merging Branches

1. Check dependencies in "Merge Order" above
2. Ensure CI passes on the PR
3. Run security tests: `poetry run pytest -m security`
4. Merge to develop first, then develop → master
5. Update this file with new branch state

### Critical Files

| File | Purpose | Caution |
|------|---------|---------|
| `lakehouse` | CLI script | Security-sensitive (input validation) |
| `config/spark/spark-defaults.conf` | Spark config | **Never commit** (credentials) |
| `.env` | Environment variables | **Never commit** (credentials) |
| `scripts/download-jars.sh` | JAR downloads | Version-sensitive |
| `.github/workflows/ci.yml` | CI pipeline | Security-sensitive (pinned actions) |
| `.pre-commit-config.yaml` | Security hooks | Keep updated |

### Version Constraints (Do Not Change)

- AWS SDK v2: **2.24.6** (exact match for Hadoop 3.4.1)
- Iceberg: **1.10.0**
- Spark: **4.0.1** or **4.1.0** (Scala 2.13)
- Poetry: **2.1.0**

## Updating This Document

When branch state changes significantly:
1. Update "Branch Relationships" diagram
2. Update "Branch Contents" table
3. Update "Phase Status" table
4. Commit: `git commit -m "docs: update DEV_WORKFLOW branch state"`
