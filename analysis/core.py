"""End-to-end provisioning analysis orchestration."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from scripts.clean_data import CleanedTables, clean_all

from .statistics import summarize_metric
from .tagged_parents import analyze_tagged_parent_rates


UNKNOWN_PREY_CATEGORIES = {"U", "UNKNOWN", "OTHER"}


@dataclass
class AnalysisResults:
    cleaned: CleanedTables
    tables: dict[str, pd.DataFrame]


def analyze_prey_delivery_rate(stints: pd.DataFrame) -> dict[str, pd.DataFrame]:
    valid = stints[stints["valid_observation_duration"]].copy()
    summary, outliers = summarize_metric(valid, ["year", "species"], "prey_deliveries_per_hour")
    return {
        "prey_delivered_per_hour_summary": summary,
        "prey_delivered_per_hour_outliers": outliers,
    }


def analyze_diet_composition(
    deliveries: pd.DataFrame,
    label: str,
    identified_fish_only: bool,
) -> dict[str, pd.DataFrame]:
    events = deliveries.copy()
    if identified_fish_only:
        events = events[
            events["is_fish"].astype(str).str.lower().isin(["true", "1"])
            & ~events["prey_species"].fillna("UNKNOWN").astype(str).str.upper().isin(UNKNOWN_PREY_CATEGORIES)
        ].copy()

    events["prey_species"] = events["prey_species"].fillna("UNKNOWN").astype(str).str.upper()
    diet_counts = (
        events.groupby(["year", "species", "prey_species"], dropna=False)
        .size()
        .rename("prey_count")
        .reset_index()
    )
    if diet_counts.empty:
        summary = pd.DataFrame()
        outliers = pd.DataFrame()
    else:
        diet_counts["total_prey_for_group"] = diet_counts.groupby(["year", "species"])["prey_count"].transform("sum")
        diet_counts["diet_percent"] = diet_counts["prey_count"] / diet_counts["total_prey_for_group"] * 100

        stint_prey_counts = (
            events.groupby(["stint_id", "year", "species", "prey_species"], dropna=False)
            .size()
            .rename("prey_count")
            .reset_index()
        )
        stint_totals = events.groupby(["stint_id"], dropna=False).size().rename("stint_total_prey").reset_index()
        stint_prey_pct = stint_prey_counts.merge(stint_totals, on="stint_id", how="left")
        stint_prey_pct["stint_diet_percent"] = stint_prey_pct["prey_count"] / stint_prey_pct["stint_total_prey"] * 100
        diet_stats, outliers = summarize_metric(
            stint_prey_pct,
            ["year", "species", "prey_species"],
            "stint_diet_percent",
        )
        summary = diet_counts.merge(diet_stats, on=["year", "species", "prey_species"], how="left")
        summary.insert(0, "analysis_set", label)
        if not outliers.empty:
            outliers.insert(0, "analysis_set", label)

    prefix = "question2_identified_fish_only" if identified_fish_only else "question2_all_deliveries"
    return {
        f"{prefix}_diet_composition_percent_summary": summary,
        f"{prefix}_diet_composition_percent_outliers": outliers,
    }


def analyze_fish_delivery_rate(stints: pd.DataFrame) -> dict[str, pd.DataFrame]:
    valid = stints[stints["valid_observation_duration"]].copy()
    fish_hour = valid.copy()
    fish_hour["metric_name"] = "fish_deliveries_per_hour"
    fish_hour["metric_value"] = fish_hour["fish_deliveries_per_hour"]

    chick_valid = stints[stints["valid_observation_duration"] & stints["valid_chick_count"]].copy()
    chick_hour = chick_valid.copy()
    chick_hour["metric_name"] = "fish_deliveries_per_chick_hour"
    chick_hour["metric_value"] = chick_hour["fish_deliveries_per_chick_hour"]

    fish_rates = pd.concat([fish_hour, chick_hour], ignore_index=True)
    summary, outliers = summarize_metric(fish_rates, ["year", "species", "metric_name"], "metric_value")
    return {
        "fish_delivery_rates_summary": summary,
        "fish_delivery_rates_outliers": outliers,
        "fish_delivery_rates_long": fish_rates,
    }


def build_quality_tables(cleaned: CleanedTables) -> dict[str, pd.DataFrame]:
    stints = cleaned.stints
    quality = pd.DataFrame(cleaned.quality.items(), columns=["metric", "value"])
    excluded = pd.DataFrame(
        {
            "analysis": ["prey delivered per hour", "fish per hour", "fish per chick-hour"],
            "excluded_rows": [
                int((~stints["valid_observation_duration"]).sum()),
                int((~stints["valid_observation_duration"]).sum()),
                int((~(stints["valid_observation_duration"] & stints["valid_chick_count"])).sum()),
            ],
            "reason": [
                "missing or invalid observation duration",
                "missing or invalid observation duration",
                "missing/invalid duration or chick count",
            ],
        }
    )
    return {
        "data_quality_summary": quality,
        "rows_excluded_by_analysis": excluded,
    }


def build_complete_analysis(
    provisioning_workbook: Path,
    metadata_csv: Path,
    transmitter_workbook: Path | None = None,
) -> AnalysisResults:
    cleaned = clean_all(provisioning_workbook, metadata_csv)
    tables: dict[str, pd.DataFrame] = {}
    tables.update(build_quality_tables(cleaned))
    tables.update(analyze_prey_delivery_rate(cleaned.stints))
    tables.update(analyze_diet_composition(cleaned.deliveries, "All deliveries", identified_fish_only=False))
    tables.update(analyze_diet_composition(cleaned.deliveries, "Identified fish only", identified_fish_only=True))
    tables.update(analyze_fish_delivery_rate(cleaned.stints))

    if transmitter_workbook is not None:
        tables.update(analyze_tagged_parent_rates(cleaned.stints, cleaned.deliveries, transmitter_workbook))

    return AnalysisResults(cleaned=cleaned, tables=tables)


def write_result_tables(results: AnalysisResults, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results.cleaned.stints.to_csv(output_dir / "observation_stints_clean.csv", index=False)
    results.cleaned.deliveries.to_csv(output_dir / "prey_deliveries_clean.csv", index=False)
    results.cleaned.records_with_zeros.to_csv(output_dir / "delivery_records_with_zeros.csv", index=False)
    results.cleaned.metadata.to_csv(output_dir / "metadata_clean.csv", index=False)
    results.cleaned.telemetry.to_csv(output_dir / "telemetry_lookup_clean.csv", index=False)
    (output_dir / "data_quality_report.json").write_text(json.dumps(results.cleaned.quality, indent=2), encoding="utf-8")

    for name, table in results.tables.items():
        table.to_csv(output_dir / f"{name}.csv", index=False)


def make_results_zip(results: AnalysisResults) -> bytes:
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        package_dir = tmp_dir / "provisioning_analysis_results"
        write_result_tables(results, package_dir)
        zip_path = shutil.make_archive(str(package_dir), "zip", package_dir)
        return Path(zip_path).read_bytes()

