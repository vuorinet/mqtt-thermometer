from datetime import UTC, datetime
from decimal import Decimal
import sqlite3
import paho.mqtt.subscribe


def adapt_decimal(d):
    return str(d)


def convert_decimal(s):
    return Decimal(s)


sqlite3.register_adapter(Decimal, adapt_decimal)
sqlite3.register_converter("DECTEXT", convert_decimal)

db = sqlite3.connect("mokki.db")
cursor = db.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS temperature ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "source TEXT, "
    "timestamp TEXT, "
    "temperature DECTEXT"
    ")"
)
cursor.execute("CREATE INDEX IF NOT EXISTS timestamp_index ON temperature (timestamp)")
cursor.execute("CREATE INDEX IF NOT EXISTS source_index ON temperature (source)")
db.commit()

last_timestamp: datetime = datetime.now(tz=UTC).replace(second=0, microsecond=0)
source_temperatures: dict[str, list[Decimal]] = {}


def on_message(client, userdata, message):
    global last_timestamp, source_temperatures

    temperature = Decimal(message.payload.decode())
    source = message.topic

    source_temperatures.setdefault(source, []).append(temperature)
    timestamp = datetime.now(tz=UTC).replace(second=0, microsecond=0)

    if timestamp == last_timestamp:
        return

    for source, temperatures in source_temperatures.items():
        average_temperature = Decimal(sum(temperatures) / len(temperatures)).quantize(
            Decimal("0.11")
        )
        print(last_timestamp.astimezone(), source, average_temperature)
        cursor.execute(
            "INSERT INTO temperature (source, timestamp, temperature) VALUES (?, ?, ?)",
            (source, last_timestamp.isoformat(), average_temperature),
        )
        db.commit()

    temperatures = []
    last_timestamp = timestamp


paho.mqtt.subscribe.callback(
    on_message,
    [
        ("mokki/tupa/temperature", 1),
        ("mokki/kamari/temperature", 1),
        ("mokki/terassi/temperature", 1),
        ("mokki/sauna/temperature", 1),
    ],
    hostname="localhost",
)
