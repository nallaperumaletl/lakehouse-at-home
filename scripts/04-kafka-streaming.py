from pyspark.sql import SparkSession
from pyspark.sql import functions as f 
from pyspark.sql.types import (
        StructType,
        StructField, 
        StringType,
        IntegerType,
        DoubleType,
        TimestampType
        )

# start session
spark = SparkSession.builder.appName("KafkaStreaming").getOrCreate() 

#reduce output 
spark.sparkContext.setLogLevel("WARN")

# define scheme mappings
schema = StructType(
        [
            StructField("event_id", IntegerType(), True),
            StructField("timestamp", StringType(), True), 
            StructField("user_id", StringType(), True),
            StructField("event_type", StringType(), True), 
            StructField("product", StringType(), True),
            StructField("price", DoubleType(), True), 
            StructField("quantity", IntegerType(), True), 

        ] 
    )

# read from Kafka 
kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", "localhost:9092")
        .option("subscribe", "events")
        .option("startingOffsets", "latest") 
        .load()
        )

# parse JSON from Streaming 
events_df = events_df.withColumn(
        "event_timestamp", f.to_timestamp("timestamp", "yyyy-MM-dd'T'HH:mm:ss.SSSSSS")
        )

#Transformation 1: Calculate Revenue
events_df = events_df.withColumn("revenue", f.col("price") * f.col("quantity"))

# Transformation 2: Aggregate by product in 30 second intervals
product_metrics = (
        events_df.groupBy(F.window("event_timestamp", "30 seconds"), "product")
        .agg(
            f.count("*").alias("event_count"), 
            f.sum("revenue").alias("avg_price"),
            )
        .select(
            f.col("window.start").alias("window_start"), 
            f.col("window.end".alias("window_end"), 
            "product", 
            "event_count",
            "total.revenue", 
            "avg_price",
        )
)) 


# write to console- temporary and will change later 
query = (product_metrics.writeStream.outputMode("update") 
         .format("console")
         .option("truncate", False)
         .start()
        ) 

print("Streaming from Kafka... press ctrl+c to stop")
query.awaitTermination()

