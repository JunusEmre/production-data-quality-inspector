# Production Data Quality Inspector

A Python application that inspects manufacturing production extracts, finds data-quality problems, and presents those findings in an English Streamlit dashboard.

This is Assignment 2. It is a new project and does not reuse the Assignment 1 order-reporting application.

## The manufacturing problem

Production managers rely on daily machine extracts to understand output, scrap, and downtime. Those files are only useful when the basics are trustworthy: every row has an ID, dates are real calendar days, quantities are numbers, good plus scrap does not exceed total output, and downtime fits inside the planned run.

When an extract contains blank IDs, unknown machines, text in quantity fields, or impossible totals, reports become misleading. This project inspects that extract before anyone treats it as a production result.

## Current status: Stage 3

Stage 3 adds the dashboard and the row-cleanliness score:

- Upload a CSV or use the synthetic demonstration file.
- Run complete/lazy Pandera validation as the production inspection.
- See status, score, issues, affected records, and the 19-rule contract.
- Compare Pandera direct, Pandera complete, and manual Pandas in a separate tab.
- Download in-memory CSV reports.

The application does not repair source data, save uploads, or deploy to the cloud. Presentation slides come later.

## Screenshots

Dashboard screenshots will be added when the final documentation pack is prepared. Do not expect screenshot files in this repository yet.

## Application workflow

```mermaid
flowchart LR
    A[Choose source] --> B[Load without repair]
    B --> C[Pandera complete validation]
    C --> D[Quality result]
    D --> E[Investigate and download]
```

1. Choose a data source: upload a CSV or use the demonstration dataset.
2. Preview the extract. Previewing does not change values.
3. Run quality inspection.
4. Read the status and row-cleanliness score.
5. Investigate issues, affected records, and the rulebook.
6. Download the reports.

## Dashboard tabs

- **Overview** — status, Error findings chart, and the most frequent problems.
- **Issues** — complete findings with severity, rule, and field filters.
- **Affected records** — original source rows connected to Errors, not repaired.
- **Rulebook** — all 19 contract rules and the current result for each.
- **Validation comparison** — educational view of Pandera direct, Pandera complete, and manual Pandas.
- **Downloads** — in-memory CSV reports.

## Quality-score explanation

The row-cleanliness score is the percentage of rows with no Error findings:

`score = round((clean_rows / total_rows) * 100, 2)`

Warnings do not reduce the score. Any Error still makes the file invalid. A structurally broken file, such as one with missing required columns, is **Not scorable**. Details are in [docs/quality_score.md](docs/quality_score.md).

On the demonstration file the expected main result is:

- Total rows: 1,200
- Affected rows: 17
- Clean rows: 1,183
- Row-cleanliness score: 98.58%
- Error findings: 18
- Warning findings: 0
- Status: Issues found

The score shows how many rows have no Error findings. The file is still not approved while any Error remains.

## Pandera as the production engine

The dashboard inspection button calls `validate_with_pandera(data, lazy=True)`. That complete/lazy scan is the application engine used for status, score, issues, and downloads.

## Pandas comparison as educational only

The **Validation comparison** tab also runs Pandera direct validation and `validate_with_pandas`. The pandas path exists to show how much handwritten checking the schema avoids. It does not power the main inspection.

## Dataset overview

The working extract is `data/production_data.csv`.

- About 1,200 synthetic manufacturing rows.
- 13 columns covering identity, plant, machine, product, quantities, and time.
- Valid boundary values and planted invalid values are both present on purpose.
- Those planted errors must not be cleaned out of the CSV.

The dataset is synthetic and contains no confidential production information. A full inspection is recorded in [docs/data_profile.md](docs/data_profile.md).

## Installation

Use Python 3.11 or later. From the project root:

```bash
python -m pip install -r requirements.txt
```

Required packages are pandas, Pandera, pytest, and Streamlit.

## How to run the dashboard

```bash
python -m streamlit run streamlit_app.py
```

## How to run the tests

```bash
python -m pytest -q
```

Most tests use small controlled DataFrames. They do not write into `data/`.

## Current project structure

```text
production-data-quality-inspector/
├── .streamlit/
│   └── config.toml
├── data/
│   └── production_data.csv
├── docs/
│   ├── data_dictionary.md
│   ├── data_profile.md
│   ├── pandera_vs_manual.md
│   ├── quality_score.md
│   └── validation_rules.md
├── production_quality/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── exceptions.py
│   ├── manual_validation.py
│   ├── models.py
│   ├── quality.py
│   ├── reporting.py
│   ├── rules.py
│   ├── schema.py
│   └── validation.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_data.py
│   ├── test_manual_validation.py
│   ├── test_models.py
│   ├── test_quality.py
│   ├── test_reporting.py
│   ├── test_rules.py
│   ├── test_schema.py
│   ├── test_streamlit_app.py
│   ├── test_validation.py
│   └── test_validator_comparison.py
├── README.md
├── requirements.txt
└── streamlit_app.py
```

## Downloaded reports

Downloads are built in memory from the current inspection:

- `quality_summary.csv` — status, score, and counts
- `quality_issues.csv` — finding-level report
- `affected_records.csv` — original Error-affected source rows
- `validation_rule_summary.csv` — all 19 rules and current results

There is no “cleaned dataset” download because the application does not repair source data.

## Privacy

Uploaded CSVs are read in memory and passed to the existing loader. They are not permanently saved. Closing the session discards the upload.

## Data notice

`data/production_data.csv` is synthetic manufacturing data created for teaching and portfolio demonstration. It contains no confidential production information.

## Current limitations

- Invalid source values are reported, not repaired.
- Extra columns are warnings; they are not dropped from the file.
- There is no cloud deployment, authentication, or database.
- Presentation slides and screenshot files come later.

## Technologies

- **Python** for the application
- **pandas** for loading and the educational comparison validator
- **Pandera** for the production schema and validation engine
- **pytest** for automated tests
- **Streamlit** for the English dashboard
