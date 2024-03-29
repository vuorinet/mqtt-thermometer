from datetime import UTC, datetime
from decimal import Decimal
from mqtt_thermometer import database
import time

import paho.mqtt.client as mqtt

last_timestamp: datetime = datetime.now(tz=UTC).replace(second=0, microsecond=0)
source_temperatures: dict[str, list[Decimal]] = {}

connection = None
client = None


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Failed to connect: {reason_code}. loop_forever() will retry connection")
    else:
        client.subscribe(
            [
                ("mokki/tupa/temperature", 1),
                ("mokki/kamari/temperature", 1),
                ("mokki/terassi/temperature", 1),
                ("mokki/sauna/temperature", 1),
            ]
        )


def on_message(client, userdata, message):
    assert connection
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
    source_temperatures.clear()
    last_timestamp = timestamp


def poll_mqtt_messages():
    global connection, client
    connection = database.get_database_connection()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    for _ in range(10):
        try:
            client.connect("192.168.1.113", 1883)
            break
        except OSError as e:
            print(f"Failed to connect: {e}. Retrying in 10 seconds...")
            time.sleep(10)
    else:
        msg = "Failed to connect after 10 retries. Exiting..."
        raise ConnectionError(msg)

    client.loop_forever()

    connection.close()


def stop_polling():
    assert client
    client.disconnect()


if __name__ == "__main__":
    poll_mqtt_messages()
