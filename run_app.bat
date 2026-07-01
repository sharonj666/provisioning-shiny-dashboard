@echo off
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
shiny run --reload app.py

