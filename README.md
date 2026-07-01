# Provisioning Analysis Dashboard

This Shiny app lets a nontechnical user upload raw provisioning files and generate the provisioning analysis without writing Python code.

## What The App Does

After you upload the files and click **Run analysis**, the dashboard creates:

- data-quality summary;
- mean prey delivered per hour;
- diet composition summaries;
- fish delivered per hour and fish per chick-hour;
- tagged-parent versus untagged-parent provisioning summaries;
- ambiguous parent-status review table;
- downloadable CSV result package.

## Files You Need

The app asks you to upload these files in the browser:

```text
2025 PROVISIONING DATA ENTRY.xlsx
PROV METADATA(Sheet1).csv
Adult transmitter tagging banding data 2025 field season.xlsx
```

The adult transmitter file is optional, but Question 4 needs it.

## Quick Start

Open a terminal in this folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
shiny run --reload app.py
```

Then open the local link printed in the terminal, usually:

```text
http://127.0.0.1:8000
```

On Windows, activate the environment with:

```bash
.venv\Scripts\activate
```

## How To Use

1. Upload the provisioning workbook.
2. Upload the metadata CSV.
3. Upload the adult transmitter workbook if you want Question 4.
4. Check the validation messages.
5. Click **Run analysis**.
6. Review the tabs.
7. Use the download buttons to save the result tables.

## Important Notes

- Raw data files are not included in this GitHub bundle.
- The app does not edit the uploaded raw files.
- Zero-delivery monitored nest-stints are included in the rate calculations.
- Tagged-parent matching uses the corrected TELEM/NT logic:
  - known transmitter PFR code = tagged parent;
  - `NT`, `NOT TELEM`, `NO TELEM`, `NON TELEM` = untagged parent;
  - exact `TELEM` or `TELE ADULT` = generic tagged-parent label;
  - blank or unreadable adult ID = unknown;
  - unresolved labels = ambiguous review.

## Folder Structure

```text
app.py                  Shiny dashboard
analysis/               Reusable analysis code
scripts/clean_data.py   Cleaning logic
data/raw/               Optional place to store local raw files
docs/                   Longer implementation notes
requirements.txt        Python packages
```

## Troubleshooting

If package installation is slow or fails, try:

```bash
python -m pip install -r requirements.txt --no-cache-dir
```

If the app does not start, recreate the environment with Python 3.11 or 3.12.

