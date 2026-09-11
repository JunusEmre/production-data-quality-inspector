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
3. Cross-check the same rules with a manual pandas validator for teaching.
4. Summarize issues for a production audience in a Streamlit dashboard.

The dashboard and a quality score are not built yet.

## Current status: Stage 2

Stage 2 adds the complete validation engine:

- A Pandera schema built from the existing production-data contract.
- `validate_with_pandera` / `validate_file_with_pandera` as the production API.
- Direct (`lazy=False`) and lazy (`lazy=True`) validation.
- `ValidationIssue` and `ValidationResult` records for later reporting.
- A manual pandas validator used only as an educational comparison.

Stage 2 does **not** include a quality score or a Streamlit dashboard.

## How the validation engine works

1. `load_production_data` reads the CSV and keeps raw values.
2. Extra columns are reported as `UNEXPECTED_COLUMNS` warnings.
3. The Pandera schema checks the remaining 18 Error rules.
4. Findings are mapped onto the existing `VALIDATION_RULES` catalog.
5. The original DataFrame is never mutated. `validated_data` is returned only when there are no Error issues.

```python
from production_quality import load_production_data, validate_file_with_pandera

result = validate_file_with_pandera("data/production_data.csv", lazy=True)
print(result.is_valid, result.error_count, result.warning_count)
print(result.issues_frame().head())
```

## Direct and lazy validation

- **Direct** validation (`lazy=False`) reports extra-column warnings plus the first Pandera Error. Use it when a fast fail is enough.
- **Lazy** validation (`lazy=True`, the default) collects independent Errors across the batch. Use it for a complete incoming-file inspection.

Warnings alone do not make `is_valid` false.

## Pandera versus manual comparison

Pandera is the future application engine. `validate_with_pandas` repeats the same 19 business rules with handwritten pandas so the two approaches can be compared in tests and in [docs/pandera_vs_manual.md](docs/pandera_vs_manual.md). The pandas function must not be used as a second production engine.

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
3. Validation rules check structure, allowed values, numeric ranges, and cross-column totals.
4. Later, a dashboard will show which rules failed and which rows need attention.

Steps 1–3 are in place. Step 4 comes in a later stage.

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
│   ├── pandera_vs_manual.md
│   └── validation_rules.md
├── production_quality/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── exceptions.py
│   ├── manual_validation.py
│   ├── models.py
│   ├── rules.py
│   ├── schema.py
│   └── validation.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_data.py
│   ├── test_manual_validation.py
│   ├── test_models.py
│   ├── test_rules.py
│   ├── test_schema.py
│   ├── test_validation.py
│   └── test_validator_comparison.py
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

Most tests use small controlled DataFrames. They do not write into `data/`.

## Current limitations

- There is no Streamlit dashboard yet.
- There is no overall quality score.
- Invalid source values are reported, not repaired.
- Extra columns are warnings; they are not dropped from the file.

## Technologies

- **Python** for the application
- **pandas** for loading and the educational comparison validator
- **Pandera** for the production schema and validation engine
- **pytest** for automated tests
- **Streamlit** for a later dashboard, not included in Stage 2

## Data notice

`data/production_data.csv` is synthetic manufacturing data created for teaching and portfolio demonstration. It contains no confidential production information.
