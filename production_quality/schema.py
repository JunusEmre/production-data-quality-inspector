"""Pandera schema for the production-data contract.

The schema is the machine-readable version of ``VALIDATION_RULES``. Allowed
values and required columns come from ``PRODUCTION_DATA_CONFIG``; they are not
repeated here as independent literals.

Coercion and preparation
------------------------
Pandera is **not** asked to coerce mixed text such as ``unknown``, ``fast``,
or ``2026-02-30`` into numeric or datetime dtypes during failure collection.
Those values would either raise during coercion or be turned into missing
values, which would hide a type problem as a blank.

Instead, column types stay flexible (no strict dtype). Named custom checks
inspect the original cells:

- Unparseable text in a numeric column fails that column's range rule.
- ``2026-02-30`` fails ``VALID_PRODUCTION_DATE``.
- Cross-column checks convert with ``errors='coerce'`` only to decide whether
  a comparison is safe. Rows with non-numeric cells are skipped so they are
  reported by the type/range rule, not by a misleading balance failure.

Blank and whitespace-only cells may be turned into missing values on a
**defensive copy** before ``schema.validate`` runs. That is presence
preparation, not business-value repair. The caller's DataFrame is never
changed.

When every Error rule passes, the validation service may then coerce dates
and numeric columns on the successful copy so callers receive typed data.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.rules import RULES_BY_ID


def build_production_schema(
    config: ProductionDataConfig = PRODUCTION_DATA_CONFIG,
) -> pa.DataFrameSchema:
    """Return the Pandera schema for one production extract."""

    columns = {
        "record_id": pa.Column(
            nullable=False,
            unique=True,
            required=True,
            report_duplicates="all",
            description=RULES_BY_ID["RECORD_ID_PRESENT"].description,
        ),
        "production_date": pa.Column(
            nullable=False,
            required=True,
            checks=[_named_check("VALID_PRODUCTION_DATE", _is_valid_date)],
        ),
        "plant": pa.Column(
            nullable=False,
            required=True,
            description=RULES_BY_ID["PLANT_PRESENT"].description,
        ),
        "production_line": pa.Column(
            nullable=False,
            required=True,
            checks=[
                pa.Check.isin(
                    _sorted_values(config.allowed_production_lines),
                    **_check_kwargs("VALID_PRODUCTION_LINE"),
                )
            ],
        ),
        "machine_id": pa.Column(
            nullable=False,
            required=True,
            checks=[
                pa.Check.isin(
                    _sorted_values(config.allowed_machine_ids),
                    **_check_kwargs("VALID_MACHINE_ID"),
                )
            ],
        ),
        "shift": pa.Column(
            nullable=False,
            required=True,
            checks=[
                pa.Check.isin(
                    _sorted_values(config.allowed_shifts),
                    **_check_kwargs("VALID_SHIFT"),
                )
            ],
        ),
        "product_code": pa.Column(
            nullable=False,
            required=True,
            checks=[
                pa.Check.isin(
                    _sorted_values(config.allowed_product_codes),
                    **_check_kwargs("VALID_PRODUCT_CODE"),
                )
            ],
        ),
        "produced_quantity": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check(
                    "PRODUCED_QUANTITY_RANGE",
                    _numeric_at_least(0),
                )
            ],
        ),
        "good_quantity": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check("GOOD_QUANTITY_RANGE", _numeric_at_least(0)),
            ],
        ),
        "scrap_quantity": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check("SCRAP_QUANTITY_RANGE", _numeric_at_least(0)),
            ],
        ),
        "downtime_minutes": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check("DOWNTIME_MINUTES_RANGE", _numeric_at_least(0)),
            ],
        ),
        "planned_minutes": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check("PLANNED_MINUTES_RANGE", _numeric_greater_than(0)),
            ],
        ),
        "cycle_time_seconds": pa.Column(
            nullable=False,
            required=True,
            checks=[
                _named_check("CYCLE_TIME_RANGE", _numeric_greater_than(0)),
            ],
        ),
    }
    missing = [
        name for name in config.required_columns if name not in columns
    ]
    unexpected = [
        name for name in columns if name not in config.required_columns
    ]
    if missing or unexpected:
        raise ValueError(
            "Schema columns must match ProductionDataConfig.required_columns."
        )

    ordered_columns = {name: columns[name] for name in config.required_columns}
    return pa.DataFrameSchema(
        columns=ordered_columns,
        checks=[
            _named_check("NONEMPTY_DATASET", _has_production_rows),
            _named_check("QUANTITY_BALANCE", _quantity_balance_holds),
            _named_check("DOWNTIME_WITHIN_PLAN", _downtime_within_plan),
        ],
        strict=False,
        coerce=False,
        unique_column_names=True,
        name="production_data",
    )


def _sorted_values(values: frozenset[str]) -> list[str]:
    return sorted(values)


def _check_kwargs(rule_id: str) -> dict[str, str]:
    rule = RULES_BY_ID[rule_id]
    return {
        "name": rule.rule_id,
        "error": rule.rule_id,
        "title": rule.title,
        "description": rule.description,
    }


def _named_check(rule_id: str, check_fn) -> pa.Check:
    kwargs = _check_kwargs(rule_id)
    return pa.Check(check_fn, **kwargs)


def _has_production_rows(frame: pd.DataFrame) -> bool:
    return len(frame) >= 1


def _is_valid_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").notna()


def _numeric_at_least(minimum: float):
    def check(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.notna() & (numeric >= minimum)

    return check


def _numeric_greater_than(minimum: float):
    def check(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.notna() & (numeric > minimum)

    return check


def _quantity_balance_holds(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(True, index=frame.index)
    needed = ("produced_quantity", "good_quantity", "scrap_quantity")
    if any(column not in frame.columns for column in needed):
        return result
    produced = pd.to_numeric(frame["produced_quantity"], errors="coerce")
    good = pd.to_numeric(frame["good_quantity"], errors="coerce")
    scrap = pd.to_numeric(frame["scrap_quantity"], errors="coerce")
    comparable = produced.notna() & good.notna() & scrap.notna()
    result.loc[comparable] = (good[comparable] + scrap[comparable]) <= produced[
        comparable
    ]
    return result


def _downtime_within_plan(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(True, index=frame.index)
    needed = ("downtime_minutes", "planned_minutes")
    if any(column not in frame.columns for column in needed):
        return result
    downtime = pd.to_numeric(frame["downtime_minutes"], errors="coerce")
    planned = pd.to_numeric(frame["planned_minutes"], errors="coerce")
    comparable = downtime.notna() & planned.notna()
    result.loc[comparable] = downtime[comparable] <= planned[comparable]
    return result
