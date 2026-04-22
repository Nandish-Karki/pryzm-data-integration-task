# Pryzm Solutions — Data Integration Intern Take-Home

Submission by **Nandish Mahadev Karki** · [linkedin.com/in/nandish-karki](https://linkedin.com/in/nandish-karki) · Magdeburg, Germany

## Task

Treat the [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) dataset as a new Pryzm customer's first data handover. Deliver:

1. A data quality assessment.
2. A proposed intake specification.
3. One concrete priority improvement.

## Final deliverable

[`output/Pryzm_DataIntegrationIntern_NandishKarki.pdf`](output/Pryzm_DataIntegrationIntern_NandishKarki.pdf) — 4-page write-up. Source markdown lives at `output/dq_report.md`.

## Headline findings

- **1,067,371 rows** across two sheets (2009-12-01 → 2011-12-09).
- **25.6%** of rows fail at least one High-severity or Blocker check.
- **22.77%** of rows have no `Customer ID`.
- A `currency` column is **absent entirely** across 43 countries of transactions.
- **6.28%** of rows use a StockCode that is only a casing/whitespace variant of another code.
- **39.4%** of rows belong to SKUs whose description drifts across transactions.
- Cancellations + non-product codes together account for **≈8.5%** of nominal gross revenue (£19.29M over two years).

## Layout

```
pryzm_task/
├── README.md
├── requirements.txt
├── data/                      # gitignored — drop online_retail_II.xlsx here
├── notebooks/
│   ├── 01_ingest_and_profile.ipynb
│   └── 02_quality_assessment.ipynb
├── src/
│   ├── load.py                # deterministic loader (both sheets → one DataFrame)
│   ├── dq_checks.py           # 14 checks across 6 quality dimensions
│   ├── intake_schema.py       # executable pandera schema = intake spec
│   └── report.py              # figure rendering
└── output/
    ├── dq_report.md           # the write-up (source)
    ├── dq_results.csv         # severity-ranked check results
    ├── figures/               # PNGs embedded in the PDF
    └── Pryzm_DataIntegrationIntern_NandishKarki.pdf
```

## Reproduce

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# Download the dataset from https://archive.ics.uci.edu/dataset/502/online+retail+ii
# Place online_retail_II.xlsx into ./data/

jupyter nbconvert --to notebook --execute --inplace notebooks/02_quality_assessment.ipynb
```

Every number in the PDF is emitted by `notebooks/02_quality_assessment.ipynb` and saved to `output/dq_results.csv`.

## Design choices (the short version)

- **No silent cleaning in the loader.** Anything that would hide a quality issue belongs in a check, not an ETL shortcut.
- **Every check carries a one-sentence pricing-model-impact statement.** A list of defects is a maintenance chore; a severity-sorted, business-framed register is something onboarding can act on.
- **The intake spec is executable.** Pandera schema in [`src/intake_schema.py`](src/intake_schema.py) validates real customer handovers and fails them on concrete violations — same spec the customer sees as a one-page table.
- **One priority improvement, not five.** Automated cancellation reconciliation + non-product-code filtering ships first because it restores the revenue signal a pricing model would train on.

## PDF rendering (optional)

`pandoc` + Edge headless print-to-pdf is used to render `dq_report.md` → PDF. Not required for reviewing the submission — the PDF is committed.
