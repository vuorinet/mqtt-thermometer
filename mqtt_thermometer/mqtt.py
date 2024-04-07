from datetime import UTC, datetime
from decimal import Decimal
from mqtt_thermometer import database
import time
import asyncio
import paho.mqtt.client as mqtt

from mqtt_thermometer.settings import settings

loop = asyncio.get_event_loop()
last_timestamp: datetime = datetime.now(tz=UTC).replace(second=0, microsecond=0)
source_temperatures: dict[str, list[Decimal]] = {}

connection = None
client = None

main_queue: asyncio.Queue | None = None


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"Failed to connect: {reason_code}. loop_forever() will retry connection")
    else:
        client.subscribe([(source.source, 1) for source in settings.sources])


def on_message(client, userdata, message):
    assert connection
    global last_timestamp, source_temperatures

    temperature = Decimal(message.payload.decode())
    source = message.topic
    source_temperatures.setdefault(source, []).append(temperature)
    timestamp = datetime.now(tz=UTC).replace(second=0, microsecond=0)

    assert main_queue
    asyncio.run_coroutine_threadsafe(main_queue.put((source, temperature)), loop)

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


def poll_mqtt_messages(queue: asyncio.Queue):
    global connection, client, main_queue
    main_queue = queue
    connection = database.get_database_connection()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    for _ in range(10):
        try:
            client.connect(settings.mqtt_broker.host, settings.mqtt_broker.port)
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
