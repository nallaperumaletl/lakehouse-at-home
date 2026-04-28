FROM apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu

USER root

# Ensure PySpark is importable from Python.
ENV SPARK_HOME=/opt/spark

# Minimal Jupyter stack + common data libs.
# PySpark is already provided by the base Spark image (matching Spark 4.1).
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir \
      jupyterlab \
      notebook \
      ipykernel \
      pyarrow \
      pandas

# Default notebook location (mounted from host via docker-compose-notebooks.yml)
WORKDIR /home/jovyan/notebooks

EXPOSE 8888

CMD ["bash", "-lc", "export PYTHONPATH=\"${SPARK_HOME}/python:${SPARK_HOME}/python/lib/$(ls -1 ${SPARK_HOME}/python/lib/py4j-*-src.zip | head -n 1 | xargs -n1 basename)\" && jupyter lab --ip=0.0.0.0 --port=8888 --NotebookApp.token='' --NotebookApp.password='' --allow-root"]
