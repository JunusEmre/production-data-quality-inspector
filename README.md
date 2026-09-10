# Production Data Quality Inspector

A Python application that inspects manufacturing production extracts, finds data-quality problems, and will later present those findings in a Streamlit dashboard.

This is Assignment 2. It is a new project and does not reuse the Assignment 1 order-reporting application.

## The manufacturing problem

Production managers rely on daily machine extracts to understand output, scrap, and downtime. Those files are only useful when the basics are trustworthy: every row has an ID, dates are real calendar days, quantities are numbers, good plus scrap does not exceed total output, and downtime fits inside the planned run.

When an extract contains blank IDs, unknown machines, text in quantity fields, or impossible totals, reports become misleading. This project inspects that extract before anyone treats it as a production result.

## What this project will eventually do

The finished application will:

1. Load a production CSV without silently repairing bad values.
2. Apply agreed business rules with Pandera.
3. Cross-check the same rules with a manual pandas validator.
4. Summarize issues for a production audience in a Streamlit dashboard.

Those later pieces are not built yet.

## Current status: Stage 1

Stage 1 provides the project foundation only:

- Safe CSV loading that preserves raw values.
- A frozen configuration for required columns and allowed business values.
- A human-readable catalog of 19 validation rules.
- Dataset inspection notes for the synthetic production file.
- Automated tests for configuration, rules, and loading.

Stage 1 does **not** include a Pandera schema, a manual pandas validator, a quality score, or a Streamlit dashboard.

## Dataset overview

The working extract is `data/production_data.csv`.

- About 1,200 synthetic manufacturing rows.
- 13 columns: record_id, production_date, plant, production_line, machine_id, shift, product_code, produced_quantity, good_quantity, scrap_quantity, downtime_minutes, planned_minutes, and cycle_time_seconds.
- The file includes some valid boundary values, such as zero downtime, and some invalid values on purpose.
- Those planted errors are part of the demonstration and must not be cleaned out of the CSV.

The dataset is synthetic and contains no confidential production information. A full inspection is recorded in [docs/data_profile.md](docs/data_profile.md).

## Planned user workflow

1. A production extract is received as CSV.
2. The application loads the file without changing suspect values.
3. Later, validation rules check structure, allowed values, numeric ranges, and cross-column totals.
4. Later, a dashboard will show which rules failed and which rows need attention.

Today, only steps 1 and 2 and the written rule catalog are in place.

## Validation-rule summary

The 19 agreed rules are documented in [docs/validation_rules.md](docs/validation_rules.md). In short:

- The file must contain the 13 required columns, no unnoticed extra columns, and at least one production row.
- Record IDs must be present and unique.
- Dates, plant, line, machine, shift, and product must be usable business values.
- Quantity and time fields must be numeric and inside the agreed ranges.
- Good plus scrap must not exceed produced quantity.
- Downtime must not exceed planned minutes.

Field meanings are listed in [docs/data_dictionary.md](docs/data_dictionary.md).

## Current project structure

```text
production-data-quality-inspector/
├── data/
│   └── production_data.csv
├── docs/
│   ├── data_dictionary.md
│   ├── data_profile.md
│   └── validation_rules.md
├── production_quality/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── exceptions.py
│   └── rules.py
├── tests/
│   ├── test_config.py
│   ├── test_data.py
│   └── test_rules.py
├── README.md
└── requirements.txt
```

## Installation

Use Python 3.11 or later. From the project root:

```bash
python -m pip install -r requirements.txt
```

Required packages are pandas, Pandera, and pytest.

## How to run the tests

From the project root:

```bash
python -m pytest -q
```

Tests use temporary files and in-memory CSV examples. They do not write into `data/`.

## Technologies

- **Python** for the application
- **pandas** for loading and later inspection
- **Pandera** for schema validation in a later stage
- **pytest** for automated tests
- **Streamlit** for a later dashboard, not included in Stage 1

## Data notice

`data/production_data.csv` is synthetic manufacturing data created for teaching and portfolio demonstration. It contains no confidential production information.
