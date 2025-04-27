#!/bin/bash
set -e

uv run uvicorn mqtt_thermometer.service:app --host 0.0.0.0 --port 8001 --reload

