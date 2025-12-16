// Test Iceberg integration with Spark

println("=" * 60)
println("Testing Iceberg Catalog Connection")
println("=" * 60)

// List namespaces
println("\n1. Listing namespaces:")
spark.sql("SHOW NAMESPACES IN iceberg").show()

// List tables in bronze
println("\n2. Listing tables in bronze namespace:")
spark.sql("SHOW TABLES IN iceberg.bronze").show()

// Read existing test_table (created by PyIceberg)
println("\n3. Reading existing test_table:")
spark.sql("SELECT * FROM iceberg.bronze.test_table").show()

// Create a new table
println("\n4. Creating spark_test table:")
spark.sql("""
  CREATE TABLE IF NOT EXISTS iceberg.bronze.spark_test (
    id INT,
    name STRING,
    value DOUBLE,
    created_at TIMESTAMP
  ) USING iceberg
""")

// Insert sample data
println("\n5. Inserting sample data:")
spark.sql("""
  INSERT INTO iceberg.bronze.spark_test VALUES
  (1, 'Alice', 100.5, current_timestamp()),
  (2, 'Bob', 200.7, current_timestamp()),
  (3, 'Charlie', 150.3, current_timestamp())
""")

// Read the data back
println("\n6. Reading spark_test table:")
spark.sql("SELECT * FROM iceberg.bronze.spark_test ORDER BY id").show()

// Show table metadata
println("\n7. Table metadata:")
spark.sql("DESCRIBE EXTENDED iceberg.bronze.spark_test").show(100, false)

// Verify in S3
println("\n8. Checking S3 warehouse structure:")
import sys.process._
val s3Output = "aws --endpoint-url http://host.docker.internal:8333 s3 ls s3://lakehouse/warehouse/bronze/ --recursive".!!
println(s3Output)

println("\n" + "=" * 60)
println("✅ All tests completed successfully!")
println("=" * 60)
