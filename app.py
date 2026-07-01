"""Multi-workbook Shiny dashboard for provisioning analysis."""

from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))

import matplotlib.pyplot as plt
import pandas as pd
from shiny import App, reactive, render, ui

from analysis.charts import (
    diet_bar,
    diet_stacked_bar,
    fish_rate_bar,
    fish_rate_box,
    prey_rate_box,
    prey_rate_mean,
    tagged_nest_bar,
    tagged_parent_bar,
)
from analysis.core import AnalysisResults, build_complete_analysis, filter_analysis_results
from analysis.validation import validate_multiple_inputs


APP_CSS = (ROOT / "www" / "styles.css").read_text(encoding="utf-8")
MAX_UPLOAD_BYTES = 75 * 1024 * 1024


def uploaded_paths(file_info) -> list[Path]:
    if not file_info:
        return []
    paths = []
    for item in file_info:
        if int(item.get("size", 0)) > MAX_UPLOAD_BYTES:
            raise ValueError(f"{item.get('name', 'Upload')} exceeds the 75 MB file limit.")
        paths.append(Path(item["datapath"]))
    return paths


def uploaded_path(file_info) -> Path | None:
    paths = uploaded_paths(file_info)
    return paths[0] if paths else None


def upload_names(file_info) -> list[str]:
    return [str(item.get("name", "uploaded_file")) for item in (file_info or [])]


def table_html(df: pd.DataFrame | None, max_rows: int = 100) -> str:
    if df is None or df.empty:
        return '<p class="empty-message">No rows to display for the current selection.</p>'
    return df.head(max_rows).to_html(
        index=False,
        classes="table table-striped table-sm",
        border=0,
    )


def status_box(kind: str, messages: list[str]):
    if not messages:
        return ui.tags.div()
    css_class = "alert alert-danger" if kind == "error" else "alert alert-warning"
    return ui.tags.div(
        {"class": css_class},
        ui.tags.strong("Errors" if kind == "error" else "Warnings"),
        ui.tags.ul(*[ui.tags.li(message) for message in messages]),
    )


def as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


FIGURE_BUILDERS = {
    "mean_prey_delivered_per_hour": lambda result: prey_rate_mean(
        result.tables.get("prey_delivered_per_hour_summary", pd.DataFrame())
    ),
    "prey_delivery_rate_boxplot": lambda result: prey_rate_box(result.cleaned.stints),
    "diet_all_deliveries": lambda result: diet_bar(
        result.tables.get(
            "question2_all_deliveries_diet_composition_percent_summary",
            pd.DataFrame(),
        ),
        "Diet Composition: All Deliveries",
    ),
    "diet_all_deliveries_stacked": lambda result: diet_stacked_bar(
        result.tables.get(
            "question2_all_deliveries_diet_composition_percent_summary",
            pd.DataFrame(),
        ),
        "Diet Composition by Group: All Deliveries",
    ),
    "diet_identified_fish": lambda result: diet_bar(
        result.tables.get(
            "question2_identified_fish_only_diet_composition_percent_summary",
            pd.DataFrame(),
        ),
        "Diet Composition: Identified Fish Only",
    ),
    "diet_identified_fish_stacked": lambda result: diet_stacked_bar(
        result.tables.get(
            "question2_identified_fish_only_diet_composition_percent_summary",
            pd.DataFrame(),
        ),
        "Diet Composition by Group: Identified Fish Only",
    ),
    "fish_delivery_rates": lambda result: fish_rate_bar(
        result.tables.get("fish_delivery_rates_summary", pd.DataFrame())
    ),
    "fish_delivery_rates_boxplot": lambda result: fish_rate_box(
        result.tables.get("fish_delivery_rates_long", pd.DataFrame())
    ),
    "tagged_nest_feeding_rates": lambda result: tagged_nest_bar(
        result.tables.get(
            "tagged_vs_untagged_nest_feeding_rates_summary",
            pd.DataFrame(),
        )
    ),
    "tagged_parent_feeding_rates": lambda result: tagged_parent_bar(
        result.tables.get(
            "tagged_parent_vs_untagged_parent_rates_summary",
            pd.DataFrame(),
        )
    ),
}


