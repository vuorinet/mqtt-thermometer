"""Integration test for cache functionality with database."""

import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mqtt_thermometer import cache, database


class TestCacheIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test database and clear cache."""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()

        # Mock settings to use test database
        self.original_connection_string = database.settings.db_connection_string
        database.settings.db_connection_string = self.db_path

        # Initialize test database
        database.create_table()
        cache.clear_cache()

    def tearDown(self):
        """Clean up test database and cache."""
        cache.clear_cache()
        database.settings.db_connection_string = self.original_connection_string
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_save_and_retrieve_with_cache(self):
        """Test that saving to database also populates cache."""
        source = "test/sensor"
        timestamp = datetime.now(tz=UTC)
        temperature = Decimal("22.5")

        # Save to database (should also populate cache)
        success = database.save_temperature(source, timestamp, temperature)
        self.assertTrue(success)

        # Retrieve using cached method
        since = timestamp - timedelta(minutes=1)
        results = database.get_temperatures_cached(source, since)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], source)
        self.assertEqual(results[0][1], timestamp.isoformat())
        self.assertEqual(results[0][2], temperature)

    def test_cache_miss_fallback_to_database(self):
        """Test that cache misses fall back to database correctly."""
        source = "test/sensor"
        timestamp = datetime.now(tz=UTC)
        temperature = Decimal("23.0")

        # Save directly to database (bypass cache)
        with database.get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
                (source, timestamp.isoformat(), temperature),
            )
            conn.commit()

        # Cache should be empty, so this should fall back to database
        since = timestamp - timedelta(minutes=1)
        results = database.get_temperatures_cached(source, since)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], source)
        self.assertEqual(results[0][1], timestamp.isoformat())
        self.assertEqual(results[0][2], temperature)

    def test_mixed_cache_and_database_data(self):
        """Test handling of data partially in cache and partially in database."""
        source = "test/sensor"
        base_time = datetime.now(tz=UTC)

        # Add old data directly to database (simulating pre-cache data)
        old_time = base_time - timedelta(hours=2)
        old_temp = Decimal("20.0")
        with database.get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
                (source, old_time.isoformat(), old_temp),
            )
            conn.commit()

        # Add recent data via normal save (should populate cache)
        recent_temp = Decimal("25.0")
        database.save_temperature(source, base_time, recent_temp)

        # Retrieve all data
        since = base_time - timedelta(hours=3)
        results = database.get_temperatures_cached(source, since)

        # Should get both entries
        self.assertEqual(len(results), 2)
        timestamps = [datetime.fromisoformat(r[1]) for r in results]
        temperatures = [r[2] for r in results]

        # Should be in chronological order
        self.assertEqual(min(timestamps), old_time)
        self.assertEqual(max(timestamps), base_time)
        self.assertIn(old_temp, temperatures)
        self.assertIn(recent_temp, temperatures)

    def test_cache_initialization_from_database(self):
        """Test that cache can be initialized from existing database data."""
        source = "test/sensor"
        base_time = datetime.now(tz=UTC)

        # Add data directly to database (simulating existing data)
        temperatures = [
            (base_time - timedelta(hours=2), Decimal("18.0")),
            (base_time - timedelta(hours=1), Decimal("19.5")),
            (base_time, Decimal("21.0")),
        ]

        with database.get_database_connection() as conn:
            cursor = conn.cursor()
            for timestamp, temperature in temperatures:
                cursor.execute(
                    "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
                    (source, timestamp.isoformat(), temperature),
                )
            conn.commit()

        # Clear cache and initialize from database
        cache.clear_cache()
        cache.initialize_cache_from_database()

        # Verify cache is populated
        since = base_time - timedelta(hours=3)
        cached_results = cache.get_temperatures_from_cache(source, since)

        self.assertEqual(len(cached_results), 3)

        # Verify the data is correct and sorted
        cached_temperatures = [result[2] for result in cached_results]
        expected_temperatures = [Decimal("18.0"), Decimal("19.5"), Decimal("21.0")]
        self.assertEqual(cached_temperatures, expected_temperatures)

        # Verify cache stats
        stats = cache.get_cache_stats()
        self.assertEqual(stats[source], 3)

    def test_cache_initialization_with_empty_database(self):
        """Test cache initialization when database is empty."""
        # Clear any existing data and cache
        cache.clear_cache()

        # Initialize from empty database - should not raise any exceptions
        cache.initialize_cache_from_database()

        # Cache should be empty
        stats = cache.get_cache_stats()
        self.assertEqual(len(stats), 0)


if __name__ == "__main__":
    unittest.main()
