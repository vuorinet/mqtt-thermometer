import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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
        await asyncio.sleep(10)
        for source in settings.sources:
            if (
                datetime.now(tz=UTC) - legend_data[source.label].last_updated
            ) >= timedelta(seconds=60 * 5):
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

    # Initialize cache with existing data from database
    from mqtt_thermometer import cache

    cache.initialize_cache_from_database()

    thread = Thread(target=mqtt.poll_mqtt_messages, args=(mqtt_message_queue,))
    thread.start()
    yield
    mqtt.stop_polling()
    thread.join()


app = FastAPI(lifespan=lifespan)

# Add version for cache busting
APP_VERSION = "1.0.0"  # Increment this on each deployment


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
    return {"version": APP_VERSION, "application_name": settings.application_name}


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
async def get_temperatures(request: Request):  # noqa: ARG001
    def _get_temperature_data(
        source: str, calibration_multiplier: Decimal, calibration_offset: Decimal
    ) -> dict[datetime, Decimal | None]:
        current_time = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        until = current_time  # Include the current minute in the range
        since = until - timedelta(hours=24)

        last_temperature = None
        temperature_data = _get_empty_temperature_data(since=since, until=until)
        for _, timestamp, temperature in database.get_temperatures_cached(
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

        # Add the very latest temperature reading from legend_data if available
        # This shows the most recent individual reading even before it's saved to database
        current_time = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        for legend_source, legend in legend_data.items():
            # Find matching source by comparing with source labels
            for settings_source in settings.sources:
                if (
                    settings_source.source == source
                    and settings_source.label == legend_source
                    and legend.temperature is not None
                ):
                    # Apply the same calibration as used for database values
                    latest_temp = (
                        legend.temperature * calibration_multiplier + calibration_offset
                    )
                    # Apply the same smoothing logic
                    if last_temperature is not None:
                        MAX_STEP = Decimal("0.5")
                        if latest_temp - last_temperature > MAX_STEP:
                            latest_temp = last_temperature + MAX_STEP
                        elif latest_temp - last_temperature < -MAX_STEP:
                            latest_temp = last_temperature - MAX_STEP

                    temperature_data[current_time] = latest_temp
                    break

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


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics - useful for monitoring cache performance."""
    try:
        from mqtt_thermometer import cache

        stats = cache.get_cache_stats()
        total_entries = sum(stats.values())
        return {
            "cache_stats": stats,
            "total_cached_entries": total_entries,
            "sources": list(stats.keys()),
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"error": "Failed to get cache statistics"}


@app.get("/debug/temperatures/{source}")
async def debug_temperatures(source: str, use_cache: bool = True, hours: int = 24):
    """Debug endpoint to compare cache vs database data for a specific source."""
    try:
        from mqtt_thermometer import cache

        since = datetime.now(tz=UTC) - timedelta(hours=hours)

        if use_cache:
            results = database.get_temperatures_cached(source, since)
            data_source = "cache"
        else:
            results = cache.get_temperatures_bypass_cache(source, since)
            data_source = "database"

        return {
            "source": source,
            "data_source": data_source,
            "hours": hours,
            "since": since.isoformat(),
            "count": len(results),
            "first_timestamp": results[0][1] if results else None,
            "last_timestamp": results[-1][1] if results else None,
            "sample_data": results[:5] if results else [],  # First 5 entries as sample
        }
    except Exception as e:
        logger.error(f"Failed to get debug temperatures: {e}")
        return {"error": f"Failed to get debug temperatures: {e}"}


# Add favicon route to handle direct requests
@app.get("/favicon.ico")
async def favicon():
    return FileResponse(Path(__file__).parent / "static" / "favicon.ico")


# Add manifest routes with correct MIME type for all possible paths
@app.get("/manifest.json")
@app.get("/site.webmanifest")
@app.get("/static/manifest.json")
@app.get("/static/site.webmanifest")
async def manifest(request: Request):
    static_templates = Jinja2Templates(directory=Path(__file__).parent / "static")
    template = static_templates.get_template("site.webmanifest")
    content = template.render(
        {"application_name": settings.application_name, "request": request}
    )
    return HTMLResponse(
        content=content,
        media_type="application/manifest+json",
    )


app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
