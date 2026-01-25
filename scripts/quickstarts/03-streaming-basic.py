from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    TimestampType,
)

spark = SparkSession.builder.getOrCreate()

# Define schema for incoming data
schema = StructType(
    [
        StructField("event_id", IntegerType(), True),
        StructField("event_type", StringType(), True),
        StructField("user_id", IntegerType(), True),
        StructField("value", IntegerType(), True),
    ]
)

# Create streaming source (generates test data)
streaming_df = (
    spark.readStream.format("rate")
    .option("rowsPerSecond", 5)
    .load()
    .withColumn("event_id", f.col("value"))
    .withColumn(
        "event_type", f.when(f.col("value") % 2 == 0, "click").otherwise("view")
    )
    .withColumn("user_id", (f.col("value") % 10) + 1)
    .withColumn("event_value", f.col("value") * 10)
    .select("event_id", "event_type", "user_id", "event_value", "timestamp")
)

# aggregate by event_type
aggregated = streaming_df.groupBy(
    f.window("timestamp", "10 seconds"), "event_type"
).agg(f.count("*").alias("count"), f.sum("event_value").alias("total_value"))

# Write to console
query = (
    aggregated.writeStream.outputMode("update")
    .format("console")
    .option("truncate", False)
    .start()
)

print("streaming query started, press ctrl+c to stop.")
query.awaitTermination()
