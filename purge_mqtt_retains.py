import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

client.connect("192.168.1.113", 1883)
client.publish(
    "mokki/tupa/temperature",
    None,
    retain=True,
)
client.publish(
    "mokki/kamari/temperature",
    None,
    retain=True,
)
client.publish(
    "mokki/terassi/temperature",
    None,
    retain=True,
)
client.publish(
    "mokki/sauna/temperature",
    None,
    retain=True,
)
client.disconnect()
