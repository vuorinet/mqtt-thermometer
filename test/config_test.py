from decimal import Decimal
from mqtt_thermometer.settings import settings, get_sources


def test_config():
    assert settings.mqtt_broker.host == "192.168.1.113"
    assert settings.mqtt_broker.port == 1883

    tupa_source = settings.sources[0]
    assert tupa_source.label == "Tupa"
    assert tupa_source.calibration_multiplier == Decimal("0.94")
    assert tupa_source.calibration_offset == Decimal("2.2")
    assert tupa_source.source == "mokki/tupa/temperature"
    assert tupa_source.border_color.as_hex("long") == "#00dd00"
    assert tupa_source.background_color.as_hex("long") == "#00ff00"

    sauna_source = settings.sources[3]
    assert sauna_source.label == "Sauna"
    assert sauna_source.calibration_multiplier == Decimal("1.0")
    assert sauna_source.calibration_offset == Decimal("0.0")
    assert sauna_source.source == "mokki/sauna/temperature"
    assert sauna_source.border_color.as_hex("long") == "#dddd00"
    assert sauna_source.background_color.as_hex("long") == "#ffff00"


def test_get_sources():
    sources = get_sources()
    assert sources == [
        "mokki/tupa/temperature",
        "mokki/kamari/temperature",
        "mokki/terassi/temperature",
        "mokki/sauna/temperature",
    ]
