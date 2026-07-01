# Shiny Dashboard Guide for the Provisioning Analysis

## Current Implementation

The first Shiny implementation has been added to:

```text
app.py
analysis/
```

It includes:

- upload controls for the provisioning workbook, metadata CSV, and adult transmitter workbook;
- validation for required sheets and columns;
- one-click analysis execution;
- data-quality tables;
- dashboard tabs for Questions 1-4;
- tagged-parent classification using the corrected TELEM/NT logic;
- an ambiguous-parent review table;
- downloads for all result tables and the ambiguous-parent review CSV.

Run locally with:

```bash
source .venv/bin/activate
shiny run --reload app.py
```

If Shiny or Pandas imports hang, recreate the virtual environment with the versions in `requirements.txt`.

## Goal

Build a Shiny for Python dashboard that lets a nontechnical user:

1. Upload raw provisioning data.
2. Upload metadata and adult transmitter data.
3. Validate the files before analysis.
4. Click **Run analysis**.
5. Review data-quality warnings, tables, and charts.
6. Download cleaned data and a report package without editing Python code.

The dashboard should reuse the validated cleaning and analysis rules already developed in:

- `scripts/clean_data.py`
- `notebooks/provisioning_report.ipynb`

The notebook remains useful for scientific exploration, but the production dashboard should call reusable Python functions directly rather than execute the notebook.

## Recommended Approach

Use **Shiny Core for Python**.

Shiny Core is preferable here because the application will have:

- Three coordinated file uploads.
- A **Run analysis** button.
- File and schema validation.
- Several analysis tabs.
- Download handlers.
- Error and warning messages.
- Session-specific temporary files.

Suggested user workflow:

```text
Upload files
    ↓
Validate files
    ↓
Show errors or warnings
    ↓
Run cleaning and analysis
    ↓
Display results
    ↓
Download tables, figures, and review files
```

## Do Not Build the Dashboard Directly From the Notebook

The notebook currently combines:

- data cleaning;
- calculations;
- table export;
- chart generation;
- explanatory text.

That is convenient for research, but a web application should separate these responsibilities.

Recommended structure:

```text
app.py
analysis/
    __init__.py
    cleaning.py
    validation.py
    statistics.py
    tagged_parents.py
    charts.py
scripts/
    clean_data.py
notebooks/
    provisioning_report.ipynb
tests/
    test_cleaning.py
    test_statistics.py
    test_tag_matching.py
requirements.txt
```

The notebook and Shiny app should import the same functions from `analysis/`. This prevents the dashboard and notebook from producing different answers.

## Phase 1: Refactor the Existing Analysis

Before building the user interface, move the scientific calculations into reusable functions.

### Cleaning functions

Reuse the current functions from `scripts/clean_data.py`, especially:

```python
clean_all(workbook, metadata_path)
build_observation_stints(data)
build_deliveries(data, stints)
build_records_with_zeros(stints, deliveries)
```

Modify the cleaning API so it can accept uploaded temporary file paths and return DataFrames without requiring fixed project filenames.

Suggested interface:

```python
def clean_uploaded_data(
    provisioning_path: Path,
    metadata_path: Path,
) -> CleanedTables:
    return clean_all(provisioning_path, metadata_path)
```

### Analysis functions

Move each notebook calculation into a named function:

```python
def summarize_metric(df, group_columns, value_column):
    ...


def analyze_prey_delivery_rate(stints):
    ...


def analyze_diet_composition(deliveries, identified_fish_only=False):
    ...


def analyze_fish_delivery_rate(stints):
    ...


def analyze_tagged_parent_rates(stints, deliveries, transmitter_data):
    ...
```

Each function should return DataFrames. It should not write files or display notebook output.

Example:

```python
@dataclass
class QuestionOneResults:
    summary: pd.DataFrame
    outliers: pd.DataFrame
    stint_data: pd.DataFrame
```

This makes the results easy to use in the notebook, dashboard, tests, and downloads.

## Phase 2: Define the Upload Interface

The first version should request three files:

1. Provisioning workbook:
   - `.xlsx`
   - must contain `DATA ENTRY`
   - must contain `telem Banding for Lookup` unless the standalone transmitter file is required
2. Metadata file:
   - `.csv`
3. Adult transmitter file:
   - `.xlsx`
   - must contain `Sheet1`

Suggested Shiny inputs:

```python
ui.input_file(
    "provisioning_file",
    "Provisioning workbook",
    accept=[".xlsx"],
    multiple=False,
)

ui.input_file(
    "metadata_file",
    "Provisioning metadata",
    accept=[".csv"],
    multiple=False,
)

ui.input_file(
    "transmitter_file",
    "Adult transmitter data",
    accept=[".xlsx"],
    multiple=False,
)

ui.input_action_button(
    "run_analysis",
    "Run analysis",
    class_="btn-primary",
)
```

Shiny uploads are temporary files. Read them using the uploaded file's `datapath`, not its original filename.

Example:

