import asyncio
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal

import paho.mqtt.client as mqtt

from mqtt_thermometer import database
from mqtt_thermometer.settings import settings

loop = asyncio.get_event_loop()
last_timestamp: datetime = datetime.now(tz=UTC).replace(second=0, microsecond=0)
source_temperatures: dict[str, list[Decimal]] = {}

client = None

main_queue: asyncio.Queue | None = None

logger = logging.getLogger(__name__)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        logger.error("Failed to connect: %s", reason_code)
    else:
        client.subscribe([(source.source, 1) for source in settings.sources])


def on_message(client, userdata, message):
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
        logger.debug(
            "Saving temperature: %s %s %s",
            last_timestamp.astimezone(),
            source,
            average_temperature,
        )
        success = database.save_temperature(source, last_timestamp, average_temperature)
        if not success:
            logger.error("Failed to save temperature for source: %s", source)
    source_temperatures.clear()
    last_timestamp = timestamp


def poll_mqtt_messages(queue: asyncio.Queue):
    global client, main_queue
    main_queue = queue

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    for _ in range(10):
        try:
            client.connect(settings.mqtt_broker.host, settings.mqtt_broker.port)
            break
        except OSError as e:
            logger.error("Failed to connect: %s. Retrying in 10 seconds...", e)
            time.sleep(10)
    else:
        msg = "Failed to connect after 10 retries. Exiting..."
        raise ConnectionError(msg)

    client.loop_forever()


def stop_polling():
    assert client
    client.disconnect()


if __name__ == "__main__":
    import asyncio

    queue = asyncio.Queue()
    poll_mqtt_messages(queue)