app_ui = ui.page_navbar(
    ui.nav_panel(
        "Upload Data",
        ui.layout_columns(
            ui.card(
                ui.card_header("1. Select analysis setup"),
                ui.input_radio_buttons(
                    "analysis_mode",
                    "Comparison mode",
                    {
                        "single": "Analyze one species in one year",
                        "years": "Compare one species across years",
                        "species": "Compare species within one year",
                    },
                    selected="single",
                ),
                ui.output_ui("upload_requirements"),
                ui.p(
                    "Uploads are processed only for this browser session.",
                    class_="callout",
                ),
            ),
            ui.card(
                ui.card_header("2. Upload source files"),
                ui.input_file(
                    "provisioning_file",
                    "Provisioning workbook(s) *",
                    accept=[".xlsx"],
                    multiple=True,
                ),
                ui.input_file(
                    "metadata_file",
                    "Shared metadata file *",
                    accept=[".csv"],
                    multiple=False,
                ),
                ui.input_file(
                    "transmitter_file",
                    "Adult transmitter workbook(s), optional",
                    accept=[".xlsx"],
                    multiple=True,
                ),
            ),
            col_widths=(5, 7),
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("3. Validate files"),
                ui.output_ui("validation_messages"),
                ui.output_ui("selected_files"),
            ),
            ui.card(
                ui.card_header("4. Generate analysis"),
                ui.p(
                    "Generate the analysis, then choose the active years and species from the navigation bar.",
                    class_="callout",
                ),
                ui.input_action_button(
                    "run_analysis",
                    "Generate analysis",
                    class_="btn-success btn-lg",
                ),
                ui.output_ui("run_status"),
            ),
            col_widths=(7, 5),
        ),
    ),
    ui.nav_panel(
        "Data Quality",
        ui.layout_columns(
            ui.card(
                ui.card_header("Data Quality Summary"),
                ui.output_ui("data_quality_table"),
            ),
            ui.card(
                ui.card_header("Rows Excluded By Analysis"),
                ui.output_ui("excluded_rows_table"),
            ),
            col_widths=(6, 6),
        ),
    ),
    ui.nav_panel(
        "Mean Prey Delivered per Hour",
        ui.card(
            ui.card_header("Statistical summary"),
            ui.output_ui("q1_stat_summary"),
            ui.output_ui("q1_stat_table"),
        ),
        ui.card(
            ui.card_header("Mean rate"),
            ui.output_plot("q1_mean_plot", height="540px"),
        ),
        ui.card(
            ui.card_header("Rate distribution"),
            ui.output_plot("q1_box_plot", height="540px"),
        ),
        ui.card(
            ui.card_header("Complete summary table"),
            ui.output_ui("q1_summary_table"),
        ),
        ui.card(
            ui.card_header("Outliers"),
            ui.output_ui("q1_outlier_table"),
        ),
    ),
    ui.nav_panel(
        "Diet Composition",
        ui.card(
            ui.card_header("All deliveries"),
            ui.output_plot("q2_all_plot", height="560px"),
            ui.output_plot("q2_all_stacked_plot", height="560px"),
            ui.output_ui("q2_all_table"),
        ),
        ui.card(
            ui.card_header("Identified fish only"),
            ui.output_plot("q2_fish_plot", height="560px"),
            ui.output_plot("q2_fish_stacked_plot", height="560px"),
            ui.output_ui("q2_fish_table"),
        ),
    ),
    ui.nav_panel(
        "Fish Delivery Rates",
        ui.card(
            ui.card_header("Mean rates"),
            ui.output_plot("q3_plot", height="540px"),
        ),
        ui.card(
            ui.card_header("Rate distributions"),
            ui.output_plot("q3_box_plot", height="540px"),
        ),
        ui.card(ui.card_header("Summary"), ui.output_ui("q3_summary_table")),
        ui.card(ui.card_header("Outliers"), ui.output_ui("q3_outlier_table")),
    ),
    ui.nav_panel(
        "Feeding Rate by Tagged Status",
        ui.p(
            "Known transmitter PFR codes are tagged-parent matches. NT variants are "
            "untagged, exact TELEM labels are generic tagged-parent labels, and "
            "unresolved labels remain available for review.",
            class_="callout",
        ),
        ui.card(
            ui.card_header("Tagged versus untagged nests"),
            ui.output_plot("q4_nest_plot", height="540px"),
            ui.output_ui("q4_nest_table"),
        ),
        ui.card(
            ui.card_header("Tagged versus untagged parents"),
            ui.output_plot("q4_parent_plot", height="540px"),
            ui.output_ui("q4_parent_table"),
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Adult ID data quality"),
                ui.output_ui("q4_quality_table"),
            ),
            ui.card(
                ui.card_header("Ambiguous parent status review"),
                ui.output_ui("q4_ambiguous_table"),
            ),
            col_widths=(5, 7),
        ),
    ),
    ui.nav_panel(
        "Downloads",
        ui.card(
            ui.card_header("Download current analysis"),
            ui.output_ui("download_selector_ui"),
            ui.input_checkbox(
                "download_all_items",
                "Include every available CSV and figure",
                value=True,
            ),
            ui.download_button("download_selected", "Download ZIP", class_="btn-primary"),
            ui.p(
                "Exports reflect the active comparison mode, years, and species.",
                class_="callout",
            ),
        ),
    ),
    ui.nav_spacer(),
    ui.nav_control(ui.output_ui("global_controls")),
    title="Provisioning Analysis",
    id="main_nav",
    header=ui.tags.style(APP_CSS),
    fillable=False,
)