```python
uploaded = input.provisioning_file()
if uploaded is None:
    return None

provisioning_path = Path(uploaded[0]["datapath"])
```

Do not assume the uploaded file keeps its original name or remains available after another upload.

## Phase 3: Validate Before Running

Validation should happen before scientific calculations.

### File-level checks

Check:

- all required files were supplied;
- extensions are allowed;
- files can be opened;
- Excel files are not password protected or corrupted;
- file sizes are within an acceptable limit.

### Provisioning workbook checks

Confirm:

- `DATA ENTRY` exists;
- required columns exist;
- dates can be parsed;
- start and stop times are present;
- watched nest columns exist;
- delivery nest and delivery time columns exist;
- prey fields exist;
- adult identity field exists.

### Metadata checks

Confirm:

- the CSV can be decoded;
- expected field-definition columns are present;
- there are no entirely blank files.

### Transmitter checks

Confirm:

- `Sheet1` exists;
- species, nest, and PFR-code columns exist;
- PFR codes are not duplicated unexpectedly;
- missing nest or PFR values are reported;
- species values are compatible with the provisioning data.

### Validation result

Return structured results instead of raising raw errors:

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    details: pd.DataFrame
```

Display errors prominently and prevent analysis from running until blocking errors are resolved.

Warnings should not necessarily block analysis. Examples:

- missing chick counts;
- invalid observation duration;
- unknown prey code;
- ambiguous adult ID;
- tagged PFR observed at a different nest;
- generic `TELEM` at a nest not found in the transmitter lookup.

## Phase 4: Run Analysis Reactively

Analysis should run only after the user clicks **Run analysis**, not every time an upload input changes.

Suggested pattern:

```python
@reactive.calc
@reactive.event(input.run_analysis)
def analysis_results():
    provisioning = input.provisioning_file()
    metadata = input.metadata_file()
    transmitter = input.transmitter_file()

    if provisioning is None or metadata is None or transmitter is None:
        raise ValueError("Upload all required files.")

    cleaned = clean_uploaded_data(
        Path(provisioning[0]["datapath"]),
        Path(metadata[0]["datapath"]),
    )

    tagged_results = analyze_tagged_parent_rates(
        cleaned.stints,
        cleaned.deliveries,
        Path(transmitter[0]["datapath"]),
    )

    return build_complete_analysis(cleaned, tagged_results)
```

Use a single results object so every table and chart is based on the same completed analysis run.

Suggested result structure:

```python
@dataclass
class AnalysisResults:
    cleaned: CleanedTables
    data_quality: pd.DataFrame
    question_1_summary: pd.DataFrame
    question_1_outliers: pd.DataFrame
    question_2_all: pd.DataFrame
    question_2_fish_only: pd.DataFrame
    question_3_summary: pd.DataFrame
    question_3_outliers: pd.DataFrame
    question_4_nest_summary: pd.DataFrame
    question_4_parent_summary: pd.DataFrame
    ambiguous_parent_rows: pd.DataFrame
```

## Phase 5: Dashboard Layout

Recommended navigation:

### 1. Upload and Validate

Show:

- file upload controls;
- selected filenames;
- validation status;
- data year range;
- species detected;
- number of raw rows;
- **Run analysis** button.

### 2. Data Quality

Show:

- observation stint count;
- prey delivery count;
- zero-delivery stint count;
- missing or invalid observation times;
- missing chick counts;
- unknown prey categories;
- unmatched deliveries;
- unknown and ambiguous parent identities.

Use warning banners for issues that materially affect interpretation.

### 3. Question 1: Prey Per Hour

Show:

- summary table;
- mean chart;
- box plot;
- outlier table;
- download buttons.

### 4. Question 2: Diet Composition

Show separate views for:

- all deliveries;
- identified fish only.

Include stacked percentage charts and downloadable summary tables.

### 5. Question 3: Fish Per Chick-Hour

Show:

- fish deliveries per hour;
- fish deliveries per chick-hour;
- summary statistics;
- box plot;
- missing chick-count warning;
- outlier table.

### 6. Question 4: Tagged Parents

Show two distinct analyses:

1. Tagged-parent nest versus untagged-parent nest.
2. Tagged parent versus untagged parent within tagged nests.

Display the classification rules:

```text
Known transmitter PFR code
    → tagged_parent_direct_pfr

NT / NOT TELEM / NO TELEM / NON TELEM
    → untagged_parent

Exact TELEM / TELE ADULT
    → tagged_parent_telem_label

Blank / U / UNKNOWN / unreadable
    → unknown_parent_status

Anything unresolved
    → ambiguous_parent_status
