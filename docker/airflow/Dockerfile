FROM apache/airflow:2.8.4-python3.11

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    openjdk-17-jre-headless \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for Spark
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Download and install Spark (for spark-submit)
ENV SPARK_VERSION=4.0.0
ENV SPARK_HOME=/opt/spark
RUN curl -fsSL "https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop3.tgz" \
    | tar -xz -C /opt/ \
    && mv /opt/spark-${SPARK_VERSION}-bin-hadoop3 ${SPARK_HOME} \
    && chown -R airflow:root ${SPARK_HOME}

ENV PATH="${SPARK_HOME}/bin:${PATH}"

USER airflow

# Install Airflow providers
RUN pip install --no-cache-dir \
    apache-airflow-providers-apache-spark==4.7.1 \
    apache-airflow-providers-postgres==5.10.2 \
    apache-airflow-providers-apache-kafka==1.3.1 \
    apache-airflow-providers-docker==3.10.0 \
    apache-airflow-providers-http==4.10.0 \
    pyspark==4.0.0

# Create directories
RUN mkdir -p /opt/airflow/dags /opt/airflow/logs /opt/airflow/config

WORKDIR /opt/airflow
