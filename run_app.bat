@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Creating local virtual environment in .venv ...
    python -m venv .venv
)

call .venv\Scripts\activate
if not exist .cache\matplotlib mkdir .cache\matplotlib
set MPLCONFIGDIR=%CD%\.cache\matplotlib

if not exist .venv\.requirements-installed (
    echo Installing dashboard packages. This can take a few minutes the first time ...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    echo installed > .venv\.requirements-installed
) else (
    echo Packages already installed. Skipping install.
)

echo Starting dashboard ...
echo Open the local URL printed below, usually http://127.0.0.1:8000
python -m shiny run --host 127.0.0.1 --port 8000 app.py
