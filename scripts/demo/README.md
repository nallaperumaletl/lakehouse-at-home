# Spark Declarative Pipelines Demo

A 5-minute demo showcasing Spark 4.1's Declarative Pipelines feature.

## Prerequisites

Ensure the Spark 4.1 cluster is running:

```bash
./lakehouse start spark41
./lakehouse status
```

## Demo 1: Pipeline Basics (3 min)

### Commands

```bash
# 1. Initialize a new pipeline project
docker exec spark-master-41 spark-pipelines init --name my_pipeline

# 2. View generated structure
docker exec spark-master-41 ls -la my_pipeline/

# 3. View the config file
docker exec spark-master-41 cat my_pipeline/spark-pipeline.yml

# 4. View our demo pipeline code
cat scripts/demo/transformations/sales_pipeline.py

# 5. Dry-run to validate
docker exec spark-master-41 spark-pipelines dry-run --spec /scripts/demo/spark-pipeline.yml

# 6. Run the pipeline
docker exec spark-master-41 spark-pipelines run --spec /scripts/demo/spark-pipeline.yml
```

### Narration Script

> "Let me show you Spark Declarative Pipelines - a new feature in Spark 4.1 that makes building data pipelines simpler and more reliable."

**[Run init command]**

> "First, we initialize a new pipeline project. This creates a project structure with a config file and a transformations folder."

**[Run ls and cat commands]**

> "The config file defines the pipeline name, storage location, and which Python files contain our transformations. Notice how simple it is - just YAML."

**[Show sales_pipeline.py]**

> "Here's our pipeline code. Instead of writing imperative Spark jobs, we use decorators to declare our tables. The `@sdp.table` decorator creates a streaming table from Kafka, and `@sdp.materialized_view` creates a derived view from Iceberg tables."
>
> "Notice we don't write any orchestration code - no explicit reads, writes, or dependency management. We just declare what each table should contain."

**[Run dry-run]**

> "Before running, we validate with a dry-run. This checks that all dependencies resolve, all table references are valid, and the DAG is correct - without actually processing any data."

**[Run the pipeline]**

> "Now we run it for real. The framework automatically determines the execution order, manages checkpoints, and handles failures."

---

## Demo 2: Catching Errors Early (2 min)

### Commands

```bash
# 1. Show the broken pipeline code
cat scripts/demo/transformations/sales_pipeline_broken.py

# 2. Try dry-run (will fail)
docker exec spark-master-41 spark-pipelines dry-run --spec /scripts/demo/spark-pipeline-broken.yml

# 3. Show the fix
echo "Fix: Change 'orderz' to 'orders' on line 44"

# 4. Run dry-run on fixed version
docker exec spark-master-41 spark-pipelines dry-run --spec /scripts/demo/spark-pipeline.yml
```

### Narration Script

> "One of the best features of declarative pipelines is catching errors before they cost you compute time."

**[Show broken pipeline]**

> "Here's a pipeline with a subtle bug - on line 44, someone typed 'orderz' instead of 'orders'. In a traditional Spark job, you might not catch this until runtime, after spinning up a cluster."

**[Run dry-run on broken version]**

> "Watch what happens when we dry-run..."
>
> "The framework immediately catches the error: TABLE_OR_VIEW_NOT_FOUND - 'orderz' cannot be found. It even tells us exactly which flow failed: gold.brand_summary."

**[Show the fix]**

> "The fix is simple - correct the typo from 'orderz' to 'orders'."

**[Run dry-run on fixed version]**

> "Now dry-run passes, and we can confidently run the pipeline knowing all dependencies are valid."

---

## Key Takeaways

1. **Declarative over Imperative** - Define *what* tables should contain, not *how* to build them
2. **Automatic Dependency Resolution** - Framework determines execution order
3. **Validate Before Execute** - `dry-run` catches errors without compute cost
4. **Simple Configuration** - YAML spec + decorated Python functions

## File Reference

| File | Purpose |
|------|---------|
| `spark-pipeline.yml` | Working pipeline config |
| `spark-pipeline-broken.yml` | Broken config (for error demo) |
| `transformations/sales_pipeline.py` | Working pipeline code |
| `transformations/sales_pipeline_broken.py` | Code with typo (orderz) |
| `run_demo.sh` | Interactive demo script |
| `run_demo_fix_error.sh` | Interactive error-fix demo |

## Automated Demo Scripts

For a guided walkthrough with pauses:

```bash
# Full demo with init, dry-run, run
./scripts/demo/run_demo.sh

# Error catching demo
./scripts/demo/run_demo_fix_error.sh
```
