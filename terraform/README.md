# Lakehouse Terraform Infrastructure

Terraform configuration for deploying the lakehouse stack on AWS.

## What Gets Created

| Resource | Description | Estimated Cost |
|----------|-------------|----------------|
| VPC | Network with public/private subnets | Free |
| S3 Bucket | Data lake storage with versioning | ~$3/100GB |
| RDS PostgreSQL | Iceberg catalog (db.t3.micro) | ~$15/month |
| NAT Gateway | Private subnet internet access | ~$32/month |
| EMR Cluster | Spark cluster (optional) | ~$200/month |

## Quick Start

```bash
# Initialize Terraform
cd terraform
terraform init

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
aws_region      = "us-west-2"
project_name    = "lakehouse"
environment     = "dev"
s3_bucket_name  = "my-lakehouse-data-$(date +%s)"  # Must be globally unique
db_password     = "YourSecurePassword123!"

# Set to true to create EMR cluster (adds ~$200/month)
create_emr_cluster = false
EOF

# Preview changes
terraform plan

# Apply (creates resources)
terraform apply

# Get outputs for configuration
terraform output -raw env_file_content > ../.env.aws
```

## Configuration Options

### Minimal (Dev) - ~$50/month
```hcl
environment        = "dev"
rds_instance_class = "db.t3.micro"
create_emr_cluster = false
enable_nat_gateway = true
```

### With EMR - ~$250/month
```hcl
environment            = "dev"
create_emr_cluster     = true
emr_master_instance_type = "m5.xlarge"
emr_core_instance_type   = "m5.xlarge"
emr_core_instance_count  = 2
```

### Production - ~$500+/month
```hcl
environment            = "prod"
rds_instance_class     = "db.t3.medium"
create_emr_cluster     = true
emr_master_instance_type = "m5.2xlarge"
emr_core_instance_type   = "m5.2xlarge"
emr_core_instance_count  = 4
```

## Usage

### After Deployment

1. **Get the generated .env file:**
   ```bash
   terraform output -raw env_file_content > ../.env.aws
   ```

2. **Update spark-defaults.conf** with RDS endpoint:
   ```bash
   RDS_ENDPOINT=$(terraform output -raw rds_address)
   S3_BUCKET=$(terraform output -raw s3_bucket_name)
   echo "RDS: $RDS_ENDPOINT"
   echo "S3:  $S3_BUCKET"
   ```

3. **Connect to EMR** (if created):
   ```bash
   EMR_MASTER=$(terraform output -raw emr_master_dns)
   ssh -i your-key.pem hadoop@$EMR_MASTER
   ```

### Submit Spark Jobs

```bash
# Using AWS CLI
aws emr add-steps --cluster-id $(terraform output -raw emr_cluster_id) \
  --steps Type=Spark,Name="My Job",ActionOnFailure=CONTINUE,\
Args=[--deploy-mode,cluster,s3://your-bucket/scripts/job.py]

# Or SSH to master and use spark-submit
ssh hadoop@$(terraform output -raw emr_master_dns)
spark-submit --master yarn s3://your-bucket/scripts/job.py
```

## Cost Optimization

1. **Stop EMR when not in use:**
   ```bash
   terraform apply -var="create_emr_cluster=false"
   ```

2. **Use Spot instances** (add to main.tf):
   ```hcl
   core_instance_group {
     instance_type  = "m5.xlarge"
     instance_count = 2
     bid_price      = "0.10"  # Spot price
   }
   ```

3. **Disable NAT Gateway** for testing (no internet in private subnets):
   ```bash
   terraform apply -var="enable_nat_gateway=false"
   ```

## Cleanup

```bash
# Destroy all resources
terraform destroy

# Note: S3 bucket must be empty before destruction
aws s3 rm s3://$(terraform output -raw s3_bucket_name) --recursive
terraform destroy
```

## Troubleshooting

### "Bucket already exists"
S3 bucket names are globally unique. Use a unique suffix:
```hcl
s3_bucket_name = "lakehouse-${random_id.bucket.hex}"
```

### "Cannot connect to RDS"
RDS is in a private subnet. Connect via:
- EMR master node (SSH tunnel)
- VPN/Direct Connect
- Bastion host

### EMR fails to start
Check:
1. NAT Gateway is enabled (for downloading packages)
2. IAM roles are correct
3. Security groups allow internal traffic
