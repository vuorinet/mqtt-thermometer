#!/bin/bash
set -e
cp mqtt-thermometer.service /etc/systemd/system/
systemctl enable mqtt-thermometer.service
