# MQTT Thermometer

The goal of this project is to monitor temperature from various sources using MQTT topics. The temperatures will be stored in a local database and displayed on a web page for the last 24 hours.

![Screenshot](screenshot.png)

## Features

- **Real-time temperature monitoring** from multiple MQTT sources
- **24-hour historical data** with interactive charts
- **In-memory cache** for faster data retrieval (new!)
- **Calibration support** for individual sensors
- **WebSocket updates** for real-time display
- **Docker deployment** with automated CI/CD

## Performance

The application now includes an intelligent caching system that stores the last 24 hours of temperature readings in memory. This provides:

- **Instant startup performance** - cache is populated with existing data on startup
- **Faster API responses** for historical data queries
- **Reduced database load** for frequently accessed data
- **Automatic cache management** with 24-hour data retention
- **Seamless fallback** to database when cache misses occur

Cache statistics are available at `/cache/stats` endpoint for monitoring.

# Prerequisites

MQTT broker (for example https://mosquitto.org/) must be installed and running.

Use recent enough version of Python. This project is developed using Python 3.12.

The project utilizes FastAPI, fastapi-htmx, Pydantic, Paho-MQTT and Uvicorn.

The project does not rely on NPM or NodeJS 💪. Instead, it utilizes htmx (https://htmx.org/), Chart.js (https://www.chartjs.org/), and some vanilla JavaScript for interactivity.

## Run locally

```bash
uv sync
uv run uvicorn mqtt_thermometer.service:app --reload
```

--> Navigate to http://localhost:8000.

## Deploy on Raspberry Pi

This project uses Docker containers with automated CI/CD deployment.

### Initial Setup

1. **Set up the Raspberry Pi:**

   ```bash
   # Clone the repository
   git clone https://github.com/vuorinet/mqtt-thermometer.git
   cd mqtt-thermometer

   # Run setup script (choose 'home' or 'cottage')
   ./scripts/setup-raspi.sh home
   ```

2. **Configure MQTT settings:**
   Edit `/srv/mqtt-thermometer/config/mqtt-thermometer.toml` with your MQTT broker details.

3. **Set up GitHub Actions self-hosted runner:**
   - Follow GitHub's instructions to install the runner
   - Use labels: `[self-hosted, Linux, ARM64, raspi-home]` or `raspi-cottage`

### Automated Deployment

Push to the `master` branch to trigger automatic deployment to all configured Raspberry Pi devices.

### Manual Operations

```bash
cd /srv/mqtt-thermometer

# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f
```
