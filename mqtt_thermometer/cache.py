import logging
import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

from mqtt_thermometer import database

logger = logging.getLogger(__name__)

# Cache data structure: {source: [(timestamp, temperature), ...]}
# Each source has a list of (timestamp, temperature) tuples sorted by timestamp
temperature_cache: Dict[str, List[Tuple[datetime, Decimal]]] = defaultdict(list)
cache_mutex = threading.RLock()

# Maximum age for cache entries (24 hours)
CACHE_MAX_AGE = timedelta(hours=24)


def add_temperature_to_cache(source: str, timestamp: datetime, temperature: Decimal):
    """Add a temperature reading to the cache and clean up old entries."""
    with cache_mutex:
        # Add the new entry
        temperature_cache[source].append((timestamp, temperature))

        # Keep the list sorted by timestamp
        temperature_cache[source].sort(key=lambda x: x[0])

        # Clean up old entries (older than 24 hours) every time we add new data
        cutoff_time = datetime.now(tz=UTC) - CACHE_MAX_AGE
        temperature_cache[source] = [
            (ts, temp) for ts, temp in temperature_cache[source] if ts >= cutoff_time
        ]

        logger.debug(f"Added temperature to cache: {source} {timestamp} {temperature}")


def get_temperatures_from_cache_only(
    source: str, since: datetime
) -> List[Tuple[str, str, Decimal]]:
    """Get temperature readings from cache only - no database fallback.

    Returns a list of (source, timestamp_iso, temperature) tuples.
    """
    with cache_mutex:
        if source not in temperature_cache:
            return []

        # Filter entries since the given timestamp
        cached_entries = [
            (source, timestamp.isoformat(), temperature)
            for timestamp, temperature in temperature_cache[source]
            if timestamp >= since
        ]

        logger.debug(
            f"Retrieved {len(cached_entries)} entries from cache for {source} since {since}"
        )
        return cached_entries


def get_temperatures_cached(
    source: str, since: datetime
) -> List[Tuple[str, str, Decimal]]:
    """Get temperature readings from cache only - no database fallback.

    Returns a list of (source, timestamp_iso, temperature) tuples.
    """
    return get_temperatures_from_cache_only(source, since)


def get_temperatures_bypass_cache(
    source: str, since: datetime
) -> List[Tuple[str, str, Decimal]]:
    """Get temperature readings directly from database, bypassing cache entirely.

    This function is useful for debugging cache issues or when you specifically
    need fresh data from the database.

    Returns a list of (source, timestamp_iso, temperature) tuples.
    """
    logger.debug(f"Bypassing cache: fetching from database for {source} since {since}")
    return database.get_temperatures(source, since)


def initialize_cache_from_database():
    """Initialize cache with the last 24 hours of data from database on startup."""
    logger.info("Initializing cache from database...")

    # Clear any existing cache data first
    clear_cache()

    # Get all unique sources from database
    try:
        with database.get_database_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT source FROM temperature")
            sources = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get sources from database: {e}")
        return

    # For each source, load last 24 hours of data
    since = datetime.now(tz=UTC) - CACHE_MAX_AGE
    total_loaded = 0

    for source in sources:
        try:
            # Get data from database
            db_data = database.get_temperatures(source, since)

            # Add to cache
            with cache_mutex:
                for _, timestamp_iso, temperature in db_data:
                    timestamp = datetime.fromisoformat(timestamp_iso)
                    temperature_cache[source].append((timestamp, temperature))

                # Keep sorted by timestamp
                temperature_cache[source].sort(key=lambda x: x[0])

            total_loaded += len(db_data)
            logger.debug(f"Loaded {len(db_data)} entries for source {source}")

        except Exception as e:
            logger.error(f"Failed to load cache data for source {source}: {e}")

    logger.info(
        f"Cache initialization completed. Loaded {total_loaded} total entries from database."
    )


def clear_cache():
    """Clear all cache data. Useful for testing or manual cache reset."""
    with cache_mutex:
        temperature_cache.clear()
        logger.info("Temperature cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about the current cache state."""
    with cache_mutex:
        stats = {}
        for source, entries in temperature_cache.items():
            stats[source] = len(entries)
        return stats
