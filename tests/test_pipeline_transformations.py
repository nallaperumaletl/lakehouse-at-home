"""Tests for data pipeline transformations.

These tests verify the core transformation logic used in the medallion pipeline:
- Bronze: Raw data loading and timestamp parsing
- Silver: Data cleaning, JSON parsing, enrichment
- Gold: Aggregations and metrics computation
"""

import pytest
from pyspark.sql import functions as f
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
)


class TestBronzeLayer:
    """Tests for Bronze layer data loading."""

    def test_orders_have_required_columns(self, sample_orders):
        """Orders should have all required columns."""
        required = ["event_id", "event_type", "ts", "order_id", "location_id", "body"]
        for col in required:
            assert col in sample_orders.columns, f"Missing required column: {col}"

    def test_timestamp_parsing(self, sample_orders):
        """Event timestamps should be properly parsed."""
        assert "event_timestamp" in sample_orders.columns

        # Verify timestamps are not null
        null_count = sample_orders.filter(f.col("event_timestamp").isNull()).count()
        total_count = sample_orders.count()

        # Allow up to 1% null timestamps (data quality tolerance)
        assert null_count / total_count < 0.01, "Too many null timestamps"

    def test_event_types_are_valid(self, sample_orders):
        """Event types should be from expected set."""
        valid_types = {
            "order_created",
            "kitchen_started",
            "kitchen_finished",
            "order_ready",
            "driver_arrived",
            "driver_picked_up",
            "delivered",
            "driver_ping",
        }

        actual_types = {
            row.event_type for row in sample_orders.select("event_type").distinct().collect()
        }

        assert actual_types.issubset(valid_types), f"Unknown event types: {actual_types - valid_types}"

    def test_dimension_brands_schema(self, dim_brands):
        """Brands dimension should have expected schema."""
        assert "id" in dim_brands.columns
        assert "name" in dim_brands.columns
        assert dim_brands.count() == 20, "Expected 20 brands"

    def test_dimension_locations_schema(self, dim_locations):
        """Locations dimension should have expected schema."""
        assert "id" in dim_locations.columns
        assert "city" in dim_locations.columns
        assert dim_locations.count() == 4, "Expected 4 locations"


class TestSilverLayer:
    """Tests for Silver layer transformations."""

    @pytest.fixture
    def enriched_orders(self, spark, sample_orders, dim_locations):
        """Create enriched orders for testing."""
        # Filter nulls
        cleaned = sample_orders.filter(
            f.col("event_id").isNotNull()
            & f.col("order_id").isNotNull()
            & f.col("event_timestamp").isNotNull()
        )

        # Parse JSON body
        body_schema = StructType(
            [
                StructField("brand_id", IntegerType(), True),
                StructField("item_ids", StringType(), True),
                StructField("total", DoubleType(), True),
                StructField("lat", DoubleType(), True),
                StructField("lng", DoubleType(), True),
                StructField("driver_id", StringType(), True),
            ]
        )

        enriched = cleaned.withColumn("body_parsed", f.from_json("body", body_schema))

        # Extract fields
        enriched = enriched.select(
            "event_id",
            "event_type",
            "event_timestamp",
            "order_id",
            "location_id",
            f.col("body_parsed.brand_id").alias("brand_id"),
            f.col("body_parsed.total").alias("order_total"),
        )

        # Add time features
        enriched = enriched.withColumns(
            {
                "event_hour": f.hour("event_timestamp"),
                "event_day_of_week": f.dayofweek("event_timestamp"),
                "is_weekend": f.when(
                    f.dayofweek("event_timestamp").isin(1, 7), True
                ).otherwise(False),
                "event_date": f.to_date("event_timestamp"),
            }
        )

        # Join with locations
        locations_lookup = dim_locations.select(
            f.col("id").alias("location_id"),
            f.col("city").alias("city_name"),
        )

        return enriched.join(f.broadcast(locations_lookup), on="location_id", how="left")

    def test_null_filtering(self, sample_orders):
        """Null records should be filtered out."""
        original = sample_orders.count()
        cleaned = sample_orders.filter(
            f.col("event_id").isNotNull()
            & f.col("order_id").isNotNull()
            & f.col("event_timestamp").isNotNull()
        )

        # Some records may be filtered, but not too many
        assert cleaned.count() > 0
        assert cleaned.count() <= original

    def test_json_body_parsing(self, enriched_orders):
        """JSON body should be parsed correctly for order_created events."""
        created_events = enriched_orders.filter(f.col("event_type") == "order_created")

        # brand_id should be populated for order_created
        null_brand_count = created_events.filter(f.col("brand_id").isNull()).count()
        total_created = created_events.count()

        if total_created > 0:
            # Allow up to 5% null brand_ids (some data quality variance expected)
            assert null_brand_count / total_created < 0.05, "Too many null brand_ids"

    def test_time_features_added(self, enriched_orders):
        """Time-based features should be correctly computed."""
        required_cols = ["event_hour", "event_day_of_week", "is_weekend", "event_date"]
        for col in required_cols:
            assert col in enriched_orders.columns, f"Missing time feature: {col}"

        # event_hour should be 0-23
        hour_stats = enriched_orders.agg(
            f.min("event_hour").alias("min_hour"),
            f.max("event_hour").alias("max_hour"),
        ).collect()[0]

        assert hour_stats.min_hour >= 0
        assert hour_stats.max_hour <= 23

    def test_location_join(self, enriched_orders):
        """Location names should be joined correctly."""
        assert "city_name" in enriched_orders.columns

        # Most records should have city_name
        null_city = enriched_orders.filter(f.col("city_name").isNull()).count()
        total = enriched_orders.count()

        if total > 0:
            # Allow up to 5% null city names (some events like driver_ping may lack location)
            assert null_city / total < 0.05, "Too many null city names"


