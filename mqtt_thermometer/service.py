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
    return {"greeting": "Temperatures at the cottage"}


async def get_db() -> AsyncGenerator[Connection, None]:
    db = database.get_database_connection()
    try:
        yield db
    finally:
        db.close()


def _get_empty_temperatures(
    since: datetime, until: datetime
) -> dict[datetime, Decimal | None]:
    temperatures = {}
    timestamp = since
    while timestamp <= until:
        temperatures[timestamp] = None
        timestamp += timedelta(minutes=1)
    return temperatures


@app.get("/temperatures")
async def get_temperatures(
    request: Request, database_connection: Annotated[Connection, Depends(get_db)]
):  # noqa: ARG001
    until = datetime.now(tz=UTC).replace(second=0, microsecond=0).astimezone()
    since = until - timedelta(hours=24)

    tupa_temperatures = _get_empty_temperatures(since=since, until=until)
    last_tupa_temperature: Decimal | None = None
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/tupa/temperature",
        since=since,
    ):
        tupa_temperature = float(temperature) * 0.94 + 2.2
        tupa_temperatures[
            datetime.fromisoformat(timestamp).astimezone()
        ] = tupa_temperature
        if tupa_temperature is not None:
            last_tupa_temperature = Decimal(tupa_temperature).quantize(Decimal("0.1"))

    kamari_temperatures = _get_empty_temperatures(since=since, until=until)
    last_kamari_temperature: Decimal | None = None
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/kamari/temperature",
        since=since,
    ):
        kamari_temperature = float(temperature) - 0.2
        kamari_temperatures[
            datetime.fromisoformat(timestamp).astimezone()
        ] = kamari_temperature
        if kamari_temperature is not None:
            last_kamari_temperature = Decimal(kamari_temperature).quantize(
                Decimal("0.1")
            )

    terassi_temperatures = _get_empty_temperatures(since=since, until=until)
    last_terassi_temperature: Decimal | None = None
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/terassi/temperature",
        since=since,
    ):
        terassi_temperature = float(temperature) - 0.25
        terassi_temperatures[
            datetime.fromisoformat(timestamp).astimezone()
        ] = terassi_temperature
        if terassi_temperature is not None:
            last_terassi_temperature = Decimal(terassi_temperature).quantize(
                Decimal("0.1")
            )

    sauna_temperatures = _get_empty_temperatures(since=since, until=until)
    last_sauna_temperature: Decimal | None = None
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/sauna/temperature",
        since=since,
    ):
        sauna_temperatures[datetime.fromisoformat(timestamp).astimezone()] = temperature
        if temperature is not None:
            last_sauna_temperature = Decimal(temperature).quantize(Decimal("0.1"))

    return {
        "labels": list(tupa_temperatures.keys()),
        "datasets": [
            {
                "data": list(tupa_temperatures.values()),
                "label": f"Tupa {last_tupa_temperature} °C",
                "borderColor": "#00dd00",
                "backgroundColor": "#00ff00",
            },
            {
                "data": list(kamari_temperatures.values()),
                "label": f"Kamari {last_kamari_temperature} °C",
                "borderColor": "#00eeee",
                "backgroundColor": "#00ddee",
            },
            {
                "data": list(terassi_temperatures.values()),
                "label": f"Terassi  {last_terassi_temperature} °C",
                "borderColor": "#dd0000",
                "backgroundColor": "#ff0000",
            },
            {
                "data": list(sauna_temperatures.values()),
                "label": f"Sauna  {last_sauna_temperature} °C",
                "borderColor": "#dddd00",
                "backgroundColor": "#ffff00",
            },
        ],
    }


app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
