"""Shared summary-statistic helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_metric(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize a numeric metric and flag outliers with the 1.5x IQR rule."""
    rows: list[dict[str, object]] = []
    outlier_rows: list[pd.DataFrame] = []

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        values = pd.to_numeric(group[value_col], errors="coerce").dropna()
        n = int(values.shape[0])
        if n == 0:
            stats = {
                "n": 0,
                "mean": np.nan,
                "standard_error": np.nan,
                "q25": np.nan,
                "median": np.nan,
                "q75": np.nan,
                "lower_outlier_bound": np.nan,
                "upper_outlier_bound": np.nan,
                "outlier_count": 0,
            }
        else:
            q25 = values.quantile(0.25)
            median = values.quantile(0.50)
            q75 = values.quantile(0.75)
            iqr = q75 - q25
            lower = q25 - 1.5 * iqr
            upper = q75 + 1.5 * iqr
            mask = group[value_col].lt(lower) | group[value_col].gt(upper)
            outliers = group.loc[mask].copy()
            if not outliers.empty:
                outliers["metric"] = value_col
                for col, key in zip(group_cols, keys, strict=False):
                    outliers[col] = key
                outlier_rows.append(outliers)

            stats = {
                "n": n,
                "mean": values.mean(),
                "standard_error": values.sem() if n > 1 else 0.0,
                "q25": q25,
                "median": median,
                "q75": q75,
                "lower_outlier_bound": lower,
                "upper_outlier_bound": upper,
                "outlier_count": int(mask.sum()),
            }

        rows.append({**dict(zip(group_cols, keys, strict=False)), "metric": value_col, **stats})

    summary = pd.DataFrame(rows)
    outliers = pd.concat(outlier_rows, ignore_index=True) if outlier_rows else pd.DataFrame()
    return summary, outliers

