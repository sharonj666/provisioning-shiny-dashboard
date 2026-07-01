"""Input validation for the Shiny upload workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


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


def _validate_provisioning_workbook(path: Path, errors: list[str], warnings: list[str]) -> None:
    if path.suffix.lower() != ".xlsx":
        errors.append("Provisioning workbook must be an .xlsx file.")
        return
    try:
        workbook = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not open provisioning workbook: {exc}")
        return
    if "DATA ENTRY" not in workbook.sheet_names:
        errors.append("Provisioning workbook is missing the DATA ENTRY sheet.")
        return
    if "telem Banding for Lookup" not in workbook.sheet_names:
        warnings.append("Provisioning workbook is missing telem Banding for Lookup.")

    data = pd.read_excel(path, sheet_name="DATA ENTRY", nrows=5)
    required = {
        "DATE",
        "SPECIES",
        "BLIND",
        "TIME START",
        "TIME STOP",
        "TIME OF DELIVERY",
        "NEST #",
        "PREY1",
        "PREY2",
    }
    present = {str(col).strip().upper() for col in data.columns}
    missing = sorted(required - present)
    if missing:
        errors.append(f"DATA ENTRY is missing required columns: {', '.join(missing)}")
    if not any(col.startswith("NEST1") for col in present):
        warnings.append("DATA ENTRY does not appear to contain watched-nest columns such as NEST1 #.")


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
        workbook = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not open adult transmitter workbook: {exc}")
        return
    if "Sheet1" not in workbook.sheet_names:
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

