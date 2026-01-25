from pyspark.sql import SparkSession
from pyspark.sql import functions as f


spark = SparkSession.builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")

df = spark.table("iceberg.bronze.spark_test")

print("Original Data:")
df.show()


# basic transformations
filtered = df.filter(f.col("id") > 1)

with_computed = filtered.withColumn("value_doubled", f.col("value") * 2)

# view execution plan
print("\nExecutionPlan:")
with_computed.explain()


print("\nResult:")
with_computed.show()

# get iceberg metadata and confirm table type

print("\nTable Type:")

print(spark.catalog.getTable("iceberg.bronze.spark_test").tableType)

spark.sql("DESCRIBE EXTENDED iceberg.bronze.spark_test").show(100, truncate=False)
