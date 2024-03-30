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
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/tupa/temperature",
        since=since,
    ):
        tupa_temperatures[datetime.fromisoformat(timestamp).astimezone()] = (
            float(temperature) * 0.94 + 2.2
        )

    kamari_temperatures = _get_empty_temperatures(since=since, until=until)
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/kamari/temperature",
        since=since,
    ):
        kamari_temperatures[datetime.fromisoformat(timestamp).astimezone()] = (
            float(temperature) - 0.2
        )

    terassi_temperatures = _get_empty_temperatures(since=since, until=until)
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/terassi/temperature",
        since=since,
    ):
        terassi_temperatures[datetime.fromisoformat(timestamp).astimezone()] = (
            float(temperature) - 0.25
        )

    sauna_temperatures = _get_empty_temperatures(since=since, until=until)
    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/sauna/temperature",
        since=since,
    ):
        sauna_temperatures[datetime.fromisoformat(timestamp).astimezone()] = temperature

    return {
        "labels": list(tupa_temperatures.keys()),
        "datasets": [
            {
                "data": list(tupa_temperatures.values()),
                "label": "Tupa",
                "borderColor": "#00dd00",
                "backgroundColor": "#00ff00",
            },
            {
                "data": list(kamari_temperatures.values()),
                "label": "Kamari",
                "borderColor": "#00eeee",
                "backgroundColor": "#00ddee",
            },
            {
                "data": list(terassi_temperatures.values()),
                "label": "Terassi",
                "borderColor": "#dd0000",
                "backgroundColor": "#ff0000",
            },
            {
                "data": list(sauna_temperatures.values()),
                "label": "Sauna",
                "borderColor": "#dddd00",
                "backgroundColor": "#ffff00",
            },
        ],
    }


app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
