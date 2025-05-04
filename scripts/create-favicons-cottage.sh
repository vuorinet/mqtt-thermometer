#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"/../mqtt_thermometer

inkscape -w 16 -h 16 icon-cottage.svg -o static/favicon-16x16.png
inkscape -w 32 -h 32 icon-cottage.svg -o static/favicon-32x32.png
inkscape -w 180 -h 180 icon-cottage.svg -o static/apple-touch-icon.png
inkscape -w 192 -h 192 icon-cottage.svg -o static/android-chrome-192x192.png
inkscape -w 512 -h 512 icon-cottage.svg -o static/android-chrome-512x512.png

convert static/favicon-16x16.png static/favicon-32x32.png static/favicon.ico
