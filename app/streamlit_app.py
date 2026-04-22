"""Pryzm Data Integration take-home — interactive companion app.

A thin UI over the same `src/` modules the submission PDF is built on. Lets a
reviewer (a) see the quality assessment run against a sampled version of the
UCI Online Retail II dataset, (b) upload any CSV/XLSX and validate it against
the proposed intake specification, and (c) drill into the check results.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from load import load_sample, summarise  # noqa: E402
from dq_checks import run_all  # noqa: E402
from report import missingness_bar, price_distribution, severity_breakdown  # noqa: E402
from intake_schema import INTAKE_FIELDS_TABLE, INTAKE_SCHEMA, intake_fields_markdown, validate  # noqa: E402


st.set_page_config(
    page_title="Pryzm Data Integration — Take-Home Demo",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_sample() -> pd.DataFrame:
    return load_sample()


@st.cache_data(show_spinner=False)
def get_checks(_df: pd.DataFrame) -> pd.DataFrame:
    return run_all(_df)


def header() -> None:
    st.markdown(
        "### Pryzm Data Integration — Take-Home Companion Demo  \n"
        "**Nandish Karki** · nkarki2791@gmail.com · "
        "[linkedin.com/in/nandish-karki](https://linkedin.com/in/nandish-karki) · Magdeburg, DE"
    )
    st.caption(
        "This app is a thin UI over the same Python modules the PDF submission was built on "
        "(`src/load.py`, `src/dq_checks.py`, `src/intake_schema.py`). "
        "A 50,000-row stratified sample of the UCI Online Retail II dataset is used so the "
        "app fits within free hosting limits — all cancellations and non-product stock codes "
        "are retained verbatim from the full 1.07M-row file."
    )


def tab_summary(df: pd.DataFrame) -> None:
    s = summarise(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows (sample)", f"{s.rows:,}")
    c2.metric("Unique invoices", f"{s.unique_invoices:,}")
    c3.metric("Unique SKUs", f"{s.unique_stock_codes:,}")
    c4.metric("Unique customers", f"{s.unique_customers:,}")

    c5, c6, c7 = st.columns(3)
    c5.metric("Countries", f"{s.unique_countries}")
    c6.metric("Date min", str(s.date_min.date()))
    c7.metric("Date max", str(s.date_max.date()))

    st.markdown("#### Top 10 countries by row count")
    st.dataframe(
        df["Country"].value_counts().head(10).rename_axis("Country").to_frame("rows"),
        use_container_width=True,
    )

    st.markdown("#### Top 15 non-numeric stock codes (fees / adjustments / tests)")
    mask = ~df["StockCode"].fillna("").str.match(r"^\d{5,6}[A-Za-z]?$")
    st.dataframe(
        df.loc[mask, "StockCode"].value_counts().head(15).rename_axis("StockCode").to_frame("rows"),
        use_container_width=True,
    )


def tab_quality(df: pd.DataFrame) -> None:
    dq = get_checks(df)

    counts = dq["Severity"].value_counts().reindex(["Blocker", "High", "Medium", "Low"]).fillna(0).astype(int)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blocker checks", int(counts.get("Blocker", 0)))
    c2.metric("High checks", int(counts.get("High", 0)))
    c3.metric("Medium checks", int(counts.get("Medium", 0)))
    c4.metric("Low checks", int(counts.get("Low", 0)))

    st.markdown("#### Severity-ranked findings")
    st.dataframe(dq, use_container_width=True, hide_index=True)

    st.download_button(
        "Download results as CSV",
        data=dq.to_csv(index=False).encode("utf-8"),
        file_name="dq_results.csv",
        mime="text/csv",
    )

    st.markdown("#### Figures")
    c1, c2 = st.columns(2)
    with c1:
        p = missingness_bar(df, path=ROOT / "output" / "figures" / "missingness_app.png")
        st.image(str(p), use_container_width=True)
    with c2:
        p = severity_breakdown(dq, path=ROOT / "output" / "figures" / "severity_app.png")
        st.image(str(p), use_container_width=True)
    p = price_distribution(df, path=ROOT / "output" / "figures" / "price_distribution_app.png")
    st.image(str(p), use_container_width=True)


def tab_intake_spec() -> None:
    st.markdown(
        "The intake specification is delivered as **(a)** a one-page table for a "
        "non-technical customer and **(b)** an executable pandera schema in "
        "[`src/intake_schema.py`](https://github.com/Nandish-Karki/pryzm-data-integration-task/blob/main/src/intake_schema.py)."
    )
    table = pd.DataFrame(
        INTAKE_FIELDS_TABLE,
        columns=["Field", "Type", "Required?", "Format / Enum", "Example", "Automated check at ingestion"],
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown(
        """
        **Six automated checks run at ingestion**
        1. Schema validation (types, nullability, enums) — pandera.
        2. Range checks: `unit_price ≥ 0`, `quantity ≠ 0`, `invoice_datetime` within the customer's declared business period.
        3. Referential integrity: every cancellation row resolves to an existing `original_invoice_id`.
        4. Duplicate detection on `(invoice_id, line_id)`.
        5. SKU normalisation audit — report casing / whitespace variants; fuzzy near-duplicates for v2.
        6. Volume sanity bounds — row count and date span checked against the customer's declared onboarding form.
        """
    )


def _expected_columns() -> list[str]:
    return list(INTAKE_SCHEMA.columns.keys())


def _sample_valid_row() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "invoice_id": "INV-0001",
            "line_id": "1",
            "sku_id": "SKU-22423",
            "product_description": "WHITE HANGING HEART T-LIGHT HOLDER",
            "quantity": 6,
            "unit_price": 2.55,
            "currency": "GBP",
            "invoice_datetime": pd.Timestamp("2010-12-01T08:26:00"),
            "customer_id": "17850",
            "country": "GB",
            "is_cancellation": False,
            "original_invoice_id": None,
        }
    ])


def _sample_raw_row() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "invoice_id": "536365",
            "line_id": "1",
            "sku_id": "85123a",
            "product_description": "WHITE HANGING HEART T-LIGHT HOLDER",
            "quantity": 0,
            "unit_price": -1.5,
            "currency": "gbp",
            "invoice_datetime": pd.Timestamp("2010-12-01T08:26:00"),
            "customer_id": "17850",
            "country": "United Kingdom",
            "is_cancellation": False,
            "original_invoice_id": None,
        }
    ])


def tab_validator() -> None:
    st.markdown(
        "Upload a CSV or XLSX that follows the 12-field intake spec above, or click one of "
        "the sample buttons to see the schema accept a valid row and reject a raw row."
    )

    b1, b2, _ = st.columns([1, 1, 2])
    use_valid = b1.button("Load a valid sample row")
    use_raw = b2.button("Load a raw (intentionally broken) row")

    upload = st.file_uploader(
        "Upload CSV or XLSX",
        type=["csv", "xlsx"],
        help="Columns expected: " + ", ".join(_expected_columns()),
    )

    df: pd.DataFrame | None = None
    source = None
    if use_valid:
        df = _sample_valid_row()
        source = "Valid sample row"
    elif use_raw:
        df = _sample_raw_row()
        source = "Raw sample row (expected to fail)"
    elif upload is not None:
        try:
            if upload.name.lower().endswith(".csv"):
                df = pd.read_csv(upload)
            else:
                df = pd.read_excel(upload)
            source = upload.name
        except Exception as exc:
            st.error(f"Could not read {upload.name}: {exc}")
            return

    if df is None:
        st.info("No file uploaded yet. Click a sample button or upload a file to validate.")
        return

    st.markdown(f"**Source:** `{source}`  —  {len(df):,} row(s), {df.shape[1]} column(s)")
    st.dataframe(df.head(20), use_container_width=True)

    ok, msg = validate(df)
    if ok:
        st.success("Intake schema PASSED — dataframe conforms to the spec.")
    else:
        st.error("Intake schema FAILED — row-level violations below.")
        st.code(msg, language="text")


def tab_about() -> None:
    st.markdown(
        f"""
        #### Submission links
        - **PDF write-up:** [`output/Pryzm_DataIntegrationIntern_NandishKarki.pdf`](https://github.com/Nandish-Karki/pryzm-data-integration-task/blob/main/output/Pryzm_DataIntegrationIntern_NandishKarki.pdf) — the primary deliverable.
        - **Repository:** [github.com/Nandish-Karki/pryzm-data-integration-task](https://github.com/Nandish-Karki/pryzm-data-integration-task).
        - **Notebook that produces every number in the PDF:** [`notebooks/02_quality_assessment.ipynb`](https://github.com/Nandish-Karki/pryzm-data-integration-task/blob/main/notebooks/02_quality_assessment.ipynb).

        #### What this app is
        A thin Streamlit companion to the PDF submission. It exists so the review team can
        interact with the checks and the intake schema rather than just read about them.
        All the real logic lives in three files in `src/`; this app is ~200 lines of wiring.

        #### Why the sample
        Streamlit Community Cloud caps memory at 1 GB. Loading the full 1.07M-row XLSX on
        every cold start is wasteful and the interaction would not change. The sample keeps
        every cancellation and every non-product stock code from the source file so the
        quality-assessment tab is still representative — the headline figures shift by a
        percentage point or two, no more.

        #### Contact
        nkarki2791@gmail.com · +49 15510822713 · Magdeburg, Germany
        """
    )


def main() -> None:
    header()
    df = get_sample()

    tabs = st.tabs(
        ["📋 Dataset summary", "🔎 Quality assessment", "📐 Intake specification", "✅ Validator", "ℹ️ About"]
    )
    with tabs[0]:
        tab_summary(df)
    with tabs[1]:
        tab_quality(df)
    with tabs[2]:
        tab_intake_spec()
    with tabs[3]:
        tab_validator()
    with tabs[4]:
        tab_about()


if __name__ == "__main__":
    main()
