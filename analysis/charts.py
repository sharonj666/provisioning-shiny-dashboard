"""Matplotlib chart builders for the Shiny dashboard."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


sns.set_theme(style="whitegrid", context="notebook")
PALETTE = ["#258b87", "#2670a0", "#da9e2c", "#3e8e41", "#b54137", "#78909c"]
PREY_COLORS = {
    "Ammodytes": "#4c78a8",
    "Bay Anchovy": "#f58518",
    "Mackerel": "#72b7b2",
    "Butterfish": "#54a24b",
    "Herring": "#e45756",
    "Silversides": "#b279a2",
    "F": "#9d755d",
    "Other": "#bab0ac",
    "Unknown": "#af7f67",
}


def empty_figure(message: str = "Run analysis to display this chart."):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.axis("off")
    return fig


def _comparison_group(data: pd.DataFrame) -> pd.Series:
    years = pd.to_numeric(data["year"], errors="coerce").astype("Int64").astype("string")
    return data["species"].astype("string") + "\n" + years


def _diet_comparison_group(data: pd.DataFrame) -> pd.Series:
    if data["year"].nunique(dropna=True) == 1:
        return data["species"].astype("string")
    if data["species"].nunique(dropna=True) == 1:
        return pd.to_numeric(data["year"], errors="coerce").astype("Int64").astype("string")
    return _comparison_group(data)


def prey_rate_mean(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No prey-rate summary available.")
    summary = summary.copy()
    summary["comparison_group"] = _comparison_group(summary)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=summary, x="comparison_group", y="mean", errorbar=None, color=PALETTE[0], ax=ax)
    ax.set_ylabel("Mean prey deliveries per hour")
    ax.set_xlabel("Species and year")
    ax.set_title("Mean prey delivered per hour")
    fig.tight_layout()
    return fig


def prey_rate_box(stints: pd.DataFrame):
    data = stints[stints["valid_observation_duration"]].copy()
    if data.empty:
        return empty_figure("No valid observation durations available.")
    data["comparison_group"] = _comparison_group(data)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(data=data, x="comparison_group", y="prey_deliveries_per_hour", color=PALETTE[0], ax=ax)
    ax.set_ylabel("Prey deliveries per hour")
    ax.set_xlabel("Species and year")
    ax.set_title("Distribution of prey delivery rates")
    fig.tight_layout()
    return fig


def diet_bar(summary: pd.DataFrame, title: str):
    if summary.empty:
        return empty_figure("No diet summary available.")
    plot_data = summary.sort_values(["year", "species", "diet_percent"], ascending=[True, True, False])
    plot_data = plot_data.copy()
    plot_data["comparison_group"] = _comparison_group(plot_data)
    fig, ax = plt.subplots(figsize=(14, 6.5))
    sns.barplot(data=plot_data, x="prey_species", y="diet_percent", hue="comparison_group", errorbar=None, ax=ax)
    ax.tick_params(axis="x", rotation=35, labelsize=10)
    ax.set_xlabel("Prey species")
    ax.set_ylabel("Diet percentage")
    ax.set_title(title)
    fig.tight_layout()
    return fig


def diet_stacked_bar(summary: pd.DataFrame, title: str):
    if summary.empty:
        return empty_figure("No diet summary available.")
    plot_data = summary.copy()
    plot_data["comparison_group"] = _comparison_group(plot_data)
    pivoted = (
        plot_data.pivot_table(
            index="comparison_group",
            columns="prey_species",
            values="diet_percent",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(14, 6.5))
    colors = sns.color_palette(PALETTE, n_colors=len(pivoted.columns))
    pivoted.plot(kind="bar", stacked=True, color=colors, ax=ax)
    ax.set_xlabel("Species and year")
    ax.set_ylabel("Diet percentage")
    ax.set_ylim(0, 100)
    ax.set_title(title)
    ax.legend(title="Prey", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    return fig


def diet_comparison_stacked_bar(
    all_deliveries: pd.DataFrame,
    identified_fish: pd.DataFrame,
):
    """Draw coordinated all-delivery and identified-fish 100% stacked bars."""
    if all_deliveries.empty and identified_fish.empty:
        return empty_figure("No diet summaries available.", (14, 6.5))

    categories = sorted(
        set(all_deliveries.get("prey_species", pd.Series(dtype=str)).dropna().astype(str))
        | set(identified_fish.get("prey_species", pd.Series(dtype=str)).dropna().astype(str))
    )
    preferred = list(PREY_COLORS)
    categories = [name for name in preferred if name in categories] + [
        name for name in categories if name not in preferred
    ]
    fallback = sns.color_palette("tab20", n_colors=max(1, len(categories)))
    colors = {
        category: PREY_COLORS.get(category, fallback[index])
        for index, category in enumerate(categories)
    }

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharey=True)
    panels = [
        (axes[0], all_deliveries, "Diet Composition By Species (All Deliveries)"),
        (axes[1], identified_fish, "Diet Composition By Species (Identified Fish Only)"),
    ]
    legend_handles = []
    for ax, summary, title in panels:
        if summary.empty:
            ax.text(0.5, 0.5, "No matching data", ha="center", va="center")
            ax.set_axis_off()
            continue
        data = summary.copy()
        data["comparison_group"] = _diet_comparison_group(data)
        pivoted = data.pivot_table(
            index="comparison_group",
            columns="prey_species",
            values="diet_percent",
            aggfunc="sum",
            fill_value=0,
        ).reindex(columns=categories, fill_value=0)
        pivoted.plot(
            kind="bar",
            stacked=True,
            color=[colors[column] for column in pivoted.columns],
            width=0.62,
            ax=ax,
            legend=False,
        )
        ax.set_title(title, fontsize=12, pad=12)
        ax.set_xlabel("")
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=0)
        ax.grid(axis="x", visible=False)
        if not legend_handles:
            legend_handles = [
                plt.Rectangle((0, 0), 1, 1, color=colors[column])
                for column in pivoted.columns
            ]

    axes[0].set_ylabel("Diet composition (%)")
    axes[1].set_ylabel("")
    if legend_handles:
        fig.legend(
            legend_handles,
            categories,
            title="Prey species / category",
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=min(5, max(1, len(categories))),
            frameon=False,
        )
    fig.subplots_adjust(top=0.78, bottom=0.13, left=0.07, right=0.98, wspace=0.2)
    return fig


def fish_rate_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No fish-rate summary available.")
    summary = summary.copy()
    summary["comparison_group"] = _comparison_group(summary)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=summary, x="comparison_group", y="mean", hue="metric_name", errorbar=None, ax=ax)
    ax.set_ylabel("Mean rate")
    ax.set_xlabel("Species and year")
    ax.set_title("Fish delivery rates")
    fig.tight_layout()
    return fig


def fish_rate_box(fish_rates: pd.DataFrame):
    if fish_rates.empty:
        return empty_figure("No fish-rate observations available.")
    data = fish_rates.copy()
    data["comparison_group"] = _comparison_group(data)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(
        data=data,
        x="comparison_group",
        y="metric_value",
        hue="metric_name",
        ax=ax,
    )
    ax.set_xlabel("Species and year")
    ax.set_ylabel("Fish delivery rate")
    ax.set_title("Distribution of fish delivery rates")
    ax.legend(title="Metric")
    fig.tight_layout()
    return fig


def tagged_nest_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No tagged-nest summary available.")
    summary = summary.copy()
    summary["comparison_group"] = _comparison_group(summary)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=summary, x="tagged_nest", y="mean", hue="comparison_group", errorbar=None, ax=ax)
    ax.set_xlabel("Nest has tagged parent")
    ax.set_ylabel("Mean prey deliveries per hour")
    ax.set_title("Mean feeding rate by tagged-nest status")
    fig.tight_layout()
    return fig


def tagged_parent_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No parent-rate summary available.")
    summary = summary.copy()
    summary["comparison_group"] = _comparison_group(summary)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=summary, x="parent_rate_group", y="mean", hue="comparison_group", errorbar=None, ax=ax)
    ax.set_xlabel("Parent delivery category")
    ax.set_ylabel("Mean deliveries per hour")
    ax.set_title("Tagged vs untagged parent feeding rates")
    fig.tight_layout()
    return fig
