#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating local virtual environment in .venv ..."
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv .venv
  else
    python3 -m venv .venv
  fi
fi

source .venv/bin/activate
mkdir -p .cache/matplotlib
export MPLCONFIGDIR="$PWD/.cache/matplotlib"

if [ ! -f ".venv/.requirements-installed" ] || [ "requirements.txt" -nt ".venv/.requirements-installed" ]; then
  echo "Installing dashboard packages. This can take a few minutes the first time ..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  date > .venv/.requirements-installed
else
  echo "Packages already installed. Skipping install."
fi

echo "Starting dashboard ..."
echo "Open the local URL printed below, usually http://127.0.0.1:8000"
python -m shiny run --host 127.0.0.1 --port 8000 app.py
