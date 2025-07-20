#!/bin/bash
# Setup script for Raspberry Pi self-hosted runners

set -e

PI_NAME=$1
if [ -z "$PI_NAME" ]; then
    echo "Usage: $0 [home|cottage]"
    exit 1
fi

echo "Setting up Raspberry Pi: $PI_NAME"

# Create directory structure
sudo mkdir -p /srv/mqtt-thermometer/{config,data}
sudo chown -R pi:pi /srv/mqtt-thermometer

# Copy appropriate configuration
if [ "$PI_NAME" = "home" ]; then
    cp config/mqtt-thermometer-home.toml /srv/mqtt-thermometer/config/mqtt-thermometer.toml
elif [ "$PI_NAME" = "cottage" ]; then
    cp config/mqtt-thermometer-cottage.toml /srv/mqtt-thermometer/config/mqtt-thermometer.toml
else
    echo "Invalid PI_NAME. Use 'home' or 'cottage'"
    exit 1
fi

# Set permissions
chmod 644 /srv/mqtt-thermometer/config/mqtt-thermometer.toml

# Create docker-compose.yml for this Pi
cat > /srv/mqtt-thermometer/docker-compose.yml << EOF
version: '3.8'

services:
  mqtt-thermometer:
    image: ghcr.io/vuorinet/mqtt-thermometer:latest
    container_name: mqtt-thermometer
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./config/mqtt-thermometer.toml:/app/config/mqtt-thermometer.toml:ro
      - ./data:/app/data
    environment:
      - MQTT_THERMOMETER_CONFIG_PATH=/app/config/mqtt-thermometer.toml
      - MQTT_THERMOMETER_DB_PATH=/app/data/mqtt-thermometer.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/temperatures"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

echo "Setup complete for $PI_NAME!"
echo "Configuration file: /srv/mqtt-thermometer/config/mqtt-thermometer.toml"
echo "Data directory: /srv/mqtt-thermometer/data"
echo "Docker Compose file: /srv/mqtt-thermometer/docker-compose.yml"
echo ""
echo "Next steps:"
echo "1. Configure your MQTT broker IP in the config file"
echo "2. Set up GitHub Actions self-hosted runner with label 'raspi-$PI_NAME'"
echo "3. Push to master branch to trigger deployment"
echo ""
echo "Manual operations:"
echo "  Start:  cd /srv/mqtt-thermometer && docker-compose up -d"
echo "  Stop:   cd /srv/mqtt-thermometer && docker-compose down"
echo "  Logs:   cd /srv/mqtt-thermometer && docker-compose logs -f"
