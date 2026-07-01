"""Matplotlib chart builders for the Shiny dashboard."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


sns.set_theme(style="whitegrid", context="notebook")


def empty_figure(message: str = "Run analysis to display this chart."):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.axis("off")
    return fig


def prey_rate_mean(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No prey-rate summary available.")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=summary, x="species", y="mean", hue="year", errorbar=None, ax=ax)
    ax.set_ylabel("Mean prey deliveries per hour")
    ax.set_xlabel("Bird species")
    ax.set_title("Mean prey delivered per hour")
    fig.tight_layout()
    return fig


def prey_rate_box(stints: pd.DataFrame):
    data = stints[stints["valid_observation_duration"]].copy()
    if data.empty:
        return empty_figure("No valid observation durations available.")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=data, x="species", y="prey_deliveries_per_hour", hue="year", ax=ax)
    ax.set_ylabel("Prey deliveries per hour")
    ax.set_xlabel("Bird species")
    ax.set_title("Distribution of prey delivery rates")
    fig.tight_layout()
    return fig


def diet_bar(summary: pd.DataFrame, title: str):
    if summary.empty:
        return empty_figure("No diet summary available.")
    plot_data = summary.sort_values(["year", "species", "diet_percent"], ascending=[True, True, False])
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=plot_data, x="prey_species", y="diet_percent", hue="species", errorbar=None, ax=ax)
    ax.tick_params(axis="x", rotation=35)
    ax.set_xlabel("Prey species")
    ax.set_ylabel("Diet percentage")
    ax.set_title(title)
    fig.tight_layout()
    return fig


def fish_rate_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No fish-rate summary available.")
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=summary, x="species", y="mean", hue="metric_name", errorbar=None, ax=ax)
    ax.set_ylabel("Mean rate")
    ax.set_xlabel("Bird species")
    ax.set_title("Fish delivery rates")
    fig.tight_layout()
    return fig


def tagged_nest_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No tagged-nest summary available.")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=summary, x="tagged_nest", y="mean", hue="species", errorbar=None, ax=ax)
    ax.set_xlabel("Nest has tagged parent")
    ax.set_ylabel("Mean prey deliveries per hour")
    ax.set_title("Mean feeding rate by tagged-nest status")
    fig.tight_layout()
    return fig


def tagged_parent_bar(summary: pd.DataFrame):
    if summary.empty:
        return empty_figure("No parent-rate summary available.")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=summary, x="parent_rate_group", y="mean", hue="species", errorbar=None, ax=ax)
    ax.set_xlabel("Parent delivery category")
    ax.set_ylabel("Mean deliveries per hour")
    ax.set_title("Tagged vs untagged parent feeding rates")
    fig.tight_layout()
    return fig

