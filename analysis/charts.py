"""Matplotlib chart builders for the Shiny dashboard."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


sns.set_theme(style="whitegrid", context="notebook")
PALETTE = ["#258b87", "#2670a0", "#da9e2c", "#3e8e41", "#b54137", "#78909c"]


def empty_figure(message: str = "Run analysis to display this chart."):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.axis("off")
    return fig


def _comparison_group(data: pd.DataFrame) -> pd.Series:
    years = pd.to_numeric(data["year"], errors="coerce").astype("Int64").astype("string")
    return data["species"].astype("string") + "\n" + years


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
