"""Clean provisioning data into analysis-ready tables.

The raw workbook stores observation-session fields and prey-delivery fields in
the same rows. This script separates them, expands each watched nest into its
own monitored stint, and creates explicit zero-delivery records for watched
nest-stints with no prey delivery.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


RAW_WORKBOOK = Path("2025 PROVISIONING DATA ENTRY.xlsx")
RAW_METADATA = Path("PROV METADATA(Sheet1).csv")
OUTPUT_DIR = Path("data/cleaned")

PREY_NAME_MAP = {
    "A": "Ammodytes",
    "H": "Herring",
    "BA": "Bay Anchovy",
    "BU": "Butterfish",
    "S": "Silversides",
    "M": "Mackerel",
    "U": "Unknown",
    "UNKNOWN": "Unknown",
    "O": "Other",
    "OTHER": "Other",
}

SESSION_COLUMNS = [
    "date",
    "species",
    "blind",
    "time_start_clean",
    "time_stop_clean",
    "observer",
    "weather",
    "telemetry_nest",
]

DELIVERY_COLUMNS = [
    "time_of_delivery_clean",
    "nest_number",
    "prey1",
    "prey2",
    "prey_size",
    "fate_of_prey",
    "chick_pfr",
    "adult_pfr_or_telem",
    "notes",
    "edit_notes",
]


@dataclass(frozen=True)
class CleanedTables:
    stints: pd.DataFrame
    deliveries: pd.DataFrame
    records_with_zeros: pd.DataFrame
    metadata: pd.DataFrame
    telemetry: pd.DataFrame
    quality: dict


def clean_column_name(value: object) -> str:
    text = str(value).strip().lower()
    text = text.replace("#", " number ")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def clean_text(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    return text if text else pd.NA


def clean_code(value: object) -> object:
    text = clean_text(value)
    if pd.isna(text):
        return pd.NA
    return str(text).upper()


def normalize_prey_name(value: object) -> str:
    """Return a report-ready prey name while preserving unrecognized labels."""
    text = clean_text(value)
    if pd.isna(text):
        return "Unknown"
    cleaned = str(text).strip()
    return PREY_NAME_MAP.get(cleaned.upper(), cleaned)


def normalize_nest(value: object) -> object:
    text = clean_text(value)
    if pd.isna(text):
        return pd.NA
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(text)
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text.upper()


def nest_match_key(value: object) -> object:
    nest = normalize_nest(value)
    if pd.isna(nest):
        return pd.NA
    key = re.sub(r"[^A-Z0-9]", "", str(nest).upper())
    if re.fullmatch(r"R\d+", key):
        return key[1:]
    return key


def parse_time(value: object) -> object:
    text = clean_text(value)
    if pd.isna(text):
        return pd.NA
    if str(text).upper() == "NONE":
        return pd.NA
    parsed = pd.to_datetime(str(text), errors="coerce")
    if pd.isna(parsed):
        return pd.NA
    return parsed.time().isoformat()


def combine_date_time(date_value: object, time_value: object) -> pd.Timestamp:
    if pd.isna(date_value) or pd.isna(time_value):
        return pd.NaT
    return pd.to_datetime(f"{pd.Timestamp(date_value).date()} {time_value}", errors="coerce")


def read_workbook_sheet(workbook: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet_name)
    df.columns = [clean_column_name(col) for col in df.columns]
    return df


def read_metadata(path: Path) -> pd.DataFrame:
    metadata = pd.read_csv(path, header=None, encoding="cp1252")
    max_cols = metadata.shape[1]
    metadata.columns = ["field", "definition"] + [f"allowed_value_{i}" for i in range(1, max_cols - 1)]
    for col in metadata.columns:
        metadata[col] = metadata[col].map(clean_text)
    metadata["field_clean"] = metadata["field"].map(clean_column_name)
    cols = ["field_clean", "field", "definition"] + [col for col in metadata.columns if col.startswith("allowed_value_")]
    return metadata[cols]


def standardize_data_entry(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.insert(0, "source_row_id", range(1, len(df) + 1))

    for col in df.columns:
        if col != "source_row_id" and (df[col].dtype == object or str(df[col].dtype) == "str"):
            df[col] = df[col].map(clean_text)

    for col in ["species", "blind", "prey1", "prey2", "fate_of_prey", "chick_pfr", "adult_pfr_or_telem", "telemetry_nest"]:
        if col in df:
            df[col] = df[col].map(clean_code)

    for col in ["nest_number", "nest1_number", "nest2_number", "nest3_number", "nest4_number", "nest5_number", "nest6_number"]:
        if col in df:
            df[col] = df[col].map(normalize_nest)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = df["date"].dt.year
    df["date"] = df["date"].dt.date

    for col in ["time_of_delivery", "time_start", "time_stop"]:
        df[f"{col}_clean"] = df[col].map(parse_time)

    df["delivery_datetime"] = [combine_date_time(d, t) for d, t in zip(df["date"], df["time_of_delivery_clean"], strict=False)]
    df["session_start_datetime"] = [combine_date_time(d, t) for d, t in zip(df["date"], df["time_start_clean"], strict=False)]
    df["session_stop_datetime"] = [combine_date_time(d, t) for d, t in zip(df["date"], df["time_stop_clean"], strict=False)]

    for col in ["prey_size", "total_number_nests_watched", "total_number_chicks_watched"]:
        if col in df:
            df[f"{col}_numeric"] = pd.to_numeric(df[col], errors="coerce")

    for slot in range(1, 7):
        col = f"number_chicks_{slot}"
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["no_prey_observed_row"] = df["time_of_delivery"].astype("string").str.upper().eq("NONE")
    df["is_delivery_row"] = df["time_of_delivery_clean"].notna()
    return df


def make_session_key(df: pd.DataFrame) -> pd.Series:
    key_cols = [
        "date",
        "species",
        "blind",
        "time_start_clean",
        "time_stop_clean",
        "observer",
    ]
    return df[key_cols].astype("string").fillna("<NA>").agg("|".join, axis=1)


def build_observation_stints(df: pd.DataFrame) -> pd.DataFrame:
    session_df = df.copy()
    session_df["session_key"] = make_session_key(session_df)
    session_base_cols = [
        "session_key",
        "date",
        "year",
        "species",
        "blind",
        "time_start_clean",
        "time_stop_clean",
        "session_start_datetime",
        "session_stop_datetime",
        "observer",
        "weather",
        "telemetry_nest",
        "total_number_nests_watched_numeric",
        "total_number_chicks_watched_numeric",
    ]
    nest_cols = [f"nest{slot}_number" for slot in range(1, 7)]
    chick_cols = [f"number_chicks_{slot}" for slot in range(1, 7)]
    sessions = session_df[session_base_cols + nest_cols + chick_cols].drop_duplicates("session_key").reset_index(drop=True)
    sessions.insert(0, "session_id", range(1, len(sessions) + 1))
    session_id_map = sessions[["session_key", "session_id"]]

    watched_rows = []
    for _, row in session_df.iterrows():
        for slot in range(1, 7):
            nest_id = row.get(f"nest{slot}_number")
            if pd.isna(nest_id):
                continue
            watched_rows.append(
                {
                    "session_key": row["session_key"],
                    "nest_slot": slot,
                    "nest_id": nest_id,
                    "nest_match_key": nest_match_key(nest_id),
                    "chick_count": row.get(f"number_chicks_{slot}"),
                    "source_row_id": row["source_row_id"],
                }
            )

    watched = pd.DataFrame(watched_rows)
    if watched.empty:
        return pd.DataFrame()
    watched = watched.sort_values(["session_key", "nest_match_key", "source_row_id", "nest_slot"])
    watched = watched.drop_duplicates(["session_key", "nest_match_key"], keep="first")

    stint_rows = []
    sessions_for_stints = watched.merge(session_id_map, on="session_key", how="left").merge(
        sessions[
            [
                "session_key",
                "date",
                "year",
                "species",
                "blind",
                "observer",
                "weather",
                "telemetry_nest",
                "time_start_clean",
                "time_stop_clean",
                "session_start_datetime",
                "session_stop_datetime",
                "total_number_nests_watched_numeric",
                "total_number_chicks_watched_numeric",
            ]
        ],
        on="session_key",
        how="left",
    )
    for _, row in sessions_for_stints.iterrows():
        stint_rows.append(
            {
                "session_id": row["session_id"],
                "session_key": row["session_key"],
                "nest_slot": row["nest_slot"],
                "nest_id": row["nest_id"],
                "chick_count": row["chick_count"],
                "date": row["date"],
                "year": row["year"],
                "species": row["species"],
                "blind": row["blind"],
                "observer": row["observer"],
                "weather": row["weather"],
                "telemetry_nest": row["telemetry_nest"],
                "time_start": row["time_start_clean"],
                "time_stop": row["time_stop_clean"],
                "session_start_datetime": row["session_start_datetime"],
                "session_stop_datetime": row["session_stop_datetime"],
                "total_nests_watched_reported": row["total_number_nests_watched_numeric"],
                "total_chicks_watched_reported": row["total_number_chicks_watched_numeric"],
            }
        )

    stints = pd.DataFrame(stint_rows)
    stints.insert(0, "stint_id", [f"ST{idx:05d}" for idx in range(1, len(stints) + 1)])
    stints["nest_match_key"] = stints["nest_id"].map(nest_match_key)
    stints["observation_hours"] = (
        pd.to_datetime(stints["session_stop_datetime"]) - pd.to_datetime(stints["session_start_datetime"])
    ).dt.total_seconds() / 3600
    stints["valid_observation_duration"] = stints["observation_hours"].gt(0)
    stints["valid_chick_count"] = stints["chick_count"].notna() & stints["chick_count"].gt(0)
    return stints


def classify_fish(prey1: object, prey2: object) -> bool:
    prey1_text = "" if pd.isna(prey1) else str(prey1).strip().upper()
    prey2_text = "" if pd.isna(prey2) else str(prey2).strip().upper()
    if prey1_text in {"F", "FNA"}:
        return True
    if prey1_text == "NF":
        return False
    return bool(prey2_text and prey2_text not in {"U", "UNKNOWN", "OTHER"})


def build_deliveries(df: pd.DataFrame, stints: pd.DataFrame) -> pd.DataFrame:
    keyed = df.copy()
    keyed["session_key"] = make_session_key(keyed)
    deliveries = keyed[keyed["is_delivery_row"]].copy()
    deliveries = deliveries[
        ["source_row_id", "session_key", "year", "date", "species", "blind", "observer", "delivery_datetime"]
        + DELIVERY_COLUMNS
    ]
    deliveries["nest_id"] = deliveries["nest_number"].map(normalize_nest)
    deliveries["nest_match_key"] = deliveries["nest_id"].map(nest_match_key)
    deliveries["prey_size_numeric"] = pd.to_numeric(deliveries["prey_size"], errors="coerce")
    deliveries["is_fish"] = [classify_fish(a, b) for a, b in zip(deliveries["prey1"], deliveries["prey2"], strict=False)]
    deliveries["prey_species"] = deliveries["prey2"].map(normalize_prey_name)
    deliveries["delivery_count"] = 1

    stint_key = stints[["stint_id", "session_id", "session_key", "nest_match_key", "chick_count", "observation_hours"]]
    deliveries = deliveries.merge(stint_key, on=["session_key", "nest_match_key"], how="left")
    deliveries.insert(0, "delivery_id", [f"DL{idx:05d}" for idx in range(1, len(deliveries) + 1)])
    return deliveries


def build_records_with_zeros(stints: pd.DataFrame, deliveries: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = (
        deliveries.groupby("stint_id", dropna=False)
        .agg(prey_deliveries=("delivery_count", "sum"), fish_deliveries=("is_fish", "sum"))
        .reset_index()
    )
    stints_with_counts = stints.merge(counts, on="stint_id", how="left")
    stints_with_counts[["prey_deliveries", "fish_deliveries"]] = stints_with_counts[
        ["prey_deliveries", "fish_deliveries"]
    ].fillna(0)
    stints_with_counts["prey_deliveries_per_hour"] = np.where(
        stints_with_counts["valid_observation_duration"],
        stints_with_counts["prey_deliveries"] / stints_with_counts["observation_hours"],
        np.nan,
    )
    stints_with_counts["fish_deliveries_per_hour"] = np.where(
        stints_with_counts["valid_observation_duration"],
        stints_with_counts["fish_deliveries"] / stints_with_counts["observation_hours"],
        np.nan,
    )
    stints_with_counts["fish_deliveries_per_chick_hour"] = np.where(
        stints_with_counts["valid_observation_duration"] & stints_with_counts["valid_chick_count"],
        stints_with_counts["fish_deliveries"] / (stints_with_counts["observation_hours"] * stints_with_counts["chick_count"]),
        np.nan,
    )
    stints_with_counts["zero_delivery_stint"] = stints_with_counts["prey_deliveries"].eq(0)

    delivery_records = deliveries.copy()
    delivery_records["record_type"] = "observed_delivery"
    zero_stints = stints_with_counts[stints_with_counts["zero_delivery_stint"]].copy()
    zero_records = zero_stints[
        [
            "stint_id",
            "session_id",
            "session_key",
            "nest_id",
            "date",
            "year",
            "species",
            "blind",
            "observer",
            "chick_count",
            "observation_hours",
        ]
    ].copy()
    zero_records.insert(0, "delivery_id", [f"ZERO{idx:05d}" for idx in range(1, len(zero_records) + 1)])
    zero_records["source_row_id"] = pd.NA
    zero_records["delivery_datetime"] = pd.NaT
    zero_records["time_of_delivery_clean"] = pd.NA
    zero_records["nest_number"] = zero_records["nest_id"]
    zero_records["prey1"] = pd.NA
    zero_records["prey2"] = pd.NA
    zero_records["prey_size"] = pd.NA
    zero_records["prey_size_numeric"] = np.nan
    zero_records["fate_of_prey"] = pd.NA
    zero_records["chick_pfr"] = pd.NA
    zero_records["adult_pfr_or_telem"] = pd.NA
    zero_records["notes"] = "Monitored stint with zero prey deliveries"
    zero_records["edit_notes"] = pd.NA
    zero_records["is_fish"] = False
    zero_records["prey_species"] = pd.NA
    zero_records["delivery_count"] = 0
    zero_records["record_type"] = "zero_delivery_stint"

    all_cols = list(dict.fromkeys(list(delivery_records.columns) + list(zero_records.columns)))
    records_with_zeros = pd.concat(
        [delivery_records.reindex(columns=all_cols), zero_records.reindex(columns=all_cols)],
        ignore_index=True,
    )
    return stints_with_counts, records_with_zeros


def clean_telemetry(raw: pd.DataFrame) -> pd.DataFrame:
    telemetry = raw.copy()
    for col in telemetry.columns:
        if telemetry[col].dtype == object or str(telemetry[col].dtype) == "str":
            telemetry[col] = telemetry[col].map(clean_text)
    for col in ["species", "plot", "pfr_color", "pfr_code", "tag_type"]:
        if col in telemetry:
            telemetry[col] = telemetry[col].map(clean_code)
    for col in ["nest_number"]:
        if col in telemetry:
            telemetry[col] = telemetry[col].map(normalize_nest)
    for col in ["date", "date_originally_banded"]:
        if col in telemetry:
            telemetry[col] = pd.to_datetime(telemetry[col], errors="coerce").dt.date
    for col in ["capture_time", "release_time", "processing_time"]:
        if col in telemetry:
            telemetry[f"{col}_clean"] = telemetry[col].map(parse_time)
    return telemetry


def quality_report(stints: pd.DataFrame, deliveries: pd.DataFrame, raw_rows: pd.DataFrame) -> dict:
    unmatched = int(deliveries["stint_id"].isna().sum())
    return {
        "raw_event_rows": int(len(raw_rows)),
        "observation_stints": int(len(stints)),
        "prey_delivery_records": int(len(deliveries)),
        "zero_delivery_stints": int(stints["zero_delivery_stint"].sum()),
        "missing_or_invalid_start_stop": int((~stints["valid_observation_duration"]).sum()),
        "missing_chick_counts": int(stints["chick_count"].isna().sum()),
        "missing_or_unknown_prey_species": int(
            deliveries["prey_species"].isna().sum()
            + deliveries["prey_species"].astype("string").str.casefold().eq("unknown").sum()
        ),
        "delivery_rows_not_matched_to_stint": unmatched,
        "rows_excluded_from_rate_calculations": int((~stints["valid_observation_duration"]).sum()),
        "rows_excluded_from_chick_corrected_rates": int((~(stints["valid_observation_duration"] & stints["valid_chick_count"])).sum()),
    }


def write_tables(tables: CleanedTables, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables.stints.to_csv(output_dir / "observation_stints_clean.csv", index=False)
    tables.deliveries.to_csv(output_dir / "prey_deliveries_clean.csv", index=False)
    tables.records_with_zeros.to_csv(output_dir / "delivery_records_with_zeros.csv", index=False)
    tables.metadata.to_csv(output_dir / "metadata_clean.csv", index=False)
    tables.telemetry.to_csv(output_dir / "telemetry_lookup_clean.csv", index=False)
    (output_dir / "data_quality_report.json").write_text(json.dumps(tables.quality, indent=2), encoding="utf-8")


def clean_all(workbook: Path, metadata_path: Path) -> CleanedTables:
    data_entry = standardize_data_entry(read_workbook_sheet(workbook, "DATA ENTRY"))
    stints = build_observation_stints(data_entry)
    deliveries = build_deliveries(data_entry, stints)
    stints, records_with_zeros = build_records_with_zeros(stints, deliveries)
    metadata = read_metadata(metadata_path)
    workbook_sheets = pd.ExcelFile(workbook).sheet_names
    telemetry = (
        clean_telemetry(read_workbook_sheet(workbook, "telem Banding for Lookup"))
        if "telem Banding for Lookup" in workbook_sheets
        else pd.DataFrame()
    )
    quality = quality_report(stints, deliveries, data_entry)
    return CleanedTables(stints, deliveries, records_with_zeros, metadata, telemetry, quality)


def _source_scoped_table(
    table: pd.DataFrame,
    source_name: str,
    source_index: int,
) -> pd.DataFrame:
    scoped = table.copy()
    prefix = f"SRC{source_index:03d}"
    scoped.insert(0, "source_workbook", source_name)
    for column in ["session_id", "session_key", "stint_id", "delivery_id"]:
        if column in scoped:
            scoped[column] = scoped[column].map(
                lambda value: value
                if pd.isna(value)
                else f"{prefix}-{value}"
            )
    return scoped


def clean_all_workbooks(
    workbooks: Iterable[Path],
    metadata_path: Path,
    source_names: Iterable[str] | None = None,
) -> CleanedTables:
    """Clean and safely combine one or more provisioning workbooks."""
    workbook_list = list(workbooks)
    if not workbook_list:
        raise ValueError("At least one provisioning workbook is required.")
    names = list(source_names or [path.name for path in workbook_list])
    if len(names) != len(workbook_list):
        raise ValueError("Each provisioning workbook must have one source name.")

    cleaned_sets = [clean_all(path, metadata_path) for path in workbook_list]
    stints = pd.concat(
        [
            _source_scoped_table(cleaned.stints, names[index], index + 1)
            for index, cleaned in enumerate(cleaned_sets)
        ],
        ignore_index=True,
    )
    deliveries = pd.concat(
        [
            _source_scoped_table(cleaned.deliveries, names[index], index + 1)
            for index, cleaned in enumerate(cleaned_sets)
        ],
        ignore_index=True,
    )
    records_with_zeros = pd.concat(
        [
            _source_scoped_table(cleaned.records_with_zeros, names[index], index + 1)
            for index, cleaned in enumerate(cleaned_sets)
        ],
        ignore_index=True,
    )
    telemetry_frames = []
    for index, cleaned in enumerate(cleaned_sets):
        telemetry = cleaned.telemetry.copy()
        telemetry.insert(0, "source_workbook", names[index])
        telemetry_frames.append(telemetry)

    quality_keys = set().union(*(cleaned.quality for cleaned in cleaned_sets))
    quality = {
        key: sum(int(cleaned.quality.get(key, 0)) for cleaned in cleaned_sets)
        for key in sorted(quality_keys)
    }
    quality["source_workbooks"] = len(workbook_list)

    return CleanedTables(
        stints=stints,
        deliveries=deliveries,
        records_with_zeros=records_with_zeros,
        metadata=cleaned_sets[0].metadata.copy(),
        telemetry=pd.concat(telemetry_frames, ignore_index=True),
        quality=quality,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean provisioning data for analysis.")
    parser.add_argument("--workbook", type=Path, default=RAW_WORKBOOK)
    parser.add_argument("--metadata", type=Path, default=RAW_METADATA)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    tables = clean_all(args.workbook, args.metadata)
    write_tables(tables, args.output_dir)
    print(json.dumps(tables.quality, indent=2))


if __name__ == "__main__":
    main()
