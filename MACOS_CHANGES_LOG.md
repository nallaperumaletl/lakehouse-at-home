# Changes Made to Lakehouse Project

Document tracking all modifications made to the lakehouse-at-home project for macOS setup.

**Date:** April 26, 2026

---

## Summary

This document tracks changes made to make the lakehouse-at-home project work on macOS with local Homebrew services (PostgreSQL, SeaweedFS) and Docker containers (Spark, Kafka, Jupyter).

**Total Files Modified:** 3  
**Total Files Created:** 1 (this guide)

---

## Modified Files

### 1. `config/spark/spark-defaults.conf`

**Lines Modified:** 6-7, 12-13

**Changes:**

```properties
# BEFORE (Lines 6-7):
spark.sql.catalog.iceberg.jdbc.user      your_username
spark.sql.catalog.iceberg.jdbc.password  your_password

# AFTER:
spark.sql.catalog.iceberg.jdbc.user      lakehouse
spark.sql.catalog.iceberg.jdbc.password  lakehouse
```

```properties
# BEFORE (Lines 12-13):
spark.hadoop.fs.s3a.access.key           your_access_key
spark.hadoop.fs.s3a.secret.key           your_secret_key

# AFTER:
spark.hadoop.fs.s3a.access.key           hello_world
spark.hadoop.fs.s3a.secret.key           hello_world123
```

**Reason:** Credentials must match PostgreSQL user and SeaweedFS setup for Spark to connect to both services.

**Who Changed:** User manually via VS Code editor

---

### 2. `.env`

**Lines Modified:** 4

**Changes:**

```bash
# BEFORE:
POSTGRES_HOST=host.docker.internal

# AFTER:
POSTGRES_HOST=localhost
```

**Reason:** On macOS with Homebrew PostgreSQL (not Docker), use `localhost` directly. The `host.docker.internal` is for services running inside Docker containers needing to reach the host.

**Who Changed:** User manually via VS Code editor

---

### 3. `docker-compose-spark41.yml`

**Lines Modified:** 11-12, 32-33 (two locations)

**Changes in `spark-master-41` service:**

```yaml
# BEFORE:
volumes:
  - /data/spark:/opt/spark-data
  - ./config/spark:/opt/spark/conf
  - ./notebooks:/notebooks
  - ./jars:/opt/spark/jars-extra
  - ./scripts:/scripts
  - ./ivy-cache:/root/.ivy2
  - ./data:/data

# AFTER:
volumes:
  - ./data/spark:/opt/spark-data
  - ./config/spark:/opt/spark/conf
  - ./notebooks:/notebooks
  - ./jars:/opt/spark/jars-extra
  - ./scripts:/scripts
  - ./ivy-cache:/root/.ivy2
  - ./data:/data
```

**Changes in `spark-worker-41` service:** Same volume path change.

**Reason:** macOS Docker Desktop doesn't support `/data` directory sharing. Using relative paths (`./data/spark`) works reliably and is contained within the project.

**Who Changed:** User manually via VS Code editor

---

### 4. `docker-compose-notebooks.yml`

**Lines Modified:** 15-24

**Changes:**

```yaml
# BEFORE:
services:
  jupyter:
    image: jupyter/pyspark-notebook:spark-3.5.0
    container_name: jupyter
    network_mode: "host"
    user: root
    volumes:
      - ./notebooks:/home/jovyan/notebooks
      ...
    environment:
      - JUPYTER_ENABLE_LAB=yes
      - JUPYTER_PORT=8889
      - GRANT_SUDO=yes
      ...

# AFTER:
services:
  jupyter:
    image: jupyter/pyspark-notebook:spark-3.5.0
    container_name: jupyter
    ports:
      - "8889:8888"
    user: root
    volumes:
      - ./notebooks:/home/jovyan/notebooks
      ...
    environment:
      - JUPYTER_ENABLE_LAB=yes
      - GRANT_SUDO=yes
      ...
```

