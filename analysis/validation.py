"""Input validation for the Shiny upload workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.clean_data import (
    PROVISIONING_REQUIRED_COLUMNS,
    WorkbookSheetSelection,
    clean_column_name,
    detect_provisioning_sheet,
)


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


def validate_inputs(
    provisioning_workbook: Path | None,
    metadata_csv: Path | None,
    transmitter_workbook: Path | None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if provisioning_workbook is None:
        errors.append("Upload the provisioning workbook.")
    if metadata_csv is None:
        errors.append("Upload the provisioning metadata CSV.")
    if transmitter_workbook is None:
        warnings.append("Adult transmitter file was not uploaded. Question 4 will not run.")

    if provisioning_workbook is not None:
        _validate_provisioning_workbook(provisioning_workbook, errors, warnings)
    if metadata_csv is not None:
        _validate_metadata_csv(metadata_csv, errors)
    if transmitter_workbook is not None:
        _validate_transmitter_workbook(transmitter_workbook, errors, warnings)

    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def validate_multiple_inputs(
    provisioning_workbooks: list[Path],
    metadata_csv: Path | None,
    transmitter_workbooks: list[Path],
    provisioning_names: list[str] | None = None,
    transmitter_names: list[str] | None = None,
    sheet_selections: list[WorkbookSheetSelection | None] | None = None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    provisioning_names = provisioning_names or [path.name for path in provisioning_workbooks]
    transmitter_names = transmitter_names or [path.name for path in transmitter_workbooks]
    selections = sheet_selections or [None] * len(provisioning_workbooks)

    if not provisioning_workbooks:
        errors.append("Upload at least one provisioning workbook.")
    if metadata_csv is None:
        errors.append("Upload the provisioning metadata CSV.")
    if not transmitter_workbooks:
        warnings.append("Adult transmitter files were not uploaded. Feeding-rate-by-tagged-status analysis will not run.")

    for index, (path, name) in enumerate(
        zip(provisioning_workbooks, provisioning_names, strict=False)
    ):
        local_errors: list[str] = []
        local_warnings: list[str] = []
        selection = selections[index] if index < len(selections) else None
        _validate_provisioning_workbook(
            path,
            local_errors,
            local_warnings,
            sheet_selection=selection,
        )
        errors.extend(f"{name}: {message}" for message in local_errors)
        warnings.extend(f"{name}: {message}" for message in local_warnings)
    if metadata_csv is not None:
        _validate_metadata_csv(metadata_csv, errors)
    for path, name in zip(transmitter_workbooks, transmitter_names, strict=False):
        local_errors = []
        local_warnings = []
        _validate_transmitter_workbook(path, local_errors, local_warnings)
        errors.extend(f"{name}: {message}" for message in local_errors)
        warnings.extend(f"{name}: {message}" for message in local_warnings)

    duplicate_provisioning = sorted(
        {name for name in provisioning_names if provisioning_names.count(name) > 1}
    )
    if duplicate_provisioning:
        warnings.append(
            "Duplicate provisioning filenames were uploaded: "
            + ", ".join(duplicate_provisioning)
        )

    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def _validate_provisioning_workbook(
    path: Path,
    errors: list[str],
    warnings: list[str],
    sheet_selection: WorkbookSheetSelection | None = None,
) -> None:
    if path.suffix.lower() != ".xlsx":
        errors.append("Provisioning workbook must be an .xlsx file.")
        return
    try:
        with pd.ExcelFile(path) as workbook:
            sheet_names = list(workbook.sheet_names)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not open provisioning workbook: {exc}")
        return
    if "telem Banding for Lookup" not in sheet_names:
        warnings.append("Provisioning workbook is missing telem Banding for Lookup.")

    if sheet_selection is None:
        detected = detect_provisioning_sheet(path)
        if detected.recommended is None:
            if detected.candidates:
                closest = detected.candidates[0]
                errors.append(
                    f"Could not identify the provisioning data sheet. Closest "
                    f"candidate is '{closest.sheet_name}' at header row "
                    f"{closest.header_row + 1}; missing: "
                    f"{', '.join(closest.missing_required)}."
                )
            else:
                errors.append(
                    "Could not identify a provisioning data sheet or header row."
                )
            return
        sheet_selection = detected.recommended.selection()
    if sheet_selection.sheet_name not in sheet_names:
        errors.append(
            f"Selected data sheet '{sheet_selection.sheet_name}' was not found."
        )
        return
    data = pd.read_excel(
        path,
        sheet_name=sheet_selection.sheet_name,
        header=sheet_selection.header_row,
        nrows=5,
    )
    present = {clean_column_name(col) for col in data.columns}
    missing = sorted(PROVISIONING_REQUIRED_COLUMNS - present)
    if missing:
        errors.append(
            f"{sheet_selection.sheet_name} (header row "
            f"{sheet_selection.header_row + 1}) is missing required columns: "
            f"{', '.join(missing)}"
        )
    if not any(col.startswith("NEST1") for col in present):
        if "nest1_number" not in present:
            warnings.append(
                f"{sheet_selection.sheet_name} does not appear to contain "
                "watched-nest columns such as NEST1 #."
            )


def _validate_metadata_csv(path: Path, errors: list[str]) -> None:
    if path.suffix.lower() != ".csv":
        errors.append("Metadata file must be a .csv file.")
        return
    try:
        df = pd.read_csv(path, header=None, encoding="cp1252", nrows=5)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not read metadata CSV: {exc}")
        return
    if df.empty:
        errors.append("Metadata CSV appears to be empty.")


def _validate_transmitter_workbook(path: Path, errors: list[str], warnings: list[str]) -> None:
    if path.suffix.lower() != ".xlsx":
        errors.append("Adult transmitter file must be an .xlsx file.")
        return
    try:
        with pd.ExcelFile(path) as workbook:
            sheet_names = list(workbook.sheet_names)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not open adult transmitter workbook: {exc}")
        return
    if "Sheet1" not in sheet_names:
        errors.append("Adult transmitter workbook is missing Sheet1.")
        return
    data = pd.read_excel(path, sheet_name="Sheet1", nrows=10)
    cleaned_cols = {
        str(col).strip().lower().replace("#", "number").replace(" ", "_").replace(".", "_")
        for col in data.columns
    }
    required = {"date", "species", "nestnumber", "pfr_code"}
    missing = sorted(required - cleaned_cols)
    if missing:
        errors.append(f"Adult transmitter Sheet1 is missing required columns: {', '.join(missing)}")
    if data.empty:
        warnings.append("Adult transmitter Sheet1 appears to be empty.")
