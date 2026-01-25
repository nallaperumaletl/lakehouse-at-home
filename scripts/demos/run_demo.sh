#!/bin/bash
# Spark Declarative Pipelines Demo
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
# DEMO PART 1: Project Initialization
# ============================================================

banner "PART 1: Initialize a New Pipeline Project"

echo "First, let's create a new pipeline project using spark-pipelines init:"
pause

run_cmd "docker exec spark-master-41 /opt/spark/bin/spark-pipelines init --name sales_demo 2>/dev/null"

echo ""
echo -e "${GREEN}Project created! Let's see what was generated:${NC}"
pause

run_cmd "docker exec spark-master-41 ls -la sales_demo/"

echo ""
echo -e "${GREEN}Let's look at the generated config file:${NC}"
pause

run_cmd "docker exec spark-master-41 cat sales_demo/spark-pipeline.yml"

# ============================================================
# DEMO PART 2: Existing Pipeline - Dry Run
# ============================================================

banner "PART 2: Dry Run an Existing Pipeline"

echo "Now let's look at our pre-built demo pipeline:"
pause

run_cmd "cat scripts/demos/spark-pipeline.yml"

echo ""
echo -e "${GREEN}And the pipeline code:${NC}"
pause

run_cmd "cat scripts/demos/transformations/sales_pipeline.py"

echo ""
echo -e "${GREEN}Let's validate with a dry-run:${NC}"
pause

run_cmd "docker exec spark-master-41 /opt/spark/bin/spark-pipelines dry-run --spec /scripts/demos/spark-pipeline.yml 2>&1 | grep -v 'WARN\|WARNING\|SLF4J'"

echo ""
echo -e "${GREEN}Dry-run passed! The pipeline graph is valid.${NC}"

# ============================================================
# DEMO PART 3: Run the Pipeline
# ============================================================

banner "PART 3: Execute the Pipeline"

echo "Now let's run the pipeline for real:"
pause

run_cmd "docker exec spark-master-41 /opt/spark/bin/spark-pipelines run --spec /scripts/demos/spark-pipeline.yml 2>&1 | grep -v 'WARN\|WARNING\|SLF4J'"

echo ""
echo -e "${GREEN}Pipeline executed successfully!${NC}"

# ============================================================
# DEMO COMPLETE
# ============================================================

banner "Demo Complete!"

echo "You've seen:"
echo "  1. spark-pipelines init  - Create a new project"
echo "  2. spark-pipelines dry-run - Validate the pipeline graph"
echo "  3. spark-pipelines run    - Execute the pipeline"
echo ""
