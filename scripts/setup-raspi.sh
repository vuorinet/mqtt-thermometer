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
sudo mkdir -p /srv/mqtt-thermometer/data
sudo chown -R pi:pi /srv/mqtt-thermometer

# Copy appropriate configuration
if [ "$PI_NAME" = "home" ]; then
    cp config/mqtt-thermometer-home.toml /srv/mqtt-thermometer/mqtt-thermometer.toml
elif [ "$PI_NAME" = "cottage" ]; then
    cp config/mqtt-thermometer-cottage.toml /srv/mqtt-thermometer/mqtt-thermometer.toml
else
    echo "Invalid PI_NAME. Use 'home' or 'cottage'"
    exit 1
fi

# Set permissions
chmod 644 /srv/mqtt-thermometer/mqtt-thermometer.toml

# Copy production docker-compose.yml for this Pi
cp docker-compose.production.yml /srv/mqtt-thermometer/docker-compose.yml

echo "Setup complete for $PI_NAME!"
echo "Configuration file: /srv/mqtt-thermometer/mqtt-thermometer.toml"
echo "Database file: /srv/mqtt-thermometer/data/mqtt-thermometer.db (will be created on first run)"
echo "Docker Compose file: /srv/mqtt-thermometer/docker-compose.yml"
echo ""
echo "Next steps:"
echo "1. Configure your MQTT broker IP in the config file"
echo "2. Set up GitHub Actions self-hosted runner with label 'raspi-$PI_NAME'"
echo "3. Push to master branch to trigger deployment"
echo ""
echo "Manual operations:"
echo "  Start:  cd /srv/mqtt-thermometer && docker compose up -d"
echo "  Stop:   cd /srv/mqtt-thermometer && docker compose down"
echo "  Logs:   cd /srv/mqtt-thermometer && docker compose logs -f"
