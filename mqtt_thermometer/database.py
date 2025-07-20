import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

from mqtt_thermometer.settings import settings

logger = logging.getLogger(__name__)

# Create a mutex for database operations
db_mutex = threading.RLock()


def adapt_decimal(d):
    return str(d)


def convert_decimal(s):
    """Convert database value to Decimal, handling various input types."""
    if isinstance(s, bytes):
        return Decimal(s.decode("utf-8"))
    elif isinstance(s, str):
        return Decimal(s)
    elif isinstance(s, Decimal):
        return s
    else:
        return Decimal(str(s))


sqlite3.register_adapter(Decimal, adapt_decimal)
sqlite3.register_converter("DECTEXT", convert_decimal)


@contextmanager
def get_database_connection():
    connection = None
    try:
        connection = sqlite3.connect(
            settings.db_connection_string, detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Ensure our custom types are registered for this connection
        connection.execute(
            "PRAGMA table_info(temperature)"
        )  # This helps ensure types are loaded
        yield connection
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()


def create_table():
    with db_mutex:
        with get_database_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS temperature ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "source TEXT, "
                "timestamp TEXT, "
                "temperature DECTEXT"
                ")"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS timestamp_index ON temperature (timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS source_index ON temperature (source)"
            )
            connection.commit()


def save_temperature(source: str, timestamp: datetime, temperature: Decimal) -> bool:
    """Save a temperature reading to the database.

    Returns True if successful, False otherwise.
    """
    try:
        with db_mutex:
            with get_database_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
                    (source, timestamp.isoformat(), temperature),
                )
                connection.commit()
                return True
    except Exception as e:
        logger.error(f"Failed to save temperature: {e}")
        return False


def get_temperatures(source: str, since: datetime) -> list:
    """Get temperature readings from a specific source since a given timestamp.

    Returns a list of (source, timestamp, temperature) tuples.
    """
    try:
        with db_mutex:
            with get_database_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT source, timestamp, temperature FROM temperature "
                    "WHERE source=? AND timestamp >= ? ORDER BY timestamp",
                    (source, since.isoformat()),
                )
                results = cursor.fetchall()

                # Ensure temperature values are properly converted to Decimal
                converted_results = []
                for row in results:
                    source_val, timestamp_val, temperature_val = row
                    # Handle potential bytes to Decimal conversion
                    if isinstance(temperature_val, bytes):
                        temperature_val = Decimal(temperature_val.decode("utf-8"))
                    elif isinstance(temperature_val, str):
                        temperature_val = Decimal(temperature_val)
                    elif not isinstance(temperature_val, Decimal):
                        temperature_val = Decimal(str(temperature_val))

                    converted_results.append(
                        (source_val, timestamp_val, temperature_val)
                    )

                return converted_results
    except Exception as e:
        logger.error(f"Failed to get temperatures: {e}")
        return []


if __name__ == "__main__":
    create_table()
