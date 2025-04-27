import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from sqlite3 import Connection
from threading import Thread
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx, htmx_init

from mqtt_thermometer import database, mqtt
from mqtt_thermometer.settings import settings

mqtt_message_queue = asyncio.Queue(maxsize=1)

ws_connections: set[WebSocket] = set()

logger = logging.getLogger(__name__)


@dataclass
class LegendData:
    label: str
    temperature: Decimal | None
    border_color: str
    background_color: str
    last_updated: datetime


legend_data: dict[str, LegendData] = {
    source.label: LegendData(
        label=source.label,
        temperature=None,
        border_color=source.border_color.as_hex("long"),
        background_color=source.background_color.as_hex("long"),
        last_updated=datetime.now(tz=UTC),
    )
    for source in settings.sources
}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
htmx_init(templates=templates)


def _get_legends_element():
    return templates.get_template("legends.jinja2").render({"legend_data": legend_data})


async def _broadcast_temperature_data():
    text = _get_legends_element()
    for websocket in ws_connections.copy():
        try:
            await websocket.send_text(text)
        except WebSocketDisconnect:
            logger.warning("Failed to send temperature data to websocket")
            if websocket in ws_connections:
                ws_connections.remove(websocket)


async def reset_inactive_temperatures():
    while True:
        await asyncio.sleep(60)
        for source in settings.sources:
            if (
                datetime.now(tz=UTC) - legend_data[source.label].last_updated
            ) >= timedelta(seconds=60):
                legend_data[source.label] = LegendData(
                    label=source.label,
                    temperature=None,
                    border_color=source.border_color.as_hex("long"),
                    background_color=source.background_color.as_hex("long"),
                    last_updated=datetime.now(tz=UTC),
                )
        await _broadcast_temperature_data()


async def process_mqtt_queue(queue):
    while True:
        source_mqtt_topic, temperature = await queue.get()
        for source in settings.sources:
            if source.source == source_mqtt_topic:
                temperature = (
                    temperature * source.calibration_multiplier
                    + source.calibration_offset
                )
                legend_data[source.label] = LegendData(
                    label=source.label,
                    temperature=temperature.quantize(Decimal("0.1")),
                    border_color=source.border_color.as_hex("long"),
                    background_color=source.background_color.as_hex("long"),
                    last_updated=datetime.now(tz=UTC),
                )
                await _broadcast_temperature_data()
                break
        queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(process_mqtt_queue(mqtt_message_queue))
    asyncio.create_task(reset_inactive_temperatures())
    database.create_table()
    thread = Thread(target=mqtt.poll_mqtt_messages, args=(mqtt_message_queue,))
    thread.start()
    yield
    mqtt.stop_polling()
    thread.join()


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)
    try:
        await websocket.send_text(_get_legends_element())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections.remove(websocket)


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

        last_temperature = None
        temperature_data = _get_empty_temperature_data(since=since, until=until)
        for _, timestamp, temperature in database.get_temperatures(
            database_connection,
            source=source,
            since=since,
        ):
            temperature = (
                Decimal(temperature) * calibration_multiplier + calibration_offset
            )
            MAX_STEP = Decimal("0.5")
            if last_temperature is not None:
                if temperature - last_temperature > MAX_STEP:
                    temperature = last_temperature + MAX_STEP
                elif temperature - last_temperature < -MAX_STEP:
                    temperature = last_temperature - MAX_STEP
            last_temperature = temperature
            time_index = datetime.fromisoformat(timestamp).astimezone()
            if time_index in temperature_data:
                temperature_data[time_index] = temperature
        for index, (timestamp, temperature) in enumerate(temperature_data.items()):
            if temperature is None and index > 0 and index < len(temperature_data) - 1:
                previous_temperature = list(temperature_data.values())[index - 1]
                next_temperature = list(temperature_data.values())[index + 1]
                if previous_temperature is not None and next_temperature is not None:
                    temperature_data[timestamp] = (
                        previous_temperature + next_temperature
                    ) / 2

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
                "label": source.label,
                "borderColor": source.border_color.as_hex("long"),
                "backgroundColor": source.background_color.as_hex("long"),
                "borderJoinStyle": "round",
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


# Add favicon route to handle direct requests
@app.get("/favicon.ico")
async def favicon():
    return FileResponse(Path(__file__).parent / "static" / "favicon.ico")


# Add manifest routes with correct MIME type for all possible paths
@app.get("/manifest.json")
@app.get("/site.webmanifest")
@app.get("/static/manifest.json")
@app.get("/static/site.webmanifest")
async def manifest():
    return FileResponse(
        Path(__file__).parent / "static" / "site.webmanifest",
        media_type="application/manifest+json",
    )


app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