```

Include a separate downloadable ambiguous-parent review table.

### 7. Downloads

Offer:

- cleaned observation stints;
- cleaned prey deliveries;
- data-quality report;
- all summary tables;
- all outlier tables;
- ambiguous parent review table;
- figures;
- a ZIP file containing the complete run.

## Phase 6: Support New and Historical Data

Start with one provisioning workbook per analysis run.

After that works reliably, add multiple-workbook support:

```python
ui.input_file(
    "provisioning_files",
    "Provisioning workbooks",
    accept=[".xlsx"],
    multiple=True,
)
```

For multiple workbooks:

1. Validate each workbook separately.
2. Clean each workbook separately.
3. Add `source_file` to all resulting tables.
4. Combine cleaned tables.
5. Rebuild globally unique IDs.
6. Derive year from each row's date.
7. Check for duplicated observation sessions or deliveries across files.

Do not simply concatenate raw Excel rows. Clean and validate each file first.

Recommended IDs for combined data:

```text
session_id = source_file + normalized session fields
stint_id   = session_id + nest ID
delivery_id = source_file + source row ID
```

This avoids ID collisions when several years are uploaded together.

## Session and Data Safety

Each user's uploaded files and results should remain isolated.

Recommended rules:

- use uploaded `datapath` values only within the current session;
- do not copy uploads into a shared permanent folder by default;
- store generated run files in a session-specific temporary directory;
- delete temporary output after download or session end;
- never reuse a global mutable DataFrame across users;
- do not publish raw field data to a public repository;
- add authentication before deploying sensitive nest or transmitter data publicly.

## Downloads

Use Shiny download handlers for individual CSVs and the complete ZIP package.

CSV example:

```python
@render.download(filename="question_1_summary.csv")
def download_question_1():
    yield analysis_results().question_1_summary.to_csv(index=False)
```

ZIP example:

```python
@render.download(filename="provisioning_analysis.zip")
def download_all():
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        write_analysis_package(analysis_results(), output_dir)
        zip_path = shutil.make_archive(
            str(output_dir / "provisioning_analysis"),
            "zip",
            output_dir,
        )
        yield Path(zip_path).read_bytes()
```

## Error Handling

Do not show raw Python tracebacks to normal users.

Convert common failures into plain-language messages:

```text
The provisioning workbook does not contain a DATA ENTRY sheet.

The DATE column could not be found.

The transmitter file is missing the PFR code column.

No valid observation periods were found.

The uploaded files appear to contain different years or species codes.
```

Save technical details to application logs for troubleshooting.

## Testing Plan

Create a small, de-identified test dataset covering:

- a normal prey delivery;
- a zero-delivery stint;
- multiple watched nests;
- missing observation time;
- missing chick count;
- known fish and non-fish prey;
- unknown prey;
- direct tagged PFR;
- exact `TELEM`;
- `NT` and `NOT TELEM`;
- blank adult ID;
- ambiguous adult ID;
- tagged adult observed at a different nest.

Automated tests should confirm:

- zero-delivery stints remain in rate denominators;
- diet percentages sum to approximately 100%;
- chick-corrected rates require valid chick counts;
- parent-status rules are applied in the correct order;
- dashboard calculations equal notebook calculations;
- uploaded files are not modified;
- generated IDs are unique across multiple files.

## Development Roadmap

### Milestone 1: Minimal working dashboard

- Upload the three files.
- Validate filenames, sheets, and required columns.
- Run the existing cleaning functions.
- Show a data-quality table.
- Show Question 1 table and plot.

### Milestone 2: Complete scientific analysis

- Add Questions 2 and 3.
- Add standard errors, quantiles, and outliers.
- Add CSV downloads.

### Milestone 3: Tagged-parent analysis

- Add transmitter matching.
- Add tagged-nest comparison.
- Add parent-level comparison.
- Add ambiguous-status review.

### Milestone 4: Historical and multi-year data

- Allow multiple provisioning workbooks.
- Add source-file tracking.
- Detect duplicate sessions and deliveries.
- Add year filters.

### Milestone 5: Deployment

- Add authentication if data are sensitive.
- Add file-size limits and logging.
- Test with nontechnical users.
- Deploy only after the validation and scientific regression tests pass.

## Running Locally

During development:

```bash
source .venv/bin/activate
shiny run --reload app.py
```

Then open the local URL printed in the terminal.

The `--reload` option automatically restarts the app after code changes and is intended for development.

## Requirements

Add Shiny to `requirements.txt`:

```text
shiny==1.6.3
```

Keep the existing packages:

```text
pandas
openpyxl
numpy
matplotlib
seaborn
scipy
```

Optional additions:

```text
pytest
pytest-playwright
```

Pin exact versions before deployment after the application is stable.

## Recommended First Implementation

Do not build every feature at once.

The best first version is:

1. Upload provisioning workbook and metadata.
2. Validate required sheets and columns.
3. Run `clean_all()`.
4. Display the data-quality summary.
5. Display the Question 1 table and graph.
6. Download the cleaned stint table and Question 1 summary.

Once that version works with several real files, add the remaining questions one at a time.

## Official Shiny References

- Overview: <https://shiny.posit.co/py/docs/overview.html>
- File uploads: <https://shiny.posit.co/py/api/core/ui.input_file.html>
- Downloads: <https://shiny.posit.co/py/api/core/render.download.html>
