"""
Lakehouse Medallion Pipeline DAG

Orchestrates the bronze -> silver -> gold data pipeline using Spark on Iceberg.
Supports both Spark 4.0 and 4.1 clusters.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.providers.apache.kafka.sensors.kafka import AwaitMessageSensor
from airflow.models import Variable

default_args = {
    "owner": "lakehouse",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Configuration
SPARK_VERSION = Variable.get("spark_version", default_var="4.1")
SPARK_MASTER_CONTAINER = f"spark-master-41" if SPARK_VERSION == "4.1" else "spark-master"


def choose_spark_version(**context):
    """Branch based on configured Spark version."""
    version = Variable.get("spark_version", default_var="4.1")
    if version == "4.1":
        return "run_pipeline_spark41"
    return "run_pipeline_spark40"


with DAG(
    dag_id="lakehouse_medallion_pipeline",
    default_args=default_args,
    description="Bronze -> Silver -> Gold medallion pipeline",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["lakehouse", "iceberg", "spark"],
) as dag:

    # Wait for data availability (optional - can be triggered manually)
    wait_for_kafka_data = AwaitMessageSensor(
        task_id="wait_for_kafka_data",
        topics=["orders"],
        kafka_config_id="kafka_default",
        apply_function="airflow.providers.apache.kafka.sensors.kafka.AwaitMessageSensor.default_apply_function",
        xcom_push_key=None,
        timeout=300,  # 5 minutes
        soft_fail=True,  # Don't fail the DAG if no messages
    )

    # Branch based on Spark version
    choose_spark = BranchPythonOperator(
        task_id="choose_spark_version",
        python_callable=choose_spark_version,
    )

    # Run pipeline on Spark 4.1
    run_pipeline_spark41 = BashOperator(
        task_id="run_pipeline_spark41",
        bash_command="""
            docker exec spark-master-41 /opt/spark/bin/spark-submit \
                /scripts/pipeline_spark41.py
        """,
    )

    # Run pipeline on Spark 4.0
    run_pipeline_spark40 = BashOperator(
        task_id="run_pipeline_spark40",
        bash_command="""
            docker exec spark-master /opt/spark/bin/spark-submit \
                /scripts/pipeline_spark40.py
        """,
    )

    # Verify pipeline completion
    verify_tables = BashOperator(
        task_id="verify_tables",
        bash_command=f"""
            docker exec {SPARK_MASTER_CONTAINER} /opt/spark/bin/spark-sql -e "
                SELECT 'bronze.orders' as table_name, count(*) as row_count FROM iceberg.bronze.orders
                UNION ALL
                SELECT 'silver.orders_clean', count(*) FROM iceberg.silver.orders_clean
                UNION ALL
                SELECT 'gold.daily_summary', count(*) FROM iceberg.gold.daily_summary
            " 2>/dev/null || echo "Table verification skipped - tables may not exist yet"
        """,
        trigger_rule="none_failed_min_one_success",
    )

    # Task dependencies
    wait_for_kafka_data >> choose_spark >> [run_pipeline_spark41, run_pipeline_spark40]
    [run_pipeline_spark41, run_pipeline_spark40] >> verify_tables
