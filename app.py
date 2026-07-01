"""Shiny dashboard for the provisioning analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from shiny import App, reactive, render, ui

from analysis.charts import (
    diet_bar,
    fish_rate_bar,
    prey_rate_box,
    prey_rate_mean,
    tagged_nest_bar,
    tagged_parent_bar,
)
from analysis.core import AnalysisResults, build_complete_analysis, make_results_zip
from analysis.validation import validate_inputs


def uploaded_path(file_info) -> Path | None:
    if not file_info:
        return None
    return Path(file_info[0]["datapath"])


def table_html(df: pd.DataFrame | None, max_rows: int = 100) -> str:
    if df is None or df.empty:
        return "<p>No rows to display.</p>"
    shown = df.head(max_rows).copy()
    return shown.to_html(index=False, classes="table table-striped table-sm", border=0)


def status_box(kind: str, messages: list[str]):
    if not messages:
        return ui.tags.div()
    class_name = "alert alert-danger" if kind == "error" else "alert alert-warning"
    title = "Errors" if kind == "error" else "Warnings"
    return ui.tags.div(
        {"class": class_name},
        ui.tags.strong(title),
        ui.tags.ul(*[ui.tags.li(message) for message in messages]),
    )


app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style(
            """
            body { max-width: 1500px; margin: 0 auto; }
            .table-wrap { overflow-x: auto; max-height: 620px; overflow-y: auto; }
            .metric-note { color: #4b5563; font-size: 0.95rem; }
            """
        )
    ),
    ui.h2("Provisioning Analysis Dashboard"),
    ui.p(
        "Upload the raw files, validate them, then run the provisioning analysis without editing Python code.",
        class_="metric-note",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_file(
                "provisioning_file",
                "Provisioning workbook (.xlsx)",
                accept=[".xlsx"],
                multiple=False,
            ),
            ui.input_file(
                "metadata_file",
                "Metadata file (.csv)",
                accept=[".csv"],
                multiple=False,
            ),
            ui.input_file(
                "transmitter_file",
                "Adult transmitter file (.xlsx, optional for Q4)",
                accept=[".xlsx"],
                multiple=False,
            ),
            ui.input_action_button("run_analysis", "Run analysis", class_="btn-primary"),
            ui.hr(),
            ui.output_ui("run_status"),
            ui.download_button("download_all", "Download all result tables"),
            ui.download_button("download_ambiguous", "Download ambiguous parent review"),
            width=340,
        ),
        ui.navset_tab(
            ui.nav_panel(
                "Upload & Validate",
                ui.h3("Validation"),
                ui.output_ui("validation_messages"),
                ui.h4("Selected Files"),
                ui.output_ui("selected_files"),
            ),
            ui.nav_panel(
                "Data Quality",
                ui.h3("Data Quality Summary"),
                ui.output_ui("data_quality_table"),
                ui.h3("Rows Excluded By Analysis"),
                ui.output_ui("excluded_rows_table"),
            ),
            ui.nav_panel(
                "Question 1",
                ui.h3("Mean Number Of Prey Delivered Per Hour"),
                ui.output_plot("q1_mean_plot"),
                ui.output_plot("q1_box_plot"),
                ui.output_ui("q1_summary_table"),
                ui.h4("Outliers"),
                ui.output_ui("q1_outlier_table"),
            ),
            ui.nav_panel(
                "Question 2",
                ui.h3("Diet Composition"),
                ui.h4("All Deliveries"),
                ui.output_plot("q2_all_plot"),
                ui.output_ui("q2_all_table"),
                ui.h4("Identified Fish Only"),
                ui.output_plot("q2_fish_plot"),
                ui.output_ui("q2_fish_table"),
            ),
            ui.nav_panel(
                "Question 3",
                ui.h3("Fish Delivered Per Hour And Per Chick-Hour"),
                ui.output_plot("q3_plot"),
                ui.output_ui("q3_summary_table"),
                ui.h4("Outliers"),
                ui.output_ui("q3_outlier_table"),
            ),
            ui.nav_panel(
                "Question 4",
                ui.h3("Tagged Parent Provisioning Rates"),
                ui.p(
                    "Known transmitter PFR codes are direct tagged-parent matches. "
                    "NT / NOT TELEM / NO TELEM / NON TELEM are untagged. "
                    "Exact TELEM / TELE ADULT are generic tagged-parent labels. "
                    "Unresolved labels are listed for review.",
                    class_="metric-note",
                ),
                ui.h4("Tagged Nests Versus Untagged Nests"),
                ui.output_plot("q4_nest_plot"),
                ui.output_ui("q4_nest_table"),
                ui.h4("Tagged Parent Versus Untagged Parent Within Tagged Nests"),
                ui.output_plot("q4_parent_plot"),
                ui.output_ui("q4_parent_table"),
                ui.h4("Adult ID Data Quality"),
                ui.output_ui("q4_quality_table"),
                ui.h4("Ambiguous Parent Status Review"),
                ui.output_ui("q4_ambiguous_table"),
            ),
        ),
    ),
)


def server(input, output, session):
    results = reactive.Value(None)
    last_errors = reactive.Value([])
    last_warnings = reactive.Value([])
    last_message = reactive.Value("Upload files and click Run analysis.")

    def current_paths():
        provisioning = uploaded_path(input.provisioning_file())
        metadata = uploaded_path(input.metadata_file())
        transmitter = uploaded_path(input.transmitter_file())
        return provisioning, metadata, transmitter

    def get_results() -> AnalysisResults | None:
        return results.get()

    def table_from_result(name: str) -> pd.DataFrame:
        result = get_results()
        if result is None:
            return pd.DataFrame()
        return result.tables.get(name, pd.DataFrame())

    @reactive.effect
    @reactive.event(input.run_analysis)
    def _run_analysis():
        provisioning, metadata, transmitter = current_paths()
        validation = validate_inputs(provisioning, metadata, transmitter)
        last_errors.set(validation.errors)
        last_warnings.set(validation.warnings)

        if not validation.is_valid:
            results.set(None)
            last_message.set("Analysis did not run. Fix the upload errors first.")
            return

        try:
            result = build_complete_analysis(provisioning, metadata, transmitter)
        except Exception as exc:  # noqa: BLE001
            results.set(None)
            last_errors.set([f"Analysis failed: {exc}"])
            last_message.set("Analysis failed.")
            return

        results.set(result)
        last_message.set("Analysis complete.")

    @output
    @render.ui
    def run_status():
        return ui.tags.div(
            ui.tags.p(last_message.get()),
            status_box("error", last_errors.get()),
            status_box("warning", last_warnings.get()),
        )

    @output
    @render.ui
    def validation_messages():
        provisioning, metadata, transmitter = current_paths()
        validation = validate_inputs(provisioning, metadata, transmitter)
        if validation.is_valid and not validation.warnings:
            return ui.tags.div({"class": "alert alert-success"}, "Files look ready to analyze.")
        return ui.tags.div(status_box("error", validation.errors), status_box("warning", validation.warnings))

    @output
    @render.ui
    def selected_files():
        rows = []
        for label, file_info in [
            ("Provisioning workbook", input.provisioning_file()),
            ("Metadata", input.metadata_file()),
            ("Adult transmitter", input.transmitter_file()),
        ]:
            if file_info:
                rows.append({"input": label, "file": file_info[0]["name"], "size_bytes": file_info[0]["size"]})
            else:
                rows.append({"input": label, "file": "Not uploaded", "size_bytes": ""})
        return ui.HTML(f'<div class="table-wrap">{table_html(pd.DataFrame(rows))}</div>')

    @output
    @render.ui
    def data_quality_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("data_quality_summary"))}</div>')

    @output
    @render.ui
    def excluded_rows_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("rows_excluded_by_analysis"))}</div>')

    @output
    @render.plot
    def q1_mean_plot():
        return prey_rate_mean(table_from_result("prey_delivered_per_hour_summary"))

    @output
    @render.plot
    def q1_box_plot():
        result = get_results()
        return prey_rate_box(result.cleaned.stints if result else pd.DataFrame())

    @output
    @render.ui
    def q1_summary_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("prey_delivered_per_hour_summary"))}</div>')

    @output
    @render.ui
    def q1_outlier_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("prey_delivered_per_hour_outliers"))}</div>')

    @output
    @render.plot
    def q2_all_plot():
        return diet_bar(
            table_from_result("question2_all_deliveries_diet_composition_percent_summary"),
            "Diet Composition: All Deliveries",
        )

    @output
    @render.ui
    def q2_all_table():
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result("question2_all_deliveries_diet_composition_percent_summary"))}</div>'
        )

    @output
    @render.plot
    def q2_fish_plot():
        return diet_bar(
            table_from_result("question2_identified_fish_only_diet_composition_percent_summary"),
            "Diet Composition: Identified Fish Only",
        )

    @output
    @render.ui
    def q2_fish_table():
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result("question2_identified_fish_only_diet_composition_percent_summary"))}</div>'
        )

    @output
    @render.plot
    def q3_plot():
        return fish_rate_bar(table_from_result("fish_delivery_rates_summary"))

    @output
    @render.ui
    def q3_summary_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("fish_delivery_rates_summary"))}</div>')

    @output
    @render.ui
    def q3_outlier_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("fish_delivery_rates_outliers"))}</div>')

    @output
    @render.plot
    def q4_nest_plot():
        return tagged_nest_bar(table_from_result("tagged_vs_untagged_nest_feeding_rates_summary"))

    @output
    @render.ui
    def q4_nest_table():
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result("tagged_vs_untagged_nest_feeding_rates_summary"))}</div>'
        )

    @output
    @render.plot
    def q4_parent_plot():
        return tagged_parent_bar(table_from_result("tagged_parent_vs_untagged_parent_rates_summary"))

    @output
    @render.ui
    def q4_parent_table():
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result("tagged_parent_vs_untagged_parent_rates_summary"))}</div>'
        )

    @output
    @render.ui
    def q4_quality_table():
        return ui.HTML(f'<div class="table-wrap">{table_html(table_from_result("tagged_parent_analysis_quality_summary"))}</div>')

    @output
    @render.ui
    def q4_ambiguous_table():
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result("tagged_parent_ambiguous_parent_status_review"), max_rows=250)}</div>'
        )

    @render.download(filename="provisioning_analysis_results.zip")
    def download_all():
        result = get_results()
        if result is None:
            yield b""
        else:
            yield make_results_zip(result)

    @render.download(filename="tagged_parent_ambiguous_parent_status_review.csv")
    def download_ambiguous():
        table = table_from_result("tagged_parent_ambiguous_parent_status_review")
        yield table.to_csv(index=False)


app = App(app_ui, server)

