# Lakehouse Terraform - Databricks

Terraform configuration for deploying the lakehouse stack on Databricks.

## What Gets Created

| Resource | Description | Notes |
|----------|-------------|-------|
| Unity Catalog | Centralized metadata catalog | Required for governance |
| Schemas | bronze, silver, gold | Medallion architecture |
| Storage Credential | Cloud storage access | AWS IAM or Azure MI |
| External Location | Data lake location | Points to your bucket |
| Interactive Cluster | Development compute | Optional, ~$0.50/DBU |
| SQL Warehouse | Analytics queries | Optional, serverless available |
| ETL Jobs | Scheduled pipelines | Optional |
| Secret Scope | Secure credential storage | For external services |

## Prerequisites

1. **Databricks Workspace** with Unity Catalog enabled (Premium tier)
2. **Cloud Storage** bucket/container created
3. **IAM Role** (AWS) or **Access Connector** (Azure) for storage access
4. **Databricks CLI** or Terraform installed

### Create IAM Role (AWS)

```bash
# Create IAM role for Databricks storage access
aws iam create-role \
  --role-name databricks-storage-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::414351767826:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<your-databricks-account-id>"
        }
      }
    }]
  }'

# Attach S3 permissions
aws iam put-role-policy \
  --role-name databricks-storage-role \
  --policy-name s3-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::your-lakehouse-bucket",
        "arn:aws:s3:::your-lakehouse-bucket/*"
      ]
    }]
  }'
```

### Create Access Connector (Azure)

```bash
# Create Access Connector
az databricks access-connector create \
  --resource-group lakehouse-rg \
  --name lakehouse-access-connector \
  --location eastus \
  --identity-type SystemAssigned

# Grant Storage Blob Data Contributor role
az role assignment create \
  --assignee <access-connector-principal-id> \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>
```

## Quick Start

```bash
# Navigate to terraform-databricks directory
cd terraform-databricks

# Initialize Terraform
terraform init

# Create terraform.tfvars from example
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars

# Preview changes
terraform plan

# Apply (creates resources)
terraform apply

# View outputs
terraform output quick_reference
```

## Configuration Profiles

### Minimal (Dev) - ~$100/month

```hcl
environment                = "dev"
create_interactive_cluster = true
create_sql_warehouse       = false
create_etl_jobs            = false

interactive_cluster_min_workers = 1
interactive_cluster_max_workers = 2
cluster_autotermination_minutes = 30
```

### Standard (Team) - ~$350/month

```hcl
environment                = "dev"
create_interactive_cluster = true
create_sql_warehouse       = true
create_etl_jobs            = false

interactive_cluster_min_workers = 1
interactive_cluster_max_workers = 4

sql_warehouse_size       = "Small"
sql_warehouse_serverless = true
```

### Production - ~$800+/month

```hcl
environment                = "prod"
create_interactive_cluster = true
create_sql_warehouse       = true
create_etl_jobs            = true

interactive_cluster_min_workers = 2
interactive_cluster_max_workers = 8

sql_warehouse_size         = "Medium"
sql_warehouse_max_clusters = 4

notification_emails = ["data-team@example.com"]
```

## Usage

### After Deployment

1. **Get connection info:**
   ```bash
   terraform output quick_reference
   terraform output -raw spark_conf_snippet
   ```

2. **Connect to interactive cluster:**
   - Open Databricks workspace
   - Navigate to Compute
   - Start the `lakehouse-interactive` cluster

3. **Query tables:**
   ```sql
   -- In Databricks SQL or notebook
   USE CATALOG lakehouse;
   SHOW SCHEMAS;
   SHOW TABLES IN bronze;
   ```

### Create Tables

