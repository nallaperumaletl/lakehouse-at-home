"""
Iceberg Table Maintenance DAG

Performs routine maintenance tasks on Iceberg tables:
- Expire old snapshots
- Remove orphan files
- Compact small files (rewrite data files)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable

default_args = {
    "owner": "lakehouse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

# Configuration
SPARK_VERSION = Variable.get("spark_version", default_var="4.1")
SPARK_MASTER_CONTAINER = "spark-master-41" if SPARK_VERSION == "4.1" else "spark-master"

# Tables to maintain
TABLES = [
    "iceberg.bronze.orders",
    "iceberg.silver.orders_clean",
    "iceberg.gold.daily_summary",
]


def create_expire_snapshots_task(table: str) -> BashOperator:
    """Create task to expire old snapshots for a table."""
    task_id = f"expire_snapshots_{table.replace('.', '_')}"
    return BashOperator(
        task_id=task_id,
        bash_command=f"""
            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-sql -e "
                CALL iceberg.system.expire_snapshots(
                    table => '{table}',
                    older_than => TIMESTAMP '$(date -d '7 days ago' '+%Y-%m-%d %H:%M:%S')',
                    retain_last => 5
                )
            " 2>/dev/null || echo "Skipping {table} - table may not exist"
        """,
    )


def create_remove_orphans_task(table: str) -> BashOperator:
    """Create task to remove orphan files for a table."""
    task_id = f"remove_orphans_{table.replace('.', '_')}"
    return BashOperator(
        task_id=task_id,
        bash_command=f"""
            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-sql -e "
                CALL iceberg.system.remove_orphan_files(
                    table => '{table}',
                    older_than => TIMESTAMP '$(date -d '3 days ago' '+%Y-%m-%d %H:%M:%S')'
                )
            " 2>/dev/null || echo "Skipping {table} - table may not exist"
        """,
    )


def create_compact_files_task(table: str) -> BashOperator:
    """Create task to compact small files for a table."""
    task_id = f"compact_files_{table.replace('.', '_')}"
    return BashOperator(
        task_id=task_id,
        bash_command=f"""
            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-sql -e "
                CALL iceberg.system.rewrite_data_files(
                    table => '{table}',
                    options => map(
                        'target-file-size-bytes', '134217728',
                        'min-input-files', '5'
                    )
                )
            " 2>/dev/null || echo "Skipping {table} - table may not exist or no files to compact"
        """,
    )


with DAG(
    dag_id="iceberg_maintenance",
    default_args=default_args,
    description="Iceberg table maintenance: snapshots, orphans, compaction",
    schedule_interval="0 3 * * *",  # Daily at 3 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["lakehouse", "iceberg", "maintenance"],
) as dag:

    # Check Spark cluster availability
    check_spark = BashOperator(
        task_id="check_spark_cluster",
        bash_command=f"""
            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-submit --version > /dev/null 2>&1 \
                && echo "Spark cluster available" \
                || (echo "Spark cluster not available" && exit 1)
        """,
    )

    # Create maintenance tasks for each table
    for table in TABLES:
        expire_task = create_expire_snapshots_task(table)
        orphan_task = create_remove_orphans_task(table)
        compact_task = create_compact_files_task(table)

        # Chain tasks: check_spark -> expire -> orphans -> compact
        check_spark >> expire_task >> orphan_task >> compact_task


# Additional standalone DAG for on-demand compaction
with DAG(
    dag_id="iceberg_compact_on_demand",
    default_args=default_args,
    description="On-demand Iceberg file compaction",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["lakehouse", "iceberg", "maintenance"],
    params={
        "table": "iceberg.bronze.orders",
        "target_size_mb": 128,
    },
) as compact_dag:

    compact_specific_table = BashOperator(
        task_id="compact_specific_table",
        bash_command=f"""
            TABLE="{{{{ params.table }}}}"
            TARGET_BYTES=$(({{{{ params.target_size_mb }}}} * 1024 * 1024))

            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-sql -e "
                CALL iceberg.system.rewrite_data_files(
                    table => '$TABLE',
                    options => map(
                        'target-file-size-bytes', '$TARGET_BYTES',
                        'min-input-files', '2'
                    )
                )
            "
        """,
    )
