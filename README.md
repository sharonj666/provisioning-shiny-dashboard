# Provisioning Analysis Dashboard

This Shiny app lets a user upload one or more raw provisioning files and generate the provisioning analysis without writing Python code.

## What The App Does

After you upload the files and click **Run analysis**, the dashboard creates:

- data-quality summary;
- mean prey delivered per hour;
- diet composition summaries;
- fish delivered per hour and fish per chick-hour;
- tagged-parent versus untagged-parent provisioning summaries;
- ambiguous parent-status review table;
- downloadable CSV result package.
- cross-year and cross-species comparisons;
- selectable CSV and PNG figure downloads.

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

1. Choose a single-year, cross-year, or cross-species analysis.
2. Upload one or more provisioning workbooks.
3. Upload the shared metadata CSV.
4. Upload adult transmitter workbooks if you want the tagged-status analysis.
5. Check the validation messages and click **Generate analysis**.
6. Use the global year and species controls to refine the comparison.
7. Review the analysis tabs and choose CSVs or PNG figures from **Downloads**.

For a cross-year comparison, select at least two yearly provisioning workbooks
in the upload dialog. The app combines them for the current browser session and
keeps their observation, stint, and delivery identifiers distinct.

The raw-data worksheet does not need to be named `DATA ENTRY`, and historical
column names may differ. For each workbook, choose the raw-data sheet and
header-row number in the app, then map every required analysis field to the
workbook's raw column. Exact-name columns are preselected automatically, and
the workbook itself does not need to be edited.

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
