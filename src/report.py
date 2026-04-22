"""Rendering helpers: DQ DataFrame -> markdown table, and matplotlib charts."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

FIG_DIR = Path(__file__).resolve().parents[1] / "output" / "figures"


def dq_table_markdown(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def missingness_bar(df: pd.DataFrame, path: Path | str | None = None) -> Path:
    path = Path(path) if path else FIG_DIR / "missingness.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    null_pct = (df.isna().sum() / len(df) * 100).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    null_pct.plot.barh(ax=ax, color="#2a5d84")
    ax.set_xlabel("% null")
    ax.set_title("Missingness by column (1.07M rows)")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def price_distribution(df: pd.DataFrame, path: Path | str | None = None) -> Path:
    path = Path(path) if path else FIG_DIR / "price_distribution.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    prices = df["Price"].dropna()
    clip = prices.quantile(0.995)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.0))
    axes[0].hist(prices.clip(lower=-5, upper=clip), bins=60, color="#2a5d84")
    axes[0].set_title(f"Price (clipped at 99.5th pct = {clip:.2f})")
    axes[0].set_xlabel("Unit price")
    axes[0].set_ylabel("Rows")
    tail = prices[prices > clip]
    axes[1].hist(tail, bins=30, color="#b33c3c")
    axes[1].set_title(f"Tail: price > {clip:.2f}  (n={len(tail):,})")
    axes[1].set_xlabel("Unit price")
    for ax in axes:
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def severity_breakdown(dq_df: pd.DataFrame, path: Path | str | None = None) -> Path:
    path = Path(path) if path else FIG_DIR / "severity_breakdown.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = dq_df["Severity"].value_counts().reindex(["Blocker", "High", "Medium", "Low"]).fillna(0)
    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    colors = ["#b33c3c", "#d98d2e", "#e6c229", "#7ba05b"]
    counts.plot.bar(ax=ax, color=colors)
    ax.set_title("Quality checks by severity")
    ax.set_ylabel("# checks")
    ax.set_xticklabels(counts.index, rotation=0)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
