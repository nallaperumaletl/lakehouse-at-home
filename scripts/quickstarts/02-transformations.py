from pyspark.sql import SparkSession
from pyspark.sql import functions as f

spark = SparkSession.builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

df = spark.table("iceberg.bronze.spark_test")

filtered = df.filter(f.col("id") > 1)
with_column = filtered.withColumn("value_x10", f.col("value") * 10)
selected = with_column.select("name", "value", "value_x10")

print("Narrow Transformations:")
selected.explain()
selected.show()

grouped = df.groupBy("name").agg(
    f.count("*").alias("count"), f.sum("value").alias("total_value")
)


print("\nWide transformation:")
grouped.explain()
grouped.show()
