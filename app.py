from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_htmx import htmx, htmx_init

app = FastAPI()
htmx_init(templates=Jinja2Templates(directory=Path(".") / "templates"))


@app.get("/", response_class=HTMLResponse)
@htmx("index", "index")
async def root_page(request: Request):
    return {"greeting": "Hello World"}


@app.get("/customers", response_class=HTMLResponse)
@htmx("customers")
async def get_customers(request: Request):
    return {"customers": ["John Doe", "Jane Doe"]}


@app.get("/temperatures")
def get_temperatures(request: Request):  # noqa: ARG001
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
