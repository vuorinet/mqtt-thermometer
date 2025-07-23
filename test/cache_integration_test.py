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

    def test_cache_only_behavior(self):
        """Test that cache returns only cached data, no database fallback."""
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

        # Cache should be empty, so cache-only method returns nothing
        since = timestamp - timedelta(minutes=1)
        results = database.get_temperatures_cached(source, since)

        # Should return empty because data is only in database, not cache
        self.assertEqual(len(results), 0)

        # But direct database access should return the data
        db_results = database.get_temperatures(source, since)
        self.assertEqual(len(db_results), 1)
        self.assertEqual(db_results[0][2], temperature)

    def test_cache_population_through_save(self):
        """Test that data added through save_temperature appears in cache."""
        source = "test/sensor"
        base_time = datetime.now(tz=UTC)

        # Add old data directly to database (simulating existing data)
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

        # Retrieve from cache - should only get the recent data
        since = base_time - timedelta(hours=3)
        results = database.get_temperatures_cached(source, since)

        # Should only get the recent entry (the one added via save_temperature)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][2], recent_temp)

        # But database has both entries
        db_results = database.get_temperatures(source, since)
        self.assertEqual(len(db_results), 2)

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
        cached_results = cache.get_temperatures_from_cache_only(source, since)

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

    def test_cache_with_old_data_coverage_issue(self):
        """Test that cache correctly handles old data that doesn't cover recent period."""
        source = "test/sensor"
        now = datetime.now(tz=UTC)

        # Add only old data to database (simulating cottage data copied to local env)
        old_data = [
            (now - timedelta(hours=4), Decimal("18.0")),
            (now - timedelta(hours=3), Decimal("19.0")),
            (
                now - timedelta(hours=2, minutes=30),
                Decimal("20.0"),
            ),  # Last data 2.5 hours ago
        ]

        with database.get_database_connection() as conn:
            cursor = conn.cursor()
            for timestamp, temperature in old_data:
                cursor.execute(
                    "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
                    (source, timestamp.isoformat(), temperature),
                )
            conn.commit()

        # Initialize cache from database
        cache.clear_cache()
        cache.initialize_cache_from_database()

        # Request last 24 hours of data (should be cache miss due to no recent coverage)
        since = now - timedelta(hours=24)
        results = database.get_temperatures_cached(source, since)

        # Should get all data from database (not cached data only)
        self.assertEqual(len(results), 3)

        # Verify the data is complete and correct
        result_temps = [r[2] for r in results]
        expected_temps = [Decimal("18.0"), Decimal("19.0"), Decimal("20.0")]
        self.assertEqual(result_temps, expected_temps)


if __name__ == "__main__":
    unittest.main()
