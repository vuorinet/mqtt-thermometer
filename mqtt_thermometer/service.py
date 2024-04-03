from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Thread
from typing import Annotated, AsyncGenerator
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx, htmx_init
from sqlite3 import Connection
from mqtt_thermometer import database
from mqtt_thermometer import mqtt
from fastapi.staticfiles import StaticFiles

from mqtt_thermometer.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.create_table()
    thread = Thread(target=mqtt.poll_mqtt_messages)
    thread.start()
    yield
    mqtt.stop_polling()
    thread.join()


app = FastAPI(lifespan=lifespan)
htmx_init(templates=Jinja2Templates(directory=Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
@htmx("index", "index")
async def root_page(request: Request):
    return {}


async def get_db() -> AsyncGenerator[Connection, None]:
    db = database.get_database_connection()
    try:
        yield db
    finally:
        db.close()


def _get_empty_temperature_data(
    since: datetime, until: datetime
) -> dict[datetime, Decimal | None]:
    empty_temperature_data = {}
    timestamp = since
    while timestamp <= until:
        empty_temperature_data[timestamp] = None
        timestamp += timedelta(minutes=1)
    return empty_temperature_data


@app.get("/temperatures")
async def get_temperatures(
    request: Request, database_connection: Annotated[Connection, Depends(get_db)]
):  # noqa: ARG001
    def _get_temperature_data(
        source: str, calibration_multiplier: Decimal, calibration_offset: Decimal
    ) -> dict[datetime, Decimal | None]:
        until = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        since = until - timedelta(hours=24)

        temperature_data = _get_empty_temperature_data(since=since, until=until)
        for _, timestamp, temperature in database.get_temperatures(
            database_connection,
            source=source,
            since=since,
        ):
            terassi_temperature = (
                Decimal(temperature) * calibration_multiplier + calibration_offset
            )
            temperature_data[
                datetime.fromisoformat(timestamp).astimezone()
            ] = terassi_temperature
        return temperature_data

    def _get_last_known_temperature(
        temperature_data: dict[datetime, Decimal | None],
    ) -> Decimal | None:
        temperatures = list(temperature_data.values())
        if temperatures[-1] is not None:
            return Decimal(temperatures[-1]).quantize(Decimal("0.1"))
        elif temperatures[-2] is not None:
            return Decimal(temperatures[-2]).quantize(Decimal("0.1"))
        else:
            return None

    return {
        "datasets": [
            {
                "data": temperature_data,
                "label": f"{source.label} {_get_last_known_temperature(temperature_data)} °C",
                "borderColor": source.border_color.as_hex("long"),
                "backgroundColor": source.background_color.as_hex("long"),
            }
            for source in settings.sources
            if (
                temperature_data := _get_temperature_data(
                    source=source.source,
                    calibration_multiplier=source.calibration_multiplier,
                    calibration_offset=source.calibration_offset,
                )
            )
        ],
    }


app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
