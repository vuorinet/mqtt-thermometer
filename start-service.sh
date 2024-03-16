#!/bin/bash
set -e

uvicorn mqtt_thermometer.service:app --host 0.0.0.0 --port 8000 --reload