```python
# In Databricks notebook
from pyspark.sql import functions as f

# Create Iceberg table
spark.sql("""
    CREATE TABLE IF NOT EXISTS lakehouse.bronze.events (
        event_id STRING,
        event_type STRING,
        ts TIMESTAMP,
        payload STRING
    ) USING ICEBERG
    PARTITIONED BY (days(ts))
""")

# Insert data
df = spark.createDataFrame([
    ("e1", "order_created", "2024-01-01 10:00:00", "{}"),
    ("e2", "order_shipped", "2024-01-01 11:00:00", "{}")
], ["event_id", "event_type", "ts", "payload"])

df.writeTo("lakehouse.bronze.events").append()
```

### Time Travel

```sql
-- Query historical version
SELECT * FROM lakehouse.bronze.events VERSION AS OF 1;

-- Query by timestamp
SELECT * FROM lakehouse.bronze.events TIMESTAMP AS OF '2024-01-01 00:00:00';

-- Show table history
DESCRIBE HISTORY lakehouse.bronze.events;
```

### Connect BI Tools

Use SQL Warehouse JDBC URL:
```bash
terraform output -raw sql_warehouse_jdbc_url
```

Configure in Tableau, Power BI, or other tools with:
- Host: `<workspace>.cloud.databricks.com`
- HTTP Path: `/sql/1.0/warehouses/<warehouse-id>`
- Auth: Personal access token

## Cost Optimization

1. **Use auto-termination:**
   ```hcl
   cluster_autotermination_minutes = 30  # Default: 60
   sql_warehouse_auto_stop_mins    = 10  # Default: 15
   ```

2. **Enable serverless SQL:**
   ```hcl
   sql_warehouse_serverless = true  # Scales to zero
   ```

3. **Use Jobs clusters for pipelines:**
   Jobs clusters are 50% cheaper than all-purpose clusters.

4. **Schedule clusters to stop:**
   Set low `autotermination_minutes` for dev environments.

5. **Right-size clusters:**
   Start small and scale up based on workload.

## Migrating from Local Stack

1. **Export local data:**
   ```bash
   # On local machine
   spark-submit scripts/export-to-parquet.py \
     --tables iceberg.bronze.orders,iceberg.silver.orders \
     --output ./export/
   ```

2. **Upload to cloud storage:**
   ```bash
   # AWS
   aws s3 cp ./export/ s3://your-bucket/import/ --recursive

   # Azure
   az storage blob upload-batch -d import -s ./export/
   ```

3. **Import in Databricks:**
   ```python
   # Read parquet
   df = spark.read.parquet("s3://your-bucket/import/orders/")

   # Write to Iceberg
   df.writeTo("lakehouse.bronze.orders").createOrReplace()
   ```

## Cleanup

```bash
# Destroy all resources
terraform destroy

# Note: Tables and data in cloud storage are NOT deleted
# Clean up storage manually if needed:
aws s3 rm s3://your-bucket/warehouse --recursive
```

## Troubleshooting

### "Storage credential not found"
Ensure IAM role/Access Connector is properly configured:
```bash
# Check IAM role trust policy
aws iam get-role --role-name databricks-storage-role
```

### "Catalog does not exist"
Unity Catalog must be enabled at the account level:
1. Go to Account Console
2. Enable Unity Catalog
3. Create metastore and assign to workspace

### "Permission denied"
Grant appropriate permissions:
```sql
GRANT USE_CATALOG ON CATALOG lakehouse TO `your-user@email.com`;
GRANT USE_SCHEMA ON SCHEMA lakehouse.bronze TO `your-user@email.com`;
```

### Cluster fails to start
Check:
1. Node type is available in your region
2. Workspace quotas are not exceeded
3. IAM permissions are correct

## Files

| File | Description |
|------|-------------|
| `main.tf` | Main resource definitions |
| `variables.tf` | Input variable definitions |
| `outputs.tf` | Output values |
| `terraform.tfvars.example` | Example variable values |

## See Also

- [Databricks Deployment Guide](../docs/deployment/databricks.md)
- [Databricks Terraform Provider](https://registry.terraform.io/providers/databricks/databricks/latest/docs)
- [Unity Catalog Documentation](https://docs.databricks.com/data-governance/unity-catalog/)
