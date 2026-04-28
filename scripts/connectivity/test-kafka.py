from pyspark.sql import SparkSession
from pyspark.sql import functions as F
import os

spark = SparkSession.builder.appName("KafkaStreaming").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# When running inside Docker, Kafka is typically reachable as `kafka:29092`
# (see docker-compose-kafka.yml). Override via env var when needed.
kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
topic = os.environ.get("KAFKA_TOPIC", "events")

# Read from Kafka
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_bootstrap)
    .option("subscribe", topic)
    .option("startingOffsets", "earliest")
    .load()
)

# Show raw Kafka data
query = (
    kafka_df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)")
    .writeStream
    .format("console")
    .option("truncate", False)
    .start()
)

print("Showing raw Kafka data... Press Ctrl+C to stop.")
query.awaitTermination()