class TestGoldLayer:
    """Tests for Gold layer aggregations."""

    @pytest.fixture
    def hourly_metrics(self, spark, sample_orders, dim_locations):
        """Create hourly metrics for testing."""
        # Quick enrichment for test
        body_schema = StructType(
            [
                StructField("brand_id", IntegerType(), True),
                StructField("total", DoubleType(), True),
            ]
        )

        enriched = (
            sample_orders.filter(f.col("event_timestamp").isNotNull())
            .withColumn("body_parsed", f.from_json("body", body_schema))
            .select(
                "event_type",
                "order_id",
                "location_id",
                f.col("body_parsed.brand_id").alias("brand_id"),
                f.col("body_parsed.total").alias("order_total"),
                f.to_date("event_timestamp").alias("event_date"),
                f.hour("event_timestamp").alias("event_hour"),
            )
        )

        locations_lookup = dim_locations.select(
            f.col("id").alias("location_id"),
            f.col("city").alias("city_name"),
        )

        enriched = enriched.join(f.broadcast(locations_lookup), on="location_id", how="left")

        return (
            enriched.filter(f.col("event_type") == "order_created")
            .groupBy("event_date", "event_hour", "location_id", "city_name")
            .agg(
                f.count("order_id").alias("order_count"),
                f.sum("order_total").alias("total_revenue"),
                f.avg("order_total").alias("avg_order_value"),
                f.countDistinct("brand_id").alias("unique_brands"),
            )
        )

    def test_hourly_metrics_schema(self, hourly_metrics):
        """Hourly metrics should have expected schema."""
        expected_cols = [
            "event_date",
            "event_hour",
            "city_name",
            "order_count",
            "total_revenue",
            "avg_order_value",
            "unique_brands",
        ]
        for col in expected_cols:
            assert col in hourly_metrics.columns, f"Missing column: {col}"

    def test_hourly_metrics_aggregation(self, hourly_metrics):
        """Aggregations should produce valid values."""
        stats = hourly_metrics.agg(
            f.min("order_count").alias("min_orders"),
            f.max("order_count").alias("max_orders"),
            f.min("total_revenue").alias("min_revenue"),
            f.max("avg_order_value").alias("max_aov"),
        ).collect()[0]

        # Order counts should be positive
        assert stats.min_orders >= 1

        # Revenue should be positive for actual orders
        assert stats.min_revenue > 0

        # AOV should be reasonable (between $5 and $200)
        assert 5 <= stats.max_aov <= 200

    def test_unique_brands_bounded(self, hourly_metrics):
        """Unique brands per hour should be bounded by total brands."""
        max_brands = hourly_metrics.agg(f.max("unique_brands")).collect()[0][0]
        assert max_brands <= 20, "More unique brands than exist"


class TestDataQuality:
    """Data quality validation tests."""

    def test_order_ids_format(self, sample_orders):
        """Order IDs should follow expected format."""
        # Sample some order_ids
        sample_ids = [
            row.order_id
            for row in sample_orders.select("order_id").distinct().limit(100).collect()
        ]

        for order_id in sample_ids:
            # Order IDs should be non-empty strings
            assert order_id is not None
            assert len(order_id) > 0

    def test_location_ids_valid(self, sample_orders, dim_locations):
        """Location IDs should reference valid locations."""
        valid_ids = {row.id for row in dim_locations.select("id").collect()}
        actual_ids = {
            row.location_id
            for row in sample_orders.select("location_id").distinct().collect()
            if row.location_id is not None  # Exclude null location IDs
        }

        invalid_ids = actual_ids - valid_ids
        assert len(invalid_ids) == 0, f"Invalid location IDs: {invalid_ids}"

    def test_order_totals_reasonable(self, sample_orders):
        """Order totals should be within reasonable range."""
        body_schema = StructType(
            [
                StructField("total", DoubleType(), True),
            ]
        )

        totals = (
            sample_orders.filter(f.col("event_type") == "order_created")
            .withColumn("body_parsed", f.from_json("body", body_schema))
            .select(f.col("body_parsed.total").alias("total"))
            .filter(f.col("total").isNotNull())
        )

        if totals.count() > 0:
            stats = totals.agg(
                f.min("total").alias("min"),
                f.max("total").alias("max"),
                f.avg("total").alias("avg"),
            ).collect()[0]

            # Totals should be positive
            assert stats.min > 0, "Order totals must be positive"

            # Totals should be reasonable (not too high for food delivery)
            assert stats.max < 1000, "Order total too high"

            # Average should be reasonable
            assert 10 < stats.avg < 100, f"Average order total unusual: {stats.avg}"
