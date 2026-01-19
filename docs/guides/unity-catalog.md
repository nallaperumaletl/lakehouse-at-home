# Unity Catalog OSS Integration

Unity Catalog OSS provides an alternative to the PostgreSQL JDBC catalog with enhanced features for multi-format support and interoperability.

## Why Unity Catalog?

| Feature | PostgreSQL JDBC | Unity Catalog OSS |
|---------|----------------|-------------------|
| Catalog Protocol | JDBC (direct SQL) | REST API (HTTP) |
| Formats | Iceberg only | Delta + Iceberg + Hudi (UniForm) |
| Auth | Hardcoded credentials | Credential vending |
| Interoperability | Spark only | Spark + DuckDB + Trino + Dremio |
| Governance | Manual | Built-in access control |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Applications                         │
│         (Spark, DuckDB, Trino, Python, etc.)                │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Unity Catalog Server (port 8080)                │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  UC REST API    │  │  Iceberg REST   │                   │
│  │  /catalogs      │  │  Catalog API    │                   │
│  │  /schemas       │  │  /iceberg/v1/   │                   │
│  │  /tables        │  │                 │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                          │                                   │
│              ┌───────────┴───────────┐                      │
│              │   Credential Vending   │                      │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  SeaweedFS (S3-compatible)                   │
│                   s3://lakehouse/warehouse                   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Configure Unity Catalog

```bash
# Copy example config
cp config/unity-catalog/server.properties.example config/unity-catalog/server.properties

# Edit with your SeaweedFS credentials
nano config/unity-catalog/server.properties
```

Update the S3 settings:
```properties
s3.bucketPath.0=s3://lakehouse/warehouse
s3.region.0=us-east-1
s3.accessKey.0=your_seaweedfs_access_key
s3.secretKey.0=your_seaweedfs_secret_key
s3.endpoint.0=http://localhost:8333
```

### 2. Start Unity Catalog

```bash
./lakehouse start unity-catalog
```

### 3. Verify It's Running

```bash
# Check status
./lakehouse status

# Test the API
curl http://localhost:8080/api/2.1/unity-catalog/catalogs

# Run full tests
./lakehouse test
```

### 4. Configure Spark to Use Unity Catalog

Copy the Unity Catalog Spark config:
```bash
cp config/spark/spark-defaults-uc.conf.example config/spark/spark-defaults.conf
```

Or add these settings to your existing config:
```properties
spark.sql.catalog.iceberg                 org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.catalog-impl    org.apache.iceberg.rest.RESTCatalog
spark.sql.catalog.iceberg.uri             http://localhost:8080/api/2.1/unity-catalog/iceberg
spark.sql.catalog.iceberg.warehouse       unity
spark.sql.catalog.iceberg.token           not_used
```

### 5. Create Tables

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("UC-Demo") \
    .getOrCreate()

# Create schema
spark.sql("CREATE SCHEMA IF NOT EXISTS iceberg.bronze")

# Create table
spark.sql("""
    CREATE TABLE iceberg.bronze.orders (
        order_id STRING,
        customer_id STRING,
        total DECIMAL(10,2),
        created_at TIMESTAMP
    ) USING ICEBERG
""")

# Insert data
spark.sql("""
    INSERT INTO iceberg.bronze.orders VALUES
    ('ord-001', 'cust-1', 99.99, current_timestamp()),
    ('ord-002', 'cust-2', 149.99, current_timestamp())
""")

# Query
spark.sql("SELECT * FROM iceberg.bronze.orders").show()
```

## CLI Commands

```bash
# Start Unity Catalog
./lakehouse start unity-catalog

# Stop Unity Catalog
./lakehouse stop unity-catalog

# View logs
./lakehouse logs unity-catalog

# Check status
./lakehouse status
```

## REST API Examples

### List Catalogs

```bash
curl http://localhost:8080/api/2.1/unity-catalog/catalogs
```

### Create Schema

```bash
curl -X POST http://localhost:8080/api/2.1/unity-catalog/schemas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "bronze",
    "catalog_name": "unity"
  }'
