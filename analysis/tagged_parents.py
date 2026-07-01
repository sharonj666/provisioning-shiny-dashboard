"""Tagged-parent matching and provisioning-rate analysis."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .statistics import summarize_metric


UNTAGGED_LABELS = {"NT", "NOT TELEM", "NO TELEM", "NON TELEM"}
TELEM_LABELS = {"TELEM", "TELE ADULT"}
UNKNOWN_LABELS = {"U", "UNKNOWN", "COULDN'T READ ADULT PFR"}


def normalize_code(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().upper()
    if not text:
        return pd.NA
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text


def nest_match_key(value: object) -> object:
    text = normalize_code(value)
    if pd.isna(text):
        return pd.NA
    key = re.sub(r"[^A-Z0-9]", "", str(text))
    if re.fullmatch(r"R\d+", key):
        return key[1:]
    return key


def _clean_transmitter_columns(columns: pd.Index) -> list[str]:
    return [
        str(col).strip().lower().replace("#", "number").replace(" ", "_").replace(".", "_")
        for col in columns
    ]


def read_adult_transmitter_lookup(transmitter_path: Path) -> pd.DataFrame:
    """Read and normalize the standalone adult transmitter workbook."""
    raw = pd.read_excel(transmitter_path, sheet_name="Sheet1")
    raw.columns = _clean_transmitter_columns(raw.columns)

    required = {"date", "species", "nestnumber", "pfr_code"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Adult transmitter file is missing required columns: {', '.join(missing)}")

    adult = raw.copy()
    adult["date"] = pd.to_datetime(adult["date"], errors="coerce")
    adult["year"] = adult["date"].dt.year
    adult["species_norm"] = adult["species"].map(normalize_code)
    adult["nest_match_key"] = adult["nestnumber"].map(nest_match_key)
    adult["pfr_code_norm"] = adult["pfr_code"].map(normalize_code)
    if "tag_type" in adult:
        adult["tag_type_norm"] = adult["tag_type"].map(normalize_code)
    else:
        adult["tag_type_norm"] = pd.NA

    optional_cols = ["plot", "tagnumber", "tag_type", "first_location_back_at_nest", "time_to_return", "notes_1"]
    for col in optional_cols:
        if col not in adult:
            adult[col] = pd.NA

    return adult[
        [
            "year",
            "species",
            "species_norm",
            "plot",
            "nestnumber",
            "nest_match_key",
            "pfr_code",
            "pfr_code_norm",
            "tagnumber",
            "tag_type",
            "tag_type_norm",
            "first_location_back_at_nest",
            "time_to_return",
            "notes_1",
        ]
    ].copy()


def classify_parent_status_factory(tagged_pfr_codes: set[str]):
    """Return functions that classify adult identity strings against known PFR codes."""

    def extract_pfr_match(adult_value: object) -> object:
        text = normalize_code(adult_value)
        if pd.isna(text):
            return pd.NA
        tokens = re.findall(r"[A-Z0-9]+", str(text))
        for token in tokens:
            if token in tagged_pfr_codes:
                return token
        return pd.NA

    def classify_parent_status(adult_value: object) -> str:
        text = normalize_code(adult_value)
        if pd.isna(text):
            return "unknown_parent_status"
        pfr_match = extract_pfr_match(text)
        if not pd.isna(pfr_match):
            return "tagged_parent_direct_pfr"
        if text in UNTAGGED_LABELS:
            return "untagged_parent"
        if text in TELEM_LABELS:
            return "tagged_parent_telem_label"
        if text in UNKNOWN_LABELS:
            return "unknown_parent_status"
        return "ambiguous_parent_status"

    return extract_pfr_match, classify_parent_status


def analyze_tagged_parent_rates(
    stints: pd.DataFrame,
    deliveries: pd.DataFrame,
    transmitter_path: Path,
) -> dict[str, pd.DataFrame]:
    adult_lookup = read_adult_transmitter_lookup(transmitter_path)
    tagged_nest_keys = set(
        adult_lookup[["species_norm", "year", "nest_match_key"]]
        .dropna()
        .itertuples(index=False, name=None)
    )

    stints_tagged = stints.copy()
    stints_tagged["species_norm"] = stints_tagged["species"].map(normalize_code)
    stints_tagged["nest_match_key"] = stints_tagged["nest_id"].map(nest_match_key)
    stints_tagged["tagged_nest"] = [
        (species, year, nest) in tagged_nest_keys
        for species, year, nest in zip(
            stints_tagged["species_norm"],
            stints_tagged["year"],
            stints_tagged["nest_match_key"],
            strict=False,
        )
    ]

    tagged_nest_rates = stints_tagged[stints_tagged["valid_observation_duration"]].copy()
    tagged_nest_summary, tagged_nest_outliers = summarize_metric(
        tagged_nest_rates,
        ["year", "species", "tagged_nest"],
        "prey_deliveries_per_hour",
    )

    tagged_pfr_codes = set(adult_lookup["pfr_code_norm"].dropna())
    extract_pfr_match, classify_parent_status = classify_parent_status_factory(tagged_pfr_codes)

    deliveries_tagged = deliveries.copy()
    deliveries_tagged["adult_id_norm"] = deliveries_tagged["adult_pfr_or_telem"].map(normalize_code)
    deliveries_tagged["matched_tagged_pfr_code"] = deliveries_tagged["adult_pfr_or_telem"].map(extract_pfr_match)
    deliveries_tagged["parent_tag_status"] = deliveries_tagged["adult_pfr_or_telem"].map(classify_parent_status)

    status_for_parent_comparison = {
        "tagged_parent_direct_pfr": "tagged_parent",
        "tagged_parent_telem_label": "tagged_parent",
        "untagged_parent": "untagged_parent",
    }
    stint_context = stints_tagged[
        [
            "stint_id",
            "year",
            "species",
            "nest_id",
            "tagged_nest",
            "observation_hours",
            "valid_observation_duration",
        ]
    ].copy()
    classified_deliveries = deliveries_tagged.merge(
        stint_context.drop(columns=["year", "species", "nest_id"]),
        on="stint_id",
        how="left",
        suffixes=("", "_stint"),
    )
    classified_deliveries["parent_rate_group"] = classified_deliveries["parent_tag_status"].map(
        status_for_parent_comparison
    )

    unknown_or_ambiguous = classified_deliveries[classified_deliveries["parent_rate_group"].isna()].copy()
    ambiguous_parent_status = classified_deliveries[
        classified_deliveries["parent_tag_status"].eq("ambiguous_parent_status")
    ].copy()
    ambiguous_columns = [
        "delivery_id",
        "source_row_id",
        "date",
        "year",
        "species",
        "nest_id",
        "stint_id",
        "tagged_nest",
        "adult_pfr_or_telem",
        "adult_id_norm",
        "matched_tagged_pfr_code",
        "parent_tag_status",
        "notes",
    ]
    ambiguous_parent_status = ambiguous_parent_status[
        [col for col in ambiguous_columns if col in ambiguous_parent_status.columns]
    ].sort_values([col for col in ["date", "species", "nest_id", "delivery_id"] if col in ambiguous_parent_status.columns])

    parent_counts = (
        classified_deliveries[
            classified_deliveries["tagged_nest"].eq(True)
            & classified_deliveries["valid_observation_duration"].eq(True)
            & classified_deliveries["parent_rate_group"].notna()
        ]
        .groupby(["stint_id", "parent_rate_group"])
        .size()
        .rename("deliveries")
        .reset_index()
    )
    base_tagged_stints = stint_context[
        stint_context["tagged_nest"].eq(True) & stint_context["valid_observation_duration"].eq(True)
    ].copy()

    parent_rate_rows = []
    for parent_group in ["tagged_parent", "untagged_parent"]:
        tmp = base_tagged_stints.copy()
        tmp["parent_rate_group"] = parent_group
        parent_rate_rows.append(tmp)
    parent_rates = pd.concat(parent_rate_rows, ignore_index=True) if parent_rate_rows else pd.DataFrame()
    parent_rates = parent_rates.merge(parent_counts, on=["stint_id", "parent_rate_group"], how="left")
    parent_rates["deliveries"] = parent_rates["deliveries"].fillna(0)
    parent_rates["deliveries_per_hour"] = parent_rates["deliveries"] / parent_rates["observation_hours"]
    parent_summary, parent_outliers = summarize_metric(
        parent_rates,
        ["year", "species", "parent_rate_group"],
        "deliveries_per_hour",
    )

    quality = pd.DataFrame(
        {
            "metric": [
                "adult transmitter rows",
                "unique tagged adult PFR codes",
                "unique tagged nest keys",
                "valid observation stints",
                "tagged nest stints",
                "untagged nest stints",
                "delivery rows",
                "direct tagged PFR delivery rows",
                "generic TELEM delivery rows",
                "untagged/NT delivery rows",
                "unknown or ambiguous adult delivery rows",
            ],
            "value": [
                len(adult_lookup),
                adult_lookup["pfr_code_norm"].nunique(),
                adult_lookup[["species_norm", "year", "nest_match_key"]].drop_duplicates().shape[0],
                int(tagged_nest_rates.shape[0]),
                int(tagged_nest_rates["tagged_nest"].sum()),
                int((~tagged_nest_rates["tagged_nest"]).sum()),
                int(deliveries_tagged.shape[0]),
                int(deliveries_tagged["parent_tag_status"].eq("tagged_parent_direct_pfr").sum()),
                int(deliveries_tagged["parent_tag_status"].eq("tagged_parent_telem_label").sum()),
                int(deliveries_tagged["parent_tag_status"].eq("untagged_parent").sum()),
                int(
                    deliveries_tagged["parent_tag_status"]
                    .isin(["unknown_parent_status", "ambiguous_parent_status"])
                    .sum()
                ),
            ],
        }
    )

    return {
        "adult_transmitter_lookup": adult_lookup,
        "tagged_parent_observation_stints": stints_tagged,
        "tagged_vs_untagged_nest_feeding_rates_summary": tagged_nest_summary,
        "tagged_vs_untagged_nest_feeding_rates_outliers": tagged_nest_outliers,
        "tagged_parent_delivery_classifications": deliveries_tagged,
        "tagged_parent_unknown_or_ambiguous_delivery_ids": unknown_or_ambiguous,
        "tagged_parent_ambiguous_parent_status_review": ambiguous_parent_status,
        "tagged_nest_parent_level_delivery_rates": parent_rates,
        "tagged_parent_vs_untagged_parent_rates_summary": parent_summary,
        "tagged_parent_vs_untagged_parent_rates_outliers": parent_outliers,
        "tagged_parent_analysis_quality_summary": quality,
    }

