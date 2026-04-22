"""Deterministic loader for the UCI Online Retail II dataset.

Reads both sheets of online_retail_II.xlsx, concatenates them into a single
DataFrame, and applies minimal, well-documented normalisation so that downstream
quality checks operate on a consistent schema. No silent cleaning is performed
here — anything that would hide a quality issue belongs in the checks module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "online_retail_II.xlsx"

SHEETS = ("Year 2009-2010", "Year 2010-2011")

SCHEMA = {
    "Invoice": "string",
    "StockCode": "string",
    "Description": "string",
    "Quantity": "Int64",
    "InvoiceDate": "datetime64[ns]",
    "Price": "float64",
    "Customer ID": "Int64",
    "Country": "string",
}


@dataclass
class LoadSummary:
    rows: int
    sheets: dict[str, int]
    date_min: pd.Timestamp
    date_max: pd.Timestamp
    unique_invoices: int
    unique_stock_codes: int
    unique_customers: int
    unique_countries: int


def load(path: Path | str = DATA_PATH) -> pd.DataFrame:
    """Load both sheets, concatenate, and apply type coercion only.

    Adds a ``sheet`` column tagging the source period for traceability.
    Whitespace is stripped from string columns because trailing spaces are
    structurally present in this dataset and would otherwise split unique
    values artificially; the rest of the rawness is preserved.
    """
    path = Path(path)
    frames: list[pd.DataFrame] = []
    for sheet in SHEETS:
        df = pd.read_excel(path, sheet_name=sheet, dtype={"Invoice": str, "StockCode": str})
        df["sheet"] = sheet
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)

    for col in ("Invoice", "StockCode", "Description", "Country"):
        combined[col] = combined[col].astype("string").str.strip()

    combined["Quantity"] = pd.to_numeric(combined["Quantity"], errors="coerce").astype("Int64")
    combined["Price"] = pd.to_numeric(combined["Price"], errors="coerce")
    combined["Customer ID"] = pd.to_numeric(combined["Customer ID"], errors="coerce").astype("Int64")
    combined["InvoiceDate"] = pd.to_datetime(combined["InvoiceDate"], errors="coerce")

    return combined


def summarise(df: pd.DataFrame) -> LoadSummary:
    return LoadSummary(
        rows=len(df),
        sheets=df.groupby("sheet", observed=True).size().to_dict(),
        date_min=df["InvoiceDate"].min(),
        date_max=df["InvoiceDate"].max(),
        unique_invoices=df["Invoice"].nunique(dropna=True),
        unique_stock_codes=df["StockCode"].nunique(dropna=True),
        unique_customers=df["Customer ID"].nunique(dropna=True),
        unique_countries=df["Country"].nunique(dropna=True),
    )
