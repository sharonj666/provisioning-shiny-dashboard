# Provisioning Analysis Shiny App

This bundle contains the files needed to run the uploadable provisioning
analysis dashboard. It does not contain project source data.

## Requirements

- Python 3.11 or 3.12
- Internet access during the initial package installation

## Setup

### macOS and Linux

Open a terminal in this folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows PowerShell

Open PowerShell in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script, allow it for the current session
and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

Open Command Prompt in this folder and run:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

## Launch

From this folder, run:

```bash
python -m shiny run --host 127.0.0.1 --port 8000 app.py
```

The same launch command works in Windows PowerShell and Command Prompt after
the virtual environment has been activated:

```powershell
python -m shiny run --host 127.0.0.1 --port 8000 app.py
```

If the browser does not open automatically, visit:

```text
http://127.0.0.1:8000
```

Stop the app with `Ctrl+C` in the terminal.

You can also set up and launch the app with `./run_app.sh` on macOS or Linux,
or `.\run_app.bat` on Windows.

## Using the app

1. Upload the provisioning workbook.
2. Upload the provisioning metadata CSV.
3. Optionally upload the adult transmitter workbook. Question 4 requires this
   file for tagged-parent versus untagged-parent analysis.
4. Review the file-validation messages.
5. Select **Run analysis**.
6. Review the data-quality, prey-rate, diet-composition, fish-rate, and
   tagged-parent analysis tabs.
7. Use the download buttons to save individual CSV tables or the complete ZIP
   result package.

Uploads are temporary and remain isolated to the browser session. The app does
not edit or save uploaded source files.

Zero-delivery monitored nest-stints are included in rate calculations. For
tagged-parent matching, known transmitter PFR codes are classified as tagged;
`NT`, `NOT TELEM`, `NO TELEM`, and `NON TELEM` are classified as untagged;
blank or unresolved adult IDs are included in the review output.

## Included files

```text
provisioning_shiny_dashboard/
├── README.md
├── app.py
├── check_setup.py
├── requirements.txt
├── run_app.bat
├── run_app.sh
├── analysis/
│   ├── charts.py
│   ├── core.py
│   ├── statistics.py
│   ├── tagged_parents.py
│   └── validation.py
├── data/
│   └── raw/
├── docs/
│   └── SHINY_DASHBOARD_GUIDE.md
└── scripts/
    └── clean_data.py
```
