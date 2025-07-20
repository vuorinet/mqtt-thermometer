# Docker Deployment Guide

## Prerequisites for Raspberry Pi Setup

### 1. Install Docker on each Raspberry Pi

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
sudo systemctl enable docker
sudo systemctl start docker
```

### 2. Set up directory structure

```bash
# Run this on each Raspberry Pi
sudo mkdir -p /home/pi/mqtt-thermometer/{config,data}
sudo chown -R pi:pi /home/pi/mqtt-thermometer
```

### 3. Configure each Raspberry Pi

```bash
# For home Pi
cp config/mqtt-thermometer-home.toml /home/pi/mqtt-thermometer/config/mqtt-thermometer.toml

# For cottage Pi
cp config/mqtt-thermometer-cottage.toml /home/pi/mqtt-thermometer/config/mqtt-thermometer.toml
```

### 4. Set up GitHub Actions self-hosted runners

1. Go to your repository Settings → Actions → Runners
2. Add self-hosted runner for each Pi with labels:
   - `raspi-home` for the home Raspberry Pi
   - `raspi-cottage` for the cottage Raspberry Pi

## Automated Setup

```bash
# Use the setup script
./scripts/setup-raspi.sh home     # For home Pi
./scripts/setup-raspi.sh cottage  # For cottage Pi
```

## Manual Docker Operations

### Build locally for ARM64

```bash
docker buildx build --platform linux/arm64 -t mqtt-thermometer .
```

### Run container manually

```bash
docker run -d \
  --name mqtt-thermometer \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /home/pi/mqtt-thermometer/config/mqtt-thermometer.toml:/app/config/mqtt-thermometer.toml:ro \
  -v /home/pi/mqtt-thermometer/data:/app/data \
  mqtt-thermometer:latest
```

### Development with docker-compose

```bash
# Local development
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration

### Environment Variables

- `MQTT_THERMOMETER_CONFIG_PATH`: Path to TOML config file (default: `/app/config/mqtt-thermometer.toml`)
- `MQTT_THERMOMETER_DB_PATH`: Database file path (default: `/app/data/mqtt-thermometer.db`)

### Volume Mounts

- **Config**: Mount your TOML configuration file to `/app/config/mqtt-thermometer.toml`
- **Data**: Mount persistent storage to `/app/data` for the SQLite database

### Example TOML Configuration

```toml
db_connection_string = "/app/data/mqtt-thermometer.db"

[mqtt_broker]
host = "192.168.1.12"
port = 1883

[[sources]]
label = "Living Room"
source = "home/livingroom/temperature"
calibration_multiplier = 1.0
calibration_offset = 0.0
border_color = "#00dd00"
background_color = "#00ff00"
```

## CI/CD Pipeline

The GitHub Actions workflow automatically:

1. **Builds** ARM64 Docker image on GitHub-hosted runners
2. **Pushes** image to GitHub Container Registry
3. **Deploys** to both Raspberry Pis in parallel using self-hosted runners
4. **Verifies** deployment with health checks

### Deployment triggers:

- Push to `master` branch
- Manual workflow dispatch

### Monitoring:

- Container health checks every 30 seconds
- HTTP endpoint verification post-deployment
- Automatic container restart on failure

## Troubleshooting

### Check container status

```bash
docker ps | grep mqtt-thermometer
docker logs mqtt-thermometer
```

### Verify configuration

```bash
docker exec mqtt-thermometer cat /app/config/mqtt-thermometer.toml
```

### Test connectivity

```bash
curl http://localhost:8000/temperatures
```

### Update deployment

```bash
# The CI/CD pipeline handles updates automatically
# Or manually pull and restart:
docker pull ghcr.io/your-username/mqtt-thermometer:latest
docker stop mqtt-thermometer
docker rm mqtt-thermometer
# Run with new image...
```
