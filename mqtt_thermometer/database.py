import sqlite3
import threading
from datetime import datetime
from decimal import Decimal
from sqlite3 import Connection

from mqtt_thermometer.settings import settings

# Create a mutex for database operations
db_mutex = threading.RLock()


def adapt_decimal(d):
    return str(d)


def convert_decimal(s):
    return Decimal(s)


sqlite3.register_adapter(Decimal, adapt_decimal)
sqlite3.register_converter("DECTEXT", convert_decimal)


def get_database_connection() -> Connection:
    return sqlite3.connect(settings.db_connection_string)


def create_table():
    with db_mutex:
        connection = get_database_connection()
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


def save_temperature(
    connection: Connection, source: str, timestamp: datetime, temperature: Decimal
):
    with db_mutex:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
            (source, timestamp.isoformat(), temperature),
        )
        connection.commit()


def get_temperatures(connection: Connection, source: str, since: datetime):
    with db_mutex:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT source, timestamp, temperature FROM temperature "
            f"WHERE source='{source}' AND timestamp >= '{since.isoformat()}'"
            "ORDER BY timestamp"
        )
        return cursor.fetchall()


if __name__ == "__main__":
    create_table()
