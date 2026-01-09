# Lakehouse Stack Setup Guide

This guide walks you through setting up the lakehouse stack from scratch. Follow the instructions for your operating system.

## Quick Start

If you already have all prerequisites installed:

```bash
./lakehouse setup    # Validate environment and install dependencies
./lakehouse start all    # Start all services
./lakehouse test         # Verify everything works
```

## Prerequisites

| Tool | Required | Purpose |
|------|----------|---------|
| Docker + Docker Compose | Yes | Container runtime |
| Poetry | Yes | Python dependency management |
| Python 3.10+ | Yes | Scripts and test data generation |
| curl | Yes | HTTP requests |
| PostgreSQL 16 | Yes | Iceberg catalog metadata |
| SeaweedFS | Yes | S3-compatible object storage |
| Java 17+ | Recommended | Local spark-submit |
| nc (netcat) | Recommended | Port checks |
| psql | Recommended | PostgreSQL testing |

---

## macOS Setup

### 1. Install Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Required Tools

```bash
# Docker Desktop (includes Docker Compose)
brew install --cask docker

# Python and Poetry
brew install python@3.11 poetry

# PostgreSQL
brew install postgresql@16
brew services start postgresql@16

# Utilities
brew install curl netcat
```

### 3. Install SeaweedFS

```bash
brew install seaweedfs

# Start SeaweedFS (S3-compatible on port 8333)
weed server -s3 -dir=/tmp/seaweedfs &
```

Or run SeaweedFS in Docker:
```bash
docker run -d --name seaweedfs -p 8333:8333 -p 9333:9333 \
  chrislusf/seaweedfs server -s3
```

### 4. Configure PostgreSQL

```bash
# Create database user and database
createuser -P lakehouse  # Enter password when prompted
createdb -O lakehouse iceberg_catalog
```

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
# - POSTGRES_USER=lakehouse
# - POSTGRES_PASSWORD=<your_password>
# - S3_ACCESS_KEY=<any_string>
# - S3_SECRET_KEY=<any_string>

cp config/spark/spark-defaults.conf.example config/spark/spark-defaults.conf
# Edit with same credentials
```

### 6. Complete Setup

```bash
./lakehouse setup
./lakehouse start all
./lakehouse test
```

---

## Ubuntu/Debian Setup

### 1. Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### 3. Install Python and Poetry

```bash
# Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"  # Add to ~/.bashrc
```

### 4. Install PostgreSQL

```bash
sudo apt install postgresql-16 postgresql-client-16 -y
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create user and database
sudo -u postgres createuser -P lakehouse
sudo -u postgres createdb -O lakehouse iceberg_catalog
```

### 5. Install SeaweedFS

```bash
# Download latest release
wget https://github.com/seaweedfs/seaweedfs/releases/download/3.59/linux_amd64.tar.gz
tar -xzf linux_amd64.tar.gz
sudo mv weed /usr/local/bin/

# Create data directory and start
mkdir -p ~/seaweedfs-data
weed server -s3 -dir=$HOME/seaweedfs-data &

# Or create a systemd service (recommended for production)
```

### 6. Install Utilities

```bash
sudo apt install curl netcat-openbsd -y
```

### 7. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your credentials

cp config/spark/spark-defaults.conf.example config/spark/spark-defaults.conf
nano config/spark/spark-defaults.conf  # Edit with same credentials
```

### 8. Complete Setup

```bash
./lakehouse setup
./lakehouse start all
./lakehouse test
```

---

## Windows (WSL2) Setup

### 1. Enable WSL2

Open PowerShell as Administrator:
```powershell
wsl --install -d Ubuntu-22.04
```

Restart your computer, then open Ubuntu from the Start menu.

### 2. Install Docker Desktop

1. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. During installation, enable "Use WSL 2 based engine"
3. In Docker Desktop Settings → Resources → WSL Integration, enable your Ubuntu distro

### 3. Follow Ubuntu Instructions

Inside WSL2 Ubuntu terminal, follow the Ubuntu/Debian setup above starting from step 1.

**Important WSL2 Notes:**
- PostgreSQL and SeaweedFS should run inside WSL2, not on Windows
- Use `localhost` for all service connections
- Files in `/mnt/c/` are slow; keep the repo in your WSL2 home directory (`~`)

---

## Troubleshooting

### PostgreSQL Connection Failed

```bash
# Check if PostgreSQL is running
systemctl status postgresql  # Linux
brew services list           # macOS

# Check pg_hba.conf allows local connections
sudo nano /etc/postgresql/16/main/pg_hba.conf
# Ensure this line exists:
# local   all   all   md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### SeaweedFS Not Responding

```bash
# Check if process is running
pgrep -a weed

# Start SeaweedFS
weed server -s3 -dir=/tmp/seaweedfs

# Check port 8333
curl http://localhost:8333
```

### Docker Permission Denied

```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or use sudo with docker commands
```

### JARs Download Failed

```bash
# Manual download
cd jars/
./download-jars.sh

# If wget fails, try curl
curl -O https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.0_2.13/1.10.0/iceberg-spark-runtime-4.0_2.13-1.10.0.jar
```

### Port Already in Use

```bash
# Find process using port
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :8333  # SeaweedFS
sudo lsof -i :9092  # Kafka

# Kill process if needed
kill -9 <PID>
```

### Poetry Install Failed

```bash
# Clear cache and retry
poetry cache clear . --all
poetry install

# If lock file issues
poetry lock --no-update
poetry install
```

---

## Verification Checklist

After setup, verify each component:

| Check | Command | Expected |
|-------|---------|----------|
| Docker | `docker --version` | Version 20+ |
| Docker Compose | `docker compose version` | Version 2+ |
| Poetry | `poetry --version` | Version 1.5+ |
| PostgreSQL | `psql -h localhost -U lakehouse -d iceberg_catalog -c "SELECT 1;"` | Returns 1 |
| SeaweedFS | `curl http://localhost:8333` | HTML response |
| All Services | `./lakehouse test` | All tests pass |

---

## Next Steps

Once setup is complete:

1. **Generate test data**: `./lakehouse testdata generate --days 7`
2. **Start streaming**: `./lakehouse testdata stream --speed 60`
3. **View Spark UI**: http://localhost:8082
4. **Explore scripts**: See `scripts/` directory for examples
