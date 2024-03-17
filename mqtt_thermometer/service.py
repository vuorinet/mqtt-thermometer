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


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.create_table()
    thread = Thread(target=mqtt.poll_mqtt_messages)
    thread.start()
    yield
    thread.join()


app = FastAPI(lifespan=lifespan)
htmx_init(templates=Jinja2Templates(directory=Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
@htmx("index", "index")
async def root_page(request: Request):
    return {"greeting": "Hello World"}


@app.get("/customers", response_class=HTMLResponse)
@htmx("customers")
async def get_customers(request: Request):
    return {"customers": ["John Doe", "Jane Doe"]}


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
    temperatures = _get_empty_temperatures(since=since, until=until)

    for _, timestamp, temperature in database.get_temperatures(
        database_connection,
        source="mokki/tupa/temperature",
        since=since,
    ):
        temperatures[datetime.fromisoformat(timestamp).astimezone()] = temperature

    return {
        "labels": list(temperatures.keys()),
        "datasets": [
            {
                "data": list(temperatures.values()),
                "label": "Temperature",
                "borderColor": "#3e95cd",
                "backgroundColor": "#7bb6dd",
                "fill": True,
            },
        ],
    }
