@echo off
REM Zurich cycling and weather: run the web app locally (Windows)
REM Requires Python 3. Opens http://localhost:8000
cd /d "%~dp0docs"
echo Starting local server in: %CD%
echo Open http://localhost:8000 in your browser.
echo Press Ctrl+C to stop.
python -m http.server 8000
pause