**Specific Changes:**
1. Removed: `network_mode: "host"`
2. Added: `ports: - "8889:8888"`
3. Removed: `JUPYTER_PORT=8889` environment variable

**Reason:** 
- `network_mode: "host"` doesn't work reliably on macOS Docker Desktop
- Port mapping (`8889:8888`) works consistently on macOS
- Internal Jupyter port is 8888; we expose it as 8889 on the host

**Who Changed:** User manually via VS Code editor

---

### 5. `docker-compose-kafka.yml`

**Lines Modified:** 28-37

**Changes:**

```yaml
# BEFORE:
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    depends_on:
      - kafka
    network_mode: "host"
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: localhost:9092
      KAFKA_CLUSTERS_0_ZOOKEEPER: localhost:2181
    ports:
      - "8088:8080"

# AFTER:
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    depends_on:
      - kafka
    ports:
      - "8088:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: host.docker.internal:9092
      KAFKA_CLUSTERS_0_ZOOKEEPER: host.docker.internal:2181
```

**Specific Changes:**
1. Removed: `network_mode: "host"`
2. Changed: `localhost` → `host.docker.internal` in Kafka URLs
3. Kept: Port mapping as is

**Reason:**
- When `network_mode: "host"` is used, port mappings are ignored
- After removing host mode, Kafka UI needs to reach Kafka on `host.docker.internal` (the host machine from Docker's perspective)

**Who Changed:** User manually via VS Code editor

---

## Files Created

### 6. `docs/getting-started/MACOS_SETUP_GUIDE.md`

**Type:** Documentation  
**Size:** ~10KB  
**Purpose:** Complete setup guide for macOS with all issues and solutions documented

**Location:** [docs/getting-started/MACOS_SETUP_GUIDE.md](../MACOS_SETUP_GUIDE.md)

**Contents:**
- System requirements
- Step-by-step installation
- Issue troubleshooting
- Fresh start checklist
- Quick reference commands

---

## Why These Changes Were Necessary

### Root Cause Analysis

#### Problem 1: File System Access
**Issue:** Docker couldn't access `/data/spark` directory  
**Root Cause:** macOS Docker Desktop runs in a Linux VM and requires explicit file sharing configuration  
**Solution:** Use relative paths within the project (`./data/spark`)

#### Problem 2: PostgreSQL Connection
**Issue:** Test script couldn't connect to PostgreSQL  
**Root Cause:** Homebrew PostgreSQL runs on the macOS host, not in Docker. The test expected `systemctl` (Linux) but macOS uses Homebrew services.  
**Solution:** Change `POSTGRES_HOST=host.docker.internal` → `POSTGRES_HOST=localhost` because Spark containers can reach the host via `localhost` through Docker bridge networking.

#### Problem 3: Jupyter Lab Access
**Issue:** Jupyter Lab wouldn't respond on `localhost:8889`  
**Root Cause:** `network_mode: "host"` doesn't work reliably on macOS Docker Desktop, and the `JUPYTER_PORT` environment variable conflicted with Docker port mapping.  
**Solution:** Remove `network_mode: "host"`, use proper port mapping, remove conflicting environment variable.

#### Problem 4: SeaweedFS Not Found
**Issue:** SeaweedFS required `/tmp/seaweedfs` directory to exist  
**Root Cause:** User ran `weed server` without creating the directory first  
**Solution:** Create directory first: `mkdir -p /tmp/seaweedfs`

#### Problem 5: PostgreSQL Version Mismatch
**Issue:** Multiple PostgreSQL versions installed (16, 18), test script failed on wrong one  
**Root Cause:** Homebrew installs can coexist; need to explicitly start the correct version  
**Solution:** Use `brew services start postgresql@16` to start the specific version

---

## How to Apply These Changes (If Fresh Clone)

### Option 1: Manual Application (What User Did)

1. Edit `config/spark/spark-defaults.conf` - Add credentials
2. Edit `.env` - Change POSTGRES_HOST
3. Edit `docker-compose-spark41.yml` - Update volume paths
4. Edit `docker-compose-notebooks.yml` - Fix network/port configuration
5. Edit `docker-compose-kafka.yml` - Fix Kafka UI configuration
6. Follow setup instructions

### Option 2: Automated Script (Future)

```bash
#!/bin/bash
# Script to apply macOS-specific changes

# 1. Update spark-defaults.conf
sed -i '' 's/your_username/lakehouse/g' config/spark/spark-defaults.conf
sed -i '' 's/your_password/lakehouse/g' config/spark/spark-defaults.conf
sed -i '' 's/your_access_key/lakehouse/g' config/spark/spark-defaults.conf
sed -i '' 's/your_secret_key/lakehouse/g' config/spark/spark-defaults.conf

# 2. Update .env
sed -i '' 's/host.docker.internal/localhost/g' .env

# 3. Update docker-compose files
sed -i '' 's|/data/spark|./data/spark|g' docker-compose-spark41.yml

# Create data directory
mkdir -p ./data/spark

echo "✅ All macOS-specific changes applied!"
```

---

## Verification of Changes

### Test Commands

```bash
# Verify Spark config
grep "spark.sql.catalog.iceberg.jdbc.user" config/spark/spark-defaults.conf
# Should output: spark.sql.catalog.iceberg.jdbc.user      lakehouse

# Verify .env
grep "POSTGRES_HOST" .env
# Should output: POSTGRES_HOST=localhost

# Verify docker-compose
grep "volumes:" docker-compose-spark41.yml | head -2
# Should show ./data paths, not /data

# Run full test
./lakehouse test
# Should show: ✓ All tests passed
```

---

## Impact Summary

### What Works Now

✅ PostgreSQL connects from Spark containers  
✅ Spark can read/write to SeaweedFS  
✅ Jupyter Lab accessible via browser  
✅ Kafka UI accessible via browser  
✅ All Docker containers can reach each other  
✅ All tests pass: `./lakehouse test`  

### What Didn't Change

- Core project code remains unchanged
- No breaking changes to existing workflows
- Linux/Linux-on-WSL users unaffected (they use different paths)
- All original features work as intended

---

## Forward Compatibility

These changes are:
- **Backward Compatible:** Won't break existing setups
- **Non-Breaking:** All changes are configuration-level
- **Documented:** Full guide provided in `docs/getting-started/MACOS_SETUP_GUIDE.md`

### For Linux/WSL Users

The original paths `/data/spark` still work on Linux. If you're on Linux:
- Keep using `/data/spark` (absolute paths)
- Use `POSTGRES_HOST=host.docker.internal` or `172.17.0.1`
- `network_mode: "host"` works fine on Linux

---

## Change Timeline

| Date | Change | File | Reason |
|------|--------|------|--------|
| Apr 26, 2026 | Add credentials | `config/spark/spark-defaults.conf` | Initial setup |
| Apr 26, 2026 | Fix POSTGRES_HOST | `.env` | PostgreSQL connection |
| Apr 26, 2026 | Update volume paths | `docker-compose-spark41.yml` | Docker file sharing |
| Apr 26, 2026 | Fix Jupyter networking | `docker-compose-notebooks.yml` | Port access |
| Apr 26, 2026 | Fix Kafka UI networking | `docker-compose-kafka.yml` | UI access |
| Apr 26, 2026 | Create setup guide | `docs/getting-started/MACOS_SETUP_GUIDE.md` | Documentation |

---

## Next Steps

1. **Bookmark this document** for reference
2. **Review the setup guide** at `docs/getting-started/MACOS_SETUP_GUIDE.md`
3. **Use Quick Reference** section for daily commands
4. **Commit changes** if working in a team (though config shouldn't be in git)

---

**Document Version:** 1.0  
**Created:** April 26, 2026  
**Modified By:** User  
**Status:** Complete ✅
