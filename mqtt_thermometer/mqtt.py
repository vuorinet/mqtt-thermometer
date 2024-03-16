from datetime import UTC, datetime
from decimal import Decimal
import paho.mqtt.subscribe
from mqtt_thermometer import database


last_timestamp: datetime = datetime.now(tz=UTC).replace(second=0, microsecond=0)
source_temperatures: dict[str, list[Decimal]] = {}

connection = database.get_database_connection()


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
        database.save_temperature(
            connection, source, last_timestamp, average_temperature
        )
    source_temperatures = {}
    last_timestamp = timestamp


paho.mqtt.subscribe.callback(
    on_message,
    [
        ("mokki/tupa/temperature", 1),
        ("mokki/kamari/temperature", 1),
        ("mokki/terassi/temperature", 1),
        ("mokki/sauna/temperature", 1),
    ],
    hostname="192.168.1.113",
)
