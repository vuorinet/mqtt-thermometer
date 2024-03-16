from datetime import datetime, UTC
from mqtt_thermometer import service


def test_get_empty_temperatures():
    since = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
    until = datetime(2021, 1, 1, 0, 3, 0, tzinfo=UTC)

    temperatures = service._get_empty_temperatures(since, until)

    assert temperatures == {
        datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC): None,
        datetime(2021, 1, 1, 0, 1, 0, tzinfo=UTC): None,
        datetime(2021, 1, 1, 0, 2, 0, tzinfo=UTC): None,
        datetime(2021, 1, 1, 0, 3, 0, tzinfo=UTC): None,
    }
