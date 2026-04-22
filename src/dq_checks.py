"""Data-quality checks organised by dimension.

Each check returns a CheckResult with a pricing-model impact statement, so the
output is not just a list of violations but a business-framed severity table.
The registry keeps checks composable: run_all() executes everything and returns
a DataFrame ready for markdown export.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

DIMENSIONS = ("Completeness", "Validity", "Uniqueness", "Consistency", "Integrity", "Anomaly")
SEVERITIES = ("Blocker", "High", "Medium", "Low")

NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "BANK CHARGES", "AMAZONFEE", "TEST", "ADJUST", "ADJUST2",
    "D", "B", "CRUK", "PADS", "SP1002", "DCGSSBOY", "DCGSSGIRL", "DCGS0070",
    "gift_0001_10", "gift_0001_20", "gift_0001_30", "gift_0001_40", "gift_0001_50",
    "S", "m",
}

NON_PRODUCT_REGEX = re.compile(r"^(?:[A-Z]{1,4}|[a-z]{1,4}|[A-Z]*FEE|TEST.*|ADJUST.*|gift_.*|DCGS.*)$")


@dataclass
class CheckResult:
    dimension: str
    name: str
    failed_rows: int
    total_rows: int
    severity: str
    pricing_impact: str
    sample: list = field(default_factory=list)

    @property
    def rate(self) -> float:
        return (self.failed_rows / self.total_rows) if self.total_rows else 0.0

    def to_row(self) -> dict:
        return {
            "Dimension": self.dimension,
            "Check": self.name,
            "Failing rows": self.failed_rows,
            "% of total": f"{self.rate * 100:.2f}%",
            "Severity": self.severity,
            "Pricing-model impact": self.pricing_impact,
        }


CheckFn = Callable[[pd.DataFrame], CheckResult]
REGISTRY: list[CheckFn] = []


def register(fn: CheckFn) -> CheckFn:
    REGISTRY.append(fn)
    return fn


# ---------- Completeness ----------
@register
def customer_id_missing(df: pd.DataFrame) -> CheckResult:
    failed = int(df["Customer ID"].isna().sum())
    return CheckResult(
        "Completeness", "Customer ID is null",
        failed, len(df), "Blocker",
        "Customer-level price elasticity and retention segmentation both require a stable customer key. Null customer IDs cannot be imputed without ambiguity.",
    )


@register
def description_missing(df: pd.DataFrame) -> CheckResult:
    failed = int(df["Description"].isna().sum() + (df["Description"].fillna("").str.len().eq(0)).sum())
    return CheckResult(
        "Completeness", "Description is null or empty",
        failed, len(df), "Medium",
        "Missing descriptions hide product clustering signals and block human review of anomalies.",
    )


@register
def price_missing(df: pd.DataFrame) -> CheckResult:
    failed = int(df["Price"].isna().sum())
    return CheckResult(
        "Completeness", "Price is null",
        failed, len(df), "Blocker",
        "Price is the target variable for a pricing model; null rows are unusable.",
    )


# ---------- Validity ----------
@register
def price_non_positive(df: pd.DataFrame) -> CheckResult:
    mask = df["Price"].fillna(0) <= 0
    failed = int(mask.sum())
    return CheckResult(
        "Validity", "Price <= 0",
        failed, len(df), "High",
        "Zero or negative unit prices contaminate the price distribution and bias any learned elasticity curve.",
    )


@register
def quantity_zero(df: pd.DataFrame) -> CheckResult:
    mask = df["Quantity"].fillna(0) == 0
    failed = int(mask.sum())
    return CheckResult(
        "Validity", "Quantity == 0",
        failed, len(df), "Medium",
        "Zero-quantity rows contribute no revenue and no volume signal; they should be excluded before modelling.",
    )


@register
def currency_implicit(df: pd.DataFrame) -> CheckResult:
    # The dataset has no currency column at all — this is a schema-level blocker.
    return CheckResult(
        "Validity", "Currency column absent",
        len(df), len(df), "Blocker",
        "Without an explicit currency, any multi-country pricing model silently mixes GBP, EUR, and other currencies as if comparable.",
    )


# ---------- Uniqueness ----------
@register
def exact_duplicates(df: pd.DataFrame) -> CheckResult:
    failed = int(df.duplicated().sum())
    return CheckResult(
        "Uniqueness", "Exact duplicate rows",
        failed, len(df), "High",
        "Duplicate rows inflate both revenue and volume, biasing any aggregation-based feature.",
    )


@register
def invoice_stockcode_duplicates(df: pd.DataFrame) -> CheckResult:
    dup_mask = df.duplicated(subset=["Invoice", "StockCode"], keep=False)
    failed = int(dup_mask.sum())
    return CheckResult(
        "Uniqueness", "Duplicate (Invoice, StockCode) pairs",
        failed, len(df), "Medium",
        "Multiple lines of the same SKU on the same invoice should be consolidated with summed quantity; otherwise line counts misrepresent basket size.",
    )


# ---------- Consistency ----------
@register
def stockcode_case_variants(df: pd.DataFrame) -> CheckResult:
    stock = df["StockCode"].dropna().unique()
    lower_map: dict[str, set[str]] = {}
    for code in stock:
        key = code.upper()
        lower_map.setdefault(key, set()).add(code)
    collisions = {k: v for k, v in lower_map.items() if len(v) > 1}
    affected_rows = int(df["StockCode"].isin({c for vs in collisions.values() for c in vs}).sum()) if collisions else 0
    return CheckResult(
        "Consistency", "StockCode casing / whitespace variants for the same product",
        affected_rows, len(df), "Medium",
        "Same product appearing under multiple SKU strings prevents price-history aggregation and splits demand signal.",
    )


@register
def multiple_descriptions_per_sku(df: pd.DataFrame) -> CheckResult:
    grp = df.dropna(subset=["StockCode", "Description"]).groupby("StockCode")["Description"].nunique()
    offending = grp[grp > 1].index
    affected_rows = int(df["StockCode"].isin(offending).sum())
    return CheckResult(
        "Consistency", "StockCodes with multiple distinct descriptions",
        affected_rows, len(df), "Medium",
        "Description drift on the same SKU signals upstream master-data inconsistency and breaks text-based features.",
    )


# ---------- Integrity ----------
@register
def cancellations_without_original(df: pd.DataFrame) -> CheckResult:
    cancels = df[df["Invoice"].fillna("").str.startswith("C")]
    normal_stock_by_customer = df[~df["Invoice"].fillna("").str.startswith("C")].groupby(
        ["Customer ID", "StockCode"]
    )["Quantity"].sum()
    orphan_count = 0
    for _, row in cancels.iterrows():
        key = (row["Customer ID"], row["StockCode"])
        if key not in normal_stock_by_customer.index:
            orphan_count += 1
    return CheckResult(
        "Integrity", "Cancellation rows with no matching original purchase",
        orphan_count, len(df), "High",
        "Unmatched cancellations either inflate returns or indicate lost origin records; either way, net-revenue features will be wrong.",
    )


@register
def negative_quantity_no_cancellation_flag(df: pd.DataFrame) -> CheckResult:
    mask = (df["Quantity"].fillna(0) < 0) & (~df["Invoice"].fillna("").str.startswith("C"))
    failed = int(mask.sum())
    return CheckResult(
        "Integrity", "Negative quantity on non-cancellation invoice",
        failed, len(df), "High",
        "Negative quantities outside the cancellation convention are ambiguous — adjustments, returns, or data errors are indistinguishable.",
    )


# ---------- Anomaly ----------
@register
def non_product_stock_codes(df: pd.DataFrame) -> CheckResult:
    codes = df["StockCode"].fillna("")
    mask = codes.isin(NON_PRODUCT_CODES) | codes.apply(
        lambda s: bool(NON_PRODUCT_REGEX.match(s)) and not re.match(r"^\d{5,6}[A-Za-z]?$", s)
    )
    failed = int(mask.sum())
    sample = df.loc[mask, "StockCode"].value_counts().head(10).to_dict()
    return CheckResult(
        "Anomaly", "Non-product stock codes (POST, DOT, BANK CHARGES, TEST, etc.)",
        failed, len(df), "High",
        "Adjustments and fees share the transactional schema but are not products; leaving them in dominates the loss during training.",
        sample=[sample],
    )


@register
def extreme_price_outliers(df: pd.DataFrame) -> CheckResult:
    valid = df["Price"].dropna()
    cutoff = valid.quantile(0.9999) if len(valid) else 0
    mask = df["Price"].fillna(0) > cutoff
    failed = int(mask.sum())
    return CheckResult(
        "Anomaly", f"Price > 99.99th percentile ({cutoff:.2f})",
        failed, len(df), "Low",
        "A handful of manual-adjustment rows at £10k+ dominate summary statistics and skew log-transformed features.",
    )


# ---------- Runner ----------
def run_all(df: pd.DataFrame) -> pd.DataFrame:
    results = [fn(df) for fn in REGISTRY]
    severity_order = {s: i for i, s in enumerate(SEVERITIES)}
    rows = [r.to_row() for r in results]
    out = pd.DataFrame(rows)
    out["_sev"] = out["Severity"].map(severity_order)
    out = out.sort_values(["_sev", "Failing rows"], ascending=[True, False]).drop(columns="_sev").reset_index(drop=True)
    return out