def server(input, output, session):
    results = reactive.Value(None)
    last_errors = reactive.Value([])
    last_warnings = reactive.Value([])
    last_message = reactive.Value("Upload files and generate the analysis.")

    def current_uploads():
        provisioning = uploaded_paths(input.provisioning_file())
        metadata = uploaded_path(input.metadata_file())
        transmitters = uploaded_paths(input.transmitter_file())
        return provisioning, metadata, transmitters

    def validation():
        try:
            provisioning, metadata, transmitters = current_uploads()
        except ValueError as exc:
            from analysis.validation import ValidationResult

            return ValidationResult(False, [str(exc)], [])
        return validate_multiple_inputs(
            provisioning,
            metadata,
            transmitters,
            upload_names(input.provisioning_file()),
            upload_names(input.transmitter_file()),
        )

    def raw_results() -> AnalysisResults | None:
        return results.get()

    def selection_values(result: AnalysisResults) -> tuple[list[int], list[str]]:
        stints = result.cleaned.stints
        available_years = sorted(
            pd.to_numeric(stints.get("year", pd.Series(dtype=float)), errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        available_species = sorted(
            stints.get("species", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
        )
        mode = input.analysis_mode()
        selected_years = as_list(input.filter_years())
        selected_species = as_list(input.filter_species())
        if not selected_years:
            selected_years = [str(value) for value in (available_years if mode == "years" else available_years[:1])]
        if not selected_species:
            selected_species = available_species if mode == "species" else available_species[:1]
        return [int(value) for value in selected_years], selected_species

    @reactive.calc
    def active_results() -> AnalysisResults | None:
        result = raw_results()
        if result is None:
            return None
        years, species = selection_values(result)
        return filter_analysis_results(result, years=years, species=species)

    def table_from_result(name: str) -> pd.DataFrame:
        result = active_results()
        if result is None:
            return pd.DataFrame()
        return result.tables.get(name, pd.DataFrame())

    @output
    @render.ui
    def upload_requirements():
        messages = {
            "single": "Upload one or more workbooks, then select one year and one species.",
            "years": "Upload workbooks covering at least two years for the same species.",
            "species": "Upload workbooks containing at least two species in the same year.",
        }
        return ui.p(messages[input.analysis_mode()], class_="callout")

    @output
    @render.ui
    def global_controls():
        result = raw_results()
        if result is None:
            return ui.span("No active analysis", class_="navbar-status")
        stints = result.cleaned.stints
        years = sorted(pd.to_numeric(stints["year"], errors="coerce").dropna().astype(int).unique())
        species = sorted(stints["species"].dropna().astype(str).unique())
        mode = input.analysis_mode()
        return ui.div(
            ui.input_selectize(
                "filter_years",
                "Year",
                {str(year): str(year) for year in years},
                selected=[str(year) for year in years] if mode == "years" else (str(years[0]) if len(years) else None),
                multiple=mode == "years",
            ),
            ui.input_selectize(
                "filter_species",
                "Species",
                {value: value for value in species},
                selected=species if mode == "species" else (species[0] if species else None),
                multiple=mode == "species",
            ),
            class_="global-controls",
        )

    @reactive.effect
    @reactive.event(input.run_analysis)
    def _run_analysis():
        checked = validation()
        last_errors.set(checked.errors)
        last_warnings.set(checked.warnings)
        if not checked.is_valid:
            results.set(None)
            last_message.set("Analysis did not run. Fix the upload errors first.")
            return
        provisioning, metadata, transmitters = current_uploads()
        try:
            result = build_complete_analysis(
                provisioning,
                metadata,
                transmitters or None,
                source_names=upload_names(input.provisioning_file()),
            )
        except Exception as exc:  # noqa: BLE001
            results.set(None)
            last_errors.set([f"Analysis failed: {exc}"])
            last_message.set("Analysis failed.")
            return
        results.set(result)
        years = sorted(pd.to_numeric(result.cleaned.stints["year"], errors="coerce").dropna().astype(int).unique())
        species = sorted(result.cleaned.stints["species"].dropna().astype(str).unique())
        mode = input.analysis_mode()
        if mode == "years" and len(years) < 2:
            last_warnings.set(last_warnings.get() + ["Cross-year comparison currently has fewer than two years."])
        if mode == "species" and len(species) < 2:
            last_warnings.set(last_warnings.get() + ["Cross-species comparison currently has fewer than two species."])
        last_message.set(
            f"Analysis complete: {len(provisioning)} workbook(s), "
            f"{len(years)} year(s), and {len(species)} species."
        )

    @output
    @render.ui
    def run_status():
        return ui.div(
            ui.p(last_message.get(), class_="status-message"),
            status_box("error", last_errors.get()),
            status_box("warning", last_warnings.get()),
        )

    @output
    @render.ui
    def validation_messages():
        checked = validation()
        if checked.is_valid and not checked.warnings:
            return ui.div("Files look ready to analyze.", class_="alert alert-success")
        return ui.div(
            status_box("error", checked.errors),
            status_box("warning", checked.warnings),
        )

    @output
    @render.ui
    def selected_files():
        rows = []
        for label, file_info in [
            ("Provisioning", input.provisioning_file()),
            ("Metadata", input.metadata_file()),
            ("Adult transmitter", input.transmitter_file()),
        ]:
            if file_info:
                rows.extend(
                    {
                        "input": label,
                        "file": item["name"],
                        "size_bytes": item["size"],
                    }
                    for item in file_info
                )
            else:
                rows.append({"input": label, "file": "Not uploaded", "size_bytes": ""})
        return ui.HTML(f'<div class="table-wrap">{table_html(pd.DataFrame(rows))}</div>')

    def table_output(name: str, max_rows: int = 100):
        return ui.HTML(
            f'<div class="table-wrap">{table_html(table_from_result(name), max_rows)}</div>'
        )

    @output
    @render.ui
    def data_quality_table():
        return table_output("data_quality_summary")

    @output
    @render.ui
    def excluded_rows_table():
        return table_output("rows_excluded_by_analysis")

    @output
    @render.plot
    def q1_mean_plot():
        return prey_rate_mean(table_from_result("prey_delivered_per_hour_summary"))

    @output
    @render.plot
    def q1_box_plot():
        result = active_results()
        return prey_rate_box(result.cleaned.stints if result else pd.DataFrame())

    @output
    @render.ui
    def q1_summary_table():
        return table_output("prey_delivered_per_hour_summary")

    @output
    @render.ui
    def q1_stat_summary():
        summary = table_from_result("prey_delivered_per_hour_summary")
        if summary.empty:
            return ui.p(
                "Generate an analysis with matching year and species selections.",
                class_="empty-message",
            )
        groups = []
        for row in summary.itertuples(index=False):
            values = row._asdict()

            def number(name: str, digits: int = 2) -> str:
                value = values.get(name)
                return "—" if pd.isna(value) else f"{float(value):.{digits}f}"

            groups.append(
                ui.div(
                    ui.h4(f"{values.get('species')} · {int(values.get('year'))}"),
                    ui.div(
                        ui.div(ui.span("Sample size"), ui.strong(str(int(values.get("n", 0)))), class_="stat"),
                        ui.div(ui.span("Mean"), ui.strong(number("mean")), class_="stat"),
                        ui.div(ui.span("Standard error"), ui.strong(number("standard_error")), class_="stat"),
                        ui.div(ui.span("Median"), ui.strong(number("median")), class_="stat"),
                        ui.div(
                            ui.span("Interquartile range"),
                            ui.strong(f"{number('q25')}–{number('q75')}"),
                            class_="stat",
                        ),
                        class_="stat-grid",
                    ),
                    class_="stat-group",
                )
            )
        return ui.div(*groups, class_="stat-summary")

    @output
    @render.ui
    def q1_stat_table():
        summary = table_from_result("prey_delivered_per_hour_summary")
        if summary.empty:
            return ui.tags.div()
        columns = {
            "year": "Year",
            "species": "Species",
            "n": "Sample size",
            "mean": "Mean prey/hour",
            "standard_error": "Standard error",
            "q25": "25th percentile",
            "median": "Median",
            "q75": "75th percentile",
            "outlier_count": "Outliers",
        }
        compact = summary[
            [column for column in columns if column in summary.columns]
        ].rename(columns=columns)
        numeric_columns = [
            "Mean prey/hour",
            "Standard error",
            "25th percentile",
            "Median",
            "75th percentile",
        ]
        for column in numeric_columns:
            if column in compact:
                compact[column] = pd.to_numeric(compact[column], errors="coerce").round(3)
        return ui.div(
            ui.h4("Mean prey delivered per hour summary table"),
            ui.HTML(table_html(compact, max_rows=500)),
            class_="compact-summary-table",
        )

    @output
    @render.ui
    def q1_outlier_table():
        return table_output("prey_delivered_per_hour_outliers")

    @output
    @render.plot
    def q2_all_plot():
        return diet_bar(
            table_from_result("question2_all_deliveries_diet_composition_percent_summary"),
            "Diet Composition: All Deliveries",
        )

    @output
    @render.plot
    def q2_all_stacked_plot():
        return diet_stacked_bar(
            table_from_result("question2_all_deliveries_diet_composition_percent_summary"),
            "Diet Composition by Group: All Deliveries",
        )

    @output
    @render.ui
    def q2_all_table():
        return table_output("question2_all_deliveries_diet_composition_percent_summary")

    @output
    @render.plot
    def q2_fish_plot():
        return diet_bar(
            table_from_result("question2_identified_fish_only_diet_composition_percent_summary"),
            "Diet Composition: Identified Fish Only",
        )

    @output
    @render.plot
    def q2_fish_stacked_plot():
        return diet_stacked_bar(
            table_from_result("question2_identified_fish_only_diet_composition_percent_summary"),
            "Diet Composition by Group: Identified Fish Only",
        )

    @output
    @render.ui
    def q2_fish_table():
        return table_output("question2_identified_fish_only_diet_composition_percent_summary")

    @output
    @render.plot
    def q3_plot():
        return fish_rate_bar(table_from_result("fish_delivery_rates_summary"))

    @output
    @render.plot
    def q3_box_plot():
        return fish_rate_box(table_from_result("fish_delivery_rates_long"))

    @output
    @render.ui
    def q3_summary_table():
        return table_output("fish_delivery_rates_summary")

    @output
    @render.ui
    def q3_outlier_table():
        return table_output("fish_delivery_rates_outliers")

    @output
    @render.plot
    def q4_nest_plot():
        return tagged_nest_bar(
            table_from_result("tagged_vs_untagged_nest_feeding_rates_summary")
        )

    @output
    @render.ui
    def q4_nest_table():
        return table_output("tagged_vs_untagged_nest_feeding_rates_summary")

    @output
    @render.plot
    def q4_parent_plot():
        return tagged_parent_bar(
            table_from_result("tagged_parent_vs_untagged_parent_rates_summary")
        )

    @output
    @render.ui
    def q4_parent_table():
        return table_output("tagged_parent_vs_untagged_parent_rates_summary")

    @output
    @render.ui
    def q4_quality_table():
        return table_output("tagged_parent_analysis_quality_summary")

    @output
    @render.ui
    def q4_ambiguous_table():
        return table_output("tagged_parent_ambiguous_parent_status_review", 250)

    def download_choices() -> dict[str, str]:
        result = active_results()
        if result is None:
            return {}
        choices = {
            f"csv:{name}": f"CSV — {name.replace('_', ' ').title()}"
            for name in sorted(result.tables)
        }
        choices.update(
            {
                f"figure:{name}": f"Figure — {name.replace('_', ' ').title()}"
                for name in FIGURE_BUILDERS
            }
        )
        return choices

    @output
    @render.ui
    def download_selector_ui():
        choices = download_choices()
        if not choices:
            return ui.p("Generate an analysis to choose downloads.")
        defaults = list(choices)[: min(6, len(choices))]
        return ui.input_checkbox_group(
            "download_items",
            "Choose CSVs and figures",
            choices,
            selected=defaults,
        )

    @render.download(filename="provisioning_analysis_selection.zip")
    def download_selected():
        result = active_results()
        if result is None:
            yield b""
            return
        choices = download_choices()
        selected = list(choices) if input.download_all_items() else as_list(input.download_items())
        years, species = selection_values(raw_results())
        memory = BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "analysis_mode": input.analysis_mode(),
                "years": years,
                "species": species,
                "source_workbooks": upload_names(input.provisioning_file()),
                "transmitter_workbooks": upload_names(input.transmitter_file()),
                "selected_items": selected,
            }
            archive.writestr("analysis_selection.json", json.dumps(manifest, indent=2))
            for item in selected:
                kind, _, name = item.partition(":")
                if kind == "csv" and name in result.tables:
                    archive.writestr(
                        f"tables/{name}.csv",
                        result.tables[name].to_csv(index=False),
                    )
                elif kind == "figure" and name in FIGURE_BUILDERS:
                    figure = FIGURE_BUILDERS[name](result)
                    image = BytesIO()
                    figure.savefig(image, format="png", dpi=180, bbox_inches="tight")
                    plt.close(figure)
                    archive.writestr(f"figures/{name}.png", image.getvalue())
        yield memory.getvalue()


app = App(app_ui, server)
