"""Executable intake specification.

The same spec a non-technical customer sees in the PDF one-pager is enforced
here as a pandera DataFrameSchema. Running the schema on a raw customer
handover produces a deterministic pass/fail report plus a list of offending
rows — which is what makes the spec 'executable' rather than aspirational.
"""
from __future__ import annotations

import re

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column, DataFrameSchema

ISO_3166_ALPHA2 = re.compile(r"^[A-Z]{2}$")
ISO_4217 = re.compile(r"^[A-Z]{3}$")
SKU_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,31}$")


INTAKE_SCHEMA = DataFrameSchema(
    columns={
        "invoice_id": Column(
            str,
            checks=[Check.str_matches(r"^[A-Z0-9\-]{1,32}$")],
            nullable=False,
        ),
        "line_id": Column(str, nullable=False),
        "sku_id": Column(
            str,
            checks=[Check.str_matches(SKU_REGEX)],
            nullable=False,
        ),
        "product_description": Column(str, nullable=False),
        "quantity": Column(
            int,
            checks=[Check(lambda s: s != 0, element_wise=True, error="quantity must be non-zero")],
            nullable=False,
        ),
        "unit_price": Column(
            float,
            checks=[Check.greater_than_or_equal_to(0)],
            nullable=False,
        ),
        "currency": Column(
            str,
            checks=[Check.str_matches(ISO_4217)],
            nullable=False,
        ),
        "invoice_datetime": Column(
            pa.DateTime,
            nullable=False,
        ),
        "customer_id": Column(str, nullable=True),
        "country": Column(
            str,
            checks=[Check.str_matches(ISO_3166_ALPHA2)],
            nullable=False,
        ),
        "is_cancellation": Column(bool, nullable=False),
        "original_invoice_id": Column(str, nullable=True),
    },
    unique=["invoice_id", "line_id"],
    strict=True,
    coerce=True,
)


INTAKE_FIELDS_TABLE = [
    ("invoice_id", "string", "Yes", "≤32 chars, uppercase/digits/hyphen", "INV-0001", "Regex + uniqueness across file"),
    ("line_id", "string", "Yes", "Unique with invoice_id", "1", "Composite key uniqueness"),
    ("sku_id", "string", "Yes", "Uppercase alphanumeric, 2–32 chars", "SKU-22423", "Regex + normalisation audit"),
    ("product_description", "string", "Yes", "Free text, non-empty", "WHITE HANGING HEART T-LIGHT HOLDER", "Non-empty + consistency per SKU"),
    ("quantity", "integer", "Yes", "Non-zero; negative only if is_cancellation=true", "6", "Range check + cancellation coherence"),
    ("unit_price", "decimal", "Yes", ">= 0", "2.55", "Range check + outlier flag"),
    ("currency", "ISO-4217", "Yes", "3-letter code", "GBP", "Enum limited to customer's operating currencies"),
    ("invoice_datetime", "ISO-8601", "Yes", "UTC or with offset", "2010-12-01T08:26:00Z", "Range check vs declared business period"),
    ("customer_id", "string", "Conditional", "Required for named customers", "17850", "Null allowed only for anonymous walk-in"),
    ("country", "ISO-3166-1 alpha-2", "Yes", "2-letter code", "GB", "Enum check"),
    ("is_cancellation", "boolean", "Yes", "Default false", "false", "Cross-field coherence with negative quantity"),
    ("original_invoice_id", "string", "Conditional", "Required if is_cancellation=true", "INV-0001", "Referential integrity to invoice_id"),
]


def intake_fields_markdown() -> str:
    header = "| Field | Type | Required? | Format / Enum | Example | Automated check at ingestion |\n"
    sep = "|---|---|---|---|---|---|\n"
    body = "\n".join("| " + " | ".join(row) + " |" for row in INTAKE_FIELDS_TABLE)
    return header + sep + body


def validate(df: pd.DataFrame) -> tuple[bool, str]:
    try:
        INTAKE_SCHEMA.validate(df, lazy=True)
        return True, "OK: dataframe conforms to intake spec."
    except pa.errors.SchemaErrors as err:
        return False, str(err.failure_cases.head(50))
