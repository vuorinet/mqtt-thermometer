from pathlib import Path
from typing import Annotated, AsyncGenerator
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx, htmx_init
from sqlite3 import Connection
from mqtt_thermometer import database

app = FastAPI()
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


@app.get("/temperatures")
async def get_temperatures(
    request: Request, db: Annotated[Connection, Depends(get_db)]
):  # noqa: ARG001
    print(database.get_temperatures(db))
    return {
        "labels": [1, 2, 3],
        "datasets": [
            {
                "data": [1, 2, 3],
                "label": "Temperature",
                "borderColor": "#3e95cd",
                "backgroundColor": "#7bb6dd",
                "fill": True,
            },
        ],
    }
