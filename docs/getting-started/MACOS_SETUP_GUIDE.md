# macOS Setup Guide - Lakehouse Stack

Complete step-by-step guide to set up the lakehouse stack on macOS from scratch.

**Last Updated:** April 26, 2026  
**Tested On:** macOS with Docker Desktop 29.2.0

---

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Step-by-Step Installation](#step-by-step-installation)
4. [Issues Encountered & Solutions](#issues-encountered--solutions)
5. [Fresh Start Checklist](#fresh-start-checklist)
6. [Verification](#verification)
7. [Quick Reference](#quick-reference)

---

## Overview

### What Gets Installed

| Component | Version | Purpose | Port |
|-----------|---------|---------|------|
| Python | 3.11+ | Project dependencies | - |
| Poetry | 2.1.0 | Python package manager | - |
| PostgreSQL | 16 | Iceberg catalog metadata | 5432 |
| SeaweedFS | 4.21+ | S3-compatible object storage | 8333 |
| Docker | 29.2.0+ | Container runtime | - |
| Spark | 4.1.0 | Data processing (container) | 7078 |
| Kafka | 7.5.0 | Message broker (container) | 9092 |
| Jupyter | - | Interactive notebooks (container) | 8889 |

### Architecture

```
Your Mac (Host)
├── PostgreSQL 16 (Homebrew) → Iceberg metadata
├── SeaweedFS (Homebrew/Docker) → S3 object storage
└── Docker Desktop
    ├── Spark 4.1 cluster
    ├── Kafka + Zookeeper
    ├── Jupyter Lab
    └── Kafka UI
```

---

## System Requirements

### Minimum Hardware

- **CPU:** 4 cores (8 recommended for Spark)
- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** 20GB free space (for JARs, data, containers)

### Software Prerequisites

- macOS 11+ (Big Sur or newer)
- Docker Desktop 29.0+
- Homebrew installed

### Verify Prerequisites

```bash
# Check Docker
docker --version     # Docker version 29.2.0+
docker compose version  # Docker Compose v2.20+

# Check Homebrew
brew --version       # Homebrew 4.0+
```

---

## Step-by-Step Installation

### Phase 1: Install System Dependencies (macOS)

#### 1.1 Install Python 3.11 & Poetry

```bash
# Install Python 3.11
brew install python@3.11 poetry

# Verify installation
python3.11 --version  # Python 3.11.x
poetry --version      # Poetry 2.1.0+
```

**Why:** Project requires Python 3.11+ for PySpark compatibility.

#### 1.2 Install PostgreSQL 16

```bash
# Install PostgreSQL 16
brew install postgresql@16

# Start PostgreSQL service
brew services start postgresql@16

# Verify it's running
brew services info postgresql@16
# Should show: Running: ✓
```

**Why:** PostgreSQL stores Iceberg table metadata. Spark needs this connection.

#### 1.3 Create PostgreSQL User & Database

```bash
# Create user 'lakehouse' with password 'lakehouse'
createuser -P lakehouse
# When prompted, enter password: lakehouse

# Create database owned by 'lakehouse' user
createdb -O lakehouse iceberg_catalog

# Verify
psql -l
# You should see 'iceberg_catalog' in the list
```

**Why:** Iceberg needs a dedicated database for catalog metadata.

#### 1.4 Install SeaweedFS

```bash
# Install SeaweedFS
brew install seaweedfs

# Create directory for SeaweedFS data
mkdir -p /tmp/seaweedfs

# Start SeaweedFS
weed server -s3 -dir=/tmp/seaweedfs &

# Verify (should return status info)
curl -s http://localhost:8333/status
```

**Why:** SeaweedFS provides S3-compatible object storage. Spark reads/writes data here.

#### 1.5 Install Utilities

```bash
brew install curl netcat
```

---

### Phase 2: Clone Project & Configure

#### 2.1 Clone Repository

```bash
git clone https://github.com/lisancao/lakehouse-at-home.git
cd lakehouse-at-home
```

#### 2.2 Download JARs

```bash
# Run setup script (downloads ~860MB of JARs)
./lakehouse setup

# This step:
# - Downloads Apache JARs for Spark, Iceberg, Kafka connectors
# - Verifies Docker is running
# - Checks Python dependencies
```

**Duration:** 5-10 minutes depending on internet speed.

#### 2.3 Create Data Directory for Docker

On macOS, Docker needs explicit file sharing for `/data` volumes.

```bash
# Create local data directory (easier than sharing /data with Docker)
mkdir -p ./data/spark

# Verify
ls -la ./data
```

---

### Phase 3: Configure Credentials

#### 3.1 Update Spark Configuration

Edit `config/spark/spark-defaults.conf`:

**Replace these lines:**

```properties
# Line 6-7: Update PostgreSQL credentials
spark.sql.catalog.iceberg.jdbc.user      lakehouse
spark.sql.catalog.iceberg.jdbc.password  lakehouse

# Line 12-13: Update S3 credentials (can be any value for local)
spark.hadoop.fs.s3a.access.key           lakehouse
spark.hadoop.fs.s3a.secret.key           lakehouse
```

**Before (placeholder values):**
```properties
spark.sql.catalog.iceberg.jdbc.user      your_username
spark.sql.catalog.iceberg.jdbc.password  your_password
spark.hadoop.fs.s3a.access.key           your_access_key
spark.hadoop.fs.s3a.secret.key           your_secret_key
```

#### 3.2 Update Environment Variables

Edit `.env`:

```bash
# Change this line:
POSTGRES_HOST=host.docker.internal

# To:
POSTGRES_HOST=localhost
```

**Why:** On macOS with Homebrew PostgreSQL, use `localhost` directly (not `host.docker.internal`).

---

### Phase 4: Start Docker Containers

#### 4.1 Modify docker-compose Files

**Update `docker-compose-spark41.yml`:**

Change volume paths from `/data/spark` to relative paths:

```yaml
# BEFORE (won't work on macOS):
volumes:
  - /data/spark:/opt/spark-data
  - /data:/data

# AFTER:
volumes:
  - ./data/spark:/opt/spark-data
  - ./data:/data
```

This applies to BOTH `spark-master-41` and `spark-worker-41` services.

Also remove `network_mode: "host"` (not supported reliably on Docker Desktop for macOS) and expose the needed ports:

```yaml
spark-master-41:
  ports:
    - "7078:7078"   # Spark Master
    - "8082:8082"   # Spark Master UI

spark-worker-41:
  ports:
    - "8083:8083"   # Spark Worker UI
```

**Update `docker-compose-notebooks.yml`:**

Remove `network_mode: "host"` and add port mapping:

```yaml
# BEFORE:
services:
  jupyter:
    network_mode: "host"
    environment:
      - JUPYTER_PORT=8889

# AFTER:
services:
  jupyter:
    ports:
      - "8889:8888"
    environment:
      # REMOVE: - JUPYTER_PORT=8889
```

**Update `docker-compose-kafka.yml`:**

Remove `network_mode: "host"` (use port mappings + internal DNS instead):

```yaml
zookeeper:
  ports:
    - "2181:2181"

kafka:
  ports:
    - "9092:9092"

kafka-ui:
  ports:
    - "8088:8080"
  environment:
    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092
    KAFKA_CLUSTERS_0_ZOOKEEPER: zookeeper:2181
```

#### 4.2 Start Spark Cluster

```bash
docker compose -f docker-compose-spark41.yml up -d

# Verify containers started
docker ps
# Should show: spark-master-41, spark-worker-41
```

#### 4.3 Start Kafka + Zookeeper

```bash
docker compose -f docker-compose-kafka.yml up -d

# Verify containers started
docker ps
# Should show: zookeeper, kafka, kafka-ui
```

#### 4.4 Start Jupyter Lab

```bash
docker compose -f docker-compose-notebooks.yml up -d

# Verify
docker ps
# Should show: jupyter
```

---

### Phase 5: Verify Everything

```bash
# Run all tests
./lakehouse test

# Expected output:
# ✓ PostgreSQL connected
# ✓ SeaweedFS responding
# ✓ Kafka broker healthy
# ✓ Spark master healthy
# All tests passed!
```

---

## Issues Encountered & Solutions

### Issue 1: Docker File Sharing Error

**Error:**
```
mounts denied: The path /data/spark is not shared from the host
```

**Solution:**
- Use relative paths (`./data/spark`) instead of absolute (`/data/spark`)
- Don't try to share `/data` from the host—Docker Desktop on macOS has restrictions

---

### Issue 2: PostgreSQL Not Found by Test Script

**Error:**
```
PostgreSQL failed
→ Check: systemctl status postgresql
```

**Cause:** Test script checks `systemctl` (Linux), but macOS uses Homebrew services.

**Solution:**
1. Check Homebrew PostgreSQL status:
   ```bash
   brew services info postgresql@16
   ```

2. If not running, start it:
   ```bash
   brew services start postgresql@16
   ```

3. Verify credentials in `.env` match your setup:
   ```bash
   POSTGRES_USER=lakehouse
   POSTGRES_PASSWORD=lakehouse
   POSTGRES_HOST=localhost
   ```

---

### Issue 3: SeaweedFS Connection Refused

**Error:**
```
SeaweedFS not responding on port 8333
curl: (7) Failed to connect to localhost port 8333
```

**Causes:**
1. Directory doesn't exist
2. SeaweedFS process crashed
3. Port already in use

**Solutions:**

```bash
# Check if SeaweedFS is running
ps aux | grep weed

# If not running, start it:
mkdir -p /tmp/seaweedfs
weed server -s3 -dir=/tmp/seaweedfs > /tmp/seaweedfs.log 2>&1 &

# Verify
curl -s http://localhost:8333/status

# Or use Docker instead:
docker run -d --name seaweedfs -p 8333:8333 -p 9333:9333 \
  chrislusf/seaweedfs server -s3
```

---

### Issue 4: Jupyter Lab Connection Refused

**Error:**
```
http://localhost:8889 - ERR_CONNECTION_REFUSED
```

**Causes:**
1. `network_mode: "host"` on macOS doesn't work reliably
2. Port conflict
3. Container not running

**Solutions:**

```bash
# Check if container is running
docker ps | grep jupyter

# Remove host network mode from docker-compose-notebooks.yml
# Add proper port mapping: - "8889:8888"

# Restart
docker compose -f docker-compose-notebooks.yml down
docker compose -f docker-compose-notebooks.yml up -d

# Check logs
docker logs jupyter | tail -20
```

---

### Issue 5: PostgreSQL Version Confusion

**Problem:** Multiple PostgreSQL versions installed (16, 18, etc.)

**Solution:**

```bash
# List all installed PostgreSQL versions
brew services list | grep postgresql

# Start the correct version
brew services start postgresql@16

# Check which is running
brew services info postgresql@16  # Should show Running: ✓
```

---

## Fresh Start Checklist

### If Starting From Scratch (Next Time)

Follow this checklist in order:

- [ ] **Step 1: Verify Docker**
  ```bash
  docker --version
  docker compose version
  ```

- [ ] **Step 2: Check Homebrew Services**
  ```bash
  brew services list
  ```

- [ ] **Step 3: Start PostgreSQL**
  ```bash
  brew services start postgresql@16
  psql -l  # Verify databases exist
  ```

- [ ] **Step 4: Start SeaweedFS**
  ```bash
  mkdir -p /tmp/seaweedfs
  weed server -s3 -dir=/tmp/seaweedfs &
  curl -s http://localhost:8333/status
  ```

- [ ] **Step 5: Clone & Setup Project**
  ```bash
  git clone https://github.com/lisancao/lakehouse-at-home.git
  cd lakehouse-at-home
  ./lakehouse setup
  ```

- [ ] **Step 6: Create Local Data Directory**
  ```bash
  mkdir -p ./data/spark
  ```

- [ ] **Step 7: Verify Configuration Files**
  - `config/spark/spark-defaults.conf` - Credentials updated
  - `.env` - POSTGRES_HOST set to `localhost`
  - `docker-compose-*.yml` - File paths use relative paths

- [ ] **Step 8: Start Containers**
  ```bash
  docker compose -f docker-compose-spark41.yml up -d
  docker compose -f docker-compose-kafka.yml up -d
  docker compose -f docker-compose-notebooks.yml up -d
  ```

- [ ] **Step 9: Run Tests**
  ```bash
  ./lakehouse test
  ```

- [ ] **Step 10: Access Services**
  - Jupyter: http://localhost:8889
  - Spark UI: http://localhost:8082
  - Kafka UI: http://localhost:8088

---

## Verification

### Quick Health Check

```bash
# Run all tests
./lakehouse test

# Check all services
docker ps

# Check Homebrew services
brew services list

# Test PostgreSQL
psql -h localhost -U lakehouse -d iceberg_catalog -c "SELECT 1;"

# Test SeaweedFS
curl -s http://localhost:8333/status | head -5

# Test Kafka
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 | head -5
```

### Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| Jupyter Lab | http://localhost:8889 | Interactive notebooks |
| Spark UI | http://localhost:8082 | Cluster monitoring |
| Kafka UI | http://localhost:8088 | Message broker UI |

---

## Quick Reference

### Start All Services

```bash
# Homebrew services (macOS)
brew services start postgresql@16
weed server -s3 -dir=/tmp/seaweedfs &

# Docker containers
docker compose -f docker-compose-spark41.yml up -d
docker compose -f docker-compose-kafka.yml up -d
docker compose -f docker-compose-notebooks.yml up -d

# Verify
./lakehouse test
```

### Stop All Services

```bash
# Stop Docker containers
docker compose -f docker-compose-spark41.yml down
docker compose -f docker-compose-kafka.yml down
docker compose -f docker-compose-notebooks.yml down

# Stop Homebrew services
brew services stop postgresql@16
killall weed  # Stop SeaweedFS
```

### Restart Specific Service

```bash
# PostgreSQL
brew services restart postgresql@16

# SeaweedFS
killall weed
weed server -s3 -dir=/tmp/seaweedfs &

# Spark
docker compose -f docker-compose-spark41.yml restart

# Kafka
docker compose -f docker-compose-kafka.yml restart

# Jupyter
docker compose -f docker-compose-notebooks.yml restart
```

### View Logs

```bash
# PostgreSQL
log show --predicate 'process == "postgres"' --last 1h

# SeaweedFS
tail -f /tmp/seaweedfs.log

# Docker containers
docker logs spark-master-41
docker logs kafka
docker logs jupyter
```

### Troubleshooting Commands

```bash
# Check port availability
lsof -i :5432      # PostgreSQL
lsof -i :8333      # SeaweedFS
lsof -i :7078      # Spark
lsof -i :9092      # Kafka
lsof -i :8889      # Jupyter

# Check running processes
ps aux | grep postgres
ps aux | grep weed
docker ps

# Test connectivity
psql -h localhost -U lakehouse -d iceberg_catalog -c "SELECT 1;"
curl -s http://localhost:8333/status
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

---

## Key Configuration Files

### 1. `.env` - Environment Variables

**Location:** `lakehouse-at-home/.env`

**Critical Settings:**
```bash
POSTGRES_HOST=localhost  # NOT host.docker.internal on macOS
POSTGRES_USER=lakehouse
POSTGRES_PASSWORD=lakehouse
```

### 2. `config/spark/spark-defaults.conf` - Spark Configuration

**Location:** `config/spark/spark-defaults.conf`

**Critical Settings:**
```properties
spark.sql.catalog.iceberg.jdbc.user       lakehouse
spark.sql.catalog.iceberg.jdbc.password   lakehouse
spark.hadoop.fs.s3a.endpoint              http://localhost:8333
spark.hadoop.fs.s3a.access.key            lakehouse
spark.hadoop.fs.s3a.secret.key            lakehouse
```

### 3. Docker Compose Files

**Locations:**
- `docker-compose-spark41.yml` - Spark cluster
- `docker-compose-kafka.yml` - Kafka + Zookeeper
- `docker-compose-notebooks.yml` - Jupyter Lab

**macOS Modifications:**
- Use relative paths: `./data/spark` instead of `/data/spark`
- Remove `network_mode: "host"` from Jupyter
- Use `host.docker.internal` for external service connections in Kafka UI

---

## Common Commands for Daily Use

```bash
# Test all services
./lakehouse test

# Generate test data
./lakehouse testdata generate --days 7
./lakehouse testdata load

# Stream data to Kafka
./lakehouse testdata stream --speed 60

# Submit Spark job
docker exec spark-master-41 /opt/spark/bin/spark-submit /scripts/pipelines/pipeline_spark41.py

# Access Spark shell
docker exec -it spark-master-41 /opt/spark/bin/spark-shell

# View Spark logs
./lakehouse logs spark-master

# Check Kafka topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# View database
psql -h localhost -U lakehouse -d iceberg_catalog
```

---

## Additional Resources

- **Project Documentation:** `docs/`
- **CLI Reference:** `docs/guides/cli-reference.md`
- **Architecture:** `docs/architecture.md`
- **Troubleshooting:** `docs/troubleshooting.md`
- **Pipelines Guide:** `docs/guides/pipelines.md`

---

## Support

If you encounter issues:

1. **Check logs:** `./lakehouse status` and `docker logs <service>`
2. **Run tests:** `./lakehouse test`
3. **Review this guide:** Search for your error message above
4. **Check project issues:** GitHub Issues on the repository

---

**Document Version:** 1.0  
**Last Updated:** April 26, 2026  
**Maintained By:** Lakehouse Team
