"""Tests for the temperature cache functionality."""

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mqtt_thermometer import cache


class TestTemperatureCache(unittest.TestCase):
    def setUp(self):
        """Clear cache before each test."""
        cache.clear_cache()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear_cache()

    def test_add_and_retrieve_temperature(self):
        """Test adding and retrieving temperature from cache."""
        source = "test/sensor"
        timestamp = datetime.now(tz=UTC)
        temperature = Decimal("20.5")

        # Add temperature to cache
        cache.add_temperature_to_cache(source, timestamp, temperature)

        # Retrieve from cache
        since = timestamp - timedelta(minutes=1)
        results = cache.get_temperatures_from_cache_only(source, since)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], source)
        self.assertEqual(results[0][1], timestamp.isoformat())
        self.assertEqual(results[0][2], temperature)

    def test_cache_ordering(self):
        """Test that cache maintains chronological order."""
        source = "test/sensor"
        base_time = datetime.now(tz=UTC)

        # Add temperatures out of order
        cache.add_temperature_to_cache(
            source, base_time + timedelta(minutes=2), Decimal("22.0")
        )
        cache.add_temperature_to_cache(source, base_time, Decimal("20.0"))
        cache.add_temperature_to_cache(
            source, base_time + timedelta(minutes=1), Decimal("21.0")
        )

        # Retrieve all
        results = cache.get_temperatures_from_cache_only(
            source, base_time - timedelta(minutes=1)
        )

        self.assertEqual(len(results), 3)
        # Should be in chronological order
        self.assertEqual(results[0][2], Decimal("20.0"))
        self.assertEqual(results[1][2], Decimal("21.0"))
        self.assertEqual(results[2][2], Decimal("22.0"))

    def test_cache_filtering_by_time(self):
        """Test that cache correctly filters by since timestamp."""
        source = "test/sensor"
        base_time = datetime.now(tz=UTC)

        # Add multiple temperatures
        cache.add_temperature_to_cache(
            source, base_time - timedelta(hours=2), Decimal("18.0")
        )
        cache.add_temperature_to_cache(
            source, base_time - timedelta(hours=1), Decimal("19.0")
        )
        cache.add_temperature_to_cache(source, base_time, Decimal("20.0"))

        # Get only recent temperatures
        since = base_time - timedelta(minutes=30)
        results = cache.get_temperatures_from_cache_only(source, since)

        # Should only get the most recent one
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][2], Decimal("20.0"))

    def test_cache_cleanup(self):
        """Test that old entries are cleaned up."""
        source = "test/sensor"
        old_time = datetime.now(tz=UTC) - timedelta(hours=25)  # Older than 24 hours
        recent_time = datetime.now(tz=UTC)

        # Add old and recent temperatures
        cache.add_temperature_to_cache(source, old_time, Decimal("15.0"))
        cache.add_temperature_to_cache(source, recent_time, Decimal("20.0"))

        # The second add should automatically clean up old entries
        # Get all entries
        results = cache.get_temperatures_from_cache_only(source, old_time)

        # Should only have recent entry due to automatic cleanup
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][2], Decimal("20.0"))

    def test_multiple_sources(self):
        """Test cache with multiple temperature sources."""
        timestamp = datetime.now(tz=UTC)

        cache.add_temperature_to_cache("source1", timestamp, Decimal("20.0"))
        cache.add_temperature_to_cache("source2", timestamp, Decimal("25.0"))

        # Get from different sources
        results1 = cache.get_temperatures_from_cache_only(
            "source1", timestamp - timedelta(minutes=1)
        )
        results2 = cache.get_temperatures_from_cache_only(
            "source2", timestamp - timedelta(minutes=1)
        )

        self.assertEqual(len(results1), 1)
        self.assertEqual(len(results2), 1)
        self.assertEqual(results1[0][2], Decimal("20.0"))
        self.assertEqual(results2[0][2], Decimal("25.0"))

    def test_cache_stats(self):
        """Test cache statistics functionality."""
        timestamp = datetime.now(tz=UTC)

        cache.add_temperature_to_cache("source1", timestamp, Decimal("20.0"))
        cache.add_temperature_to_cache(
            "source1", timestamp + timedelta(minutes=1), Decimal("20.5")
        )
        cache.add_temperature_to_cache("source2", timestamp, Decimal("25.0"))

        stats = cache.get_cache_stats()

        self.assertEqual(stats["source1"], 2)
        self.assertEqual(stats["source2"], 1)


if __name__ == "__main__":
    unittest.main()
