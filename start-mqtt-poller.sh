#!/bin/bash
set -e

PYTHONPATH=. python3 mqtt_thermometer/database.py
PYTHONPATH=. python3 mqtt_thermometer/mqtt.py
```
