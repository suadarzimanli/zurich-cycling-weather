#!/bin/sh
# Zurich cycling and weather: run the web app locally (macOS, Linux)
cd "$(dirname "$0")/docs" || exit 1
echo "Open http://localhost:8000 in your browser. Press Ctrl+C to stop."
python3 -m http.server 8000