```

### List Tables

```bash
curl "http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze"
```

## Using with DuckDB

Unity Catalog OSS works with DuckDB for local analytics:

```sql
-- Install extensions
INSTALL uc_catalog FROM core_nightly;
LOAD uc_catalog;
INSTALL delta;
LOAD delta;

-- Connect to Unity Catalog
CREATE SECRET (
    TYPE UC,
    TOKEN 'not_used',
    ENDPOINT 'http://127.0.0.1:8080',
    AWS_REGION 'us-east-1'
);

ATTACH 'unity' AS unity (TYPE UC_CATALOG);

-- Query tables
SELECT * FROM unity.bronze.orders;
```

## Migration from PostgreSQL JDBC

### Side-by-Side Testing

You can run both catalogs simultaneously:

1. Keep your existing PostgreSQL JDBC catalog as `iceberg`
2. Add Unity Catalog as a new catalog `unity`

```properties
# Existing JDBC catalog
spark.sql.catalog.iceberg           org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.type      jdbc
spark.sql.catalog.iceberg.uri       jdbc:postgresql://localhost:5432/iceberg_catalog

# New Unity Catalog (different name)
spark.sql.catalog.unity             org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.unity.catalog-impl org.apache.iceberg.rest.RESTCatalog
spark.sql.catalog.unity.uri         http://localhost:8080/api/2.1/unity-catalog/iceberg
```

Then migrate tables:
```python
# Read from old catalog
df = spark.table("iceberg.bronze.orders")

# Write to new catalog
df.writeTo("unity.bronze.orders").createOrReplace()
```

### Full Migration

Once validated:

1. Stop applications
2. Update `spark-defaults.conf` to use Unity Catalog config
3. Restart Spark cluster
4. Verify all queries work
5. Decommission PostgreSQL JDBC catalog

## Configuration Reference

### server.properties

| Property | Description | Example |
|----------|-------------|---------|
| `server.port` | HTTP port | `8080` |
| `s3.bucketPath.N` | S3 bucket path | `s3://lakehouse/warehouse` |
| `s3.accessKey.N` | S3 access key | `your_key` |
| `s3.secretKey.N` | S3 secret key | `your_secret` |
| `s3.endpoint.N` | Custom S3 endpoint | `http://localhost:8333` |
| `s3.region.N` | AWS region | `us-east-1` |

### Spark Configuration

| Property | Description |
|----------|-------------|
| `spark.sql.catalog.iceberg.catalog-impl` | Must be `org.apache.iceberg.rest.RESTCatalog` |
| `spark.sql.catalog.iceberg.uri` | Unity Catalog Iceberg endpoint |
| `spark.sql.catalog.iceberg.warehouse` | Catalog name in Unity Catalog |
| `spark.sql.catalog.iceberg.token` | Auth token (use `not_used` for local) |

## Troubleshooting

### Unity Catalog Won't Start

```bash
# Check logs
docker logs unity-catalog

# Verify config exists
ls -la config/unity-catalog/server.properties

# Check port availability
nc -z localhost 8080 && echo "Port in use" || echo "Port available"
```

### Spark Can't Connect

1. Verify Unity Catalog is running:
   ```bash
   curl http://localhost:8080/api/2.1/unity-catalog/catalogs
   ```

2. Check Spark config:
   ```bash
   grep -i "catalog.iceberg" config/spark/spark-defaults.conf
   ```

3. Ensure correct endpoint in Spark:
   ```
   http://localhost:8080/api/2.1/unity-catalog/iceberg
   ```

### Tables Not Visible

1. Check schema exists:
   ```bash
   curl "http://localhost:8080/api/2.1/unity-catalog/schemas?catalog_name=unity"
   ```

2. Verify table was created:
   ```bash
   curl "http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze"
   ```

## Resources

- [Unity Catalog Documentation](https://docs.unitycatalog.io/)
- [Unity Catalog GitHub](https://github.com/unitycatalog/unitycatalog)
- [Iceberg REST Catalog Spec](https://iceberg.apache.org/concepts/catalog/)
