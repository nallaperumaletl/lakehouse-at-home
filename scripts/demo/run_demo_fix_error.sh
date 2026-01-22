#!/bin/bash
# Spark Declarative Pipelines Demo - Finding & Fixing Errors
# Run this from the lakehouse-stack directory

set -e

YELLOW='\033[1;33m'
GREEN='\033[1;32m'
RED='\033[1;31m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

pause() {
    echo ""
    read -p "Press Enter to continue..."
    echo ""
}

banner() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

run_cmd() {
    echo -e "${YELLOW}$ $1${NC}"
    eval "$1"
}

# ============================================================
# DEMO: Catching Errors with Dry-Run
# ============================================================

banner "Catching Dependency Errors with Dry-Run"

echo "Let's look at a pipeline with a bug:"
pause

run_cmd "cat scripts/demo/transformations/sales_pipeline_broken.py | head -50"

echo ""
echo -e "${YELLOW}Notice line 44: spark.table(\"iceberg.bronze.orderz\") - typo!${NC}"
pause

echo "Let's run a dry-run to validate:"
pause

echo -e "${YELLOW}$ docker exec spark-master-41 spark-pipelines dry-run --spec /scripts/demo/spark-pipeline-broken.yml${NC}"
docker exec spark-master-41 /opt/spark/bin/spark-pipelines dry-run --spec /scripts/demo/spark-pipeline-broken.yml 2>&1 | grep -v 'WARN\|WARNING\|SLF4J' || true

echo ""
echo -e "${RED}ERROR CAUGHT! The dry-run found the typo: 'orderz' should be 'orders'${NC}"
pause

# ============================================================
# FIX THE ERROR
# ============================================================

banner "Fixing the Error"

echo "The fix is simple - change 'orderz' to 'orders' on line 44:"
echo ""
echo -e "${RED}-    orders = spark.table(\"iceberg.bronze.orderz\")${NC}"
echo -e "${GREEN}+    orders = spark.table(\"iceberg.bronze.orders\")${NC}"
pause

echo "Let's use the fixed version and dry-run again:"
pause

run_cmd "docker exec spark-master-41 /opt/spark/bin/spark-pipelines dry-run --spec /scripts/demo/spark-pipeline.yml 2>&1 | grep -E '(Loading|Found|Importing|Starting|COMPLETED)'"

echo ""
echo -e "${GREEN}Dry-run passed! Now we can safely run the pipeline.${NC}"

# ============================================================
# DEMO COMPLETE
# ============================================================

banner "Demo Complete!"

echo "Key takeaway: Always run dry-run before run!"
echo ""
echo "  spark-pipelines dry-run --spec pipeline.yml  # Validate first"
echo "  spark-pipelines run --spec pipeline.yml      # Then execute"
echo ""
