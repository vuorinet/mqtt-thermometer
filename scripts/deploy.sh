#!/bin/bash
set -e


sudo systemctl stop mqtt-thermometer.service || true
sudo rm /etc/systemd/system/mqtt-thermometer.service || true

sudo cp /srv/mqtt-thermometer/*.db /tmp || true
sudo cp /srv/mqtt-thermometer/mqtt-thermometer.toml /tmp || true

sudo rm -rf /srv/mqtt-thermometer/*

sudo env "PATH=$PATH:/root/.local/bin" uv --directory /srv/mqtt-thermometer \
  venv \
  --no-project \
  --python 3.13

sudo env "PATH=$PATH:/root/.local/bin" uv --directory /srv/mqtt-thermometer \
  pip \
  install \
  /tmp/mqtt_thermometer-0.1.0-py3-none-any.whl \
  uvicorn

sudo mv /tmp/*.db /srv/mqtt-thermometer || true
sudo mv /tmp/mqtt-thermometer.toml /srv/mqtt-thermometer || true
sudo rm /tmp/*.whl || true

sudo mv /tmp/mqtt-thermometer.service /etc/systemd/system/mqtt-thermometer.service
sudo systemctl daemon-reload
sudo systemctl enable mqtt-thermometer.service
sudo systemctl start mqtt-thermometer.service
