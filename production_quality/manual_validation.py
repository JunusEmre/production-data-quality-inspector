"""Manual pandas comparison validator.

This module exists so students and reviewers can see how much handwritten
code is needed to express the same 19 production rules without Pandera.

It is **not** the production engine. Later application workflow, including
the Streamlit dashboard, should call the Pandera validation service. This
file must not import Pandera or that service.
"""

from __future__ import annotations

import pandas as pd

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.models import (
    ValidationIssue,
    ValidationResult,
    unique_sorted_issues,
)


def validate_with_pandas(
    data: pd.DataFrame,
    *,
    config: ProductionDataConfig = PRODUCTION_DATA_CONFIG,
) -> ValidationResult:
    """Validate a production DataFrame with ordinary pandas checks."""

    original = data.copy(deep=True)
    working = _blank_strings_to_na(data.copy(deep=True))
    issues: list[ValidationIssue] = []

    issues.extend(_required_column_issues(working, config))
    issues.extend(_unexpected_column_issues(working, config))
    if len(working) == 0:
        issues.append(ValidationIssue.from_rule("NONEMPTY_DATASET"))

    if "record_id" in working.columns:
        issues.extend(_blank_issues(original, working, "record_id", "RECORD_ID_PRESENT"))
        issues.extend(_duplicate_record_id_issues(original, working))
    if "production_date" in working.columns:
        issues.extend(_invalid_date_issues(original, working))
    if "plant" in working.columns:
        issues.extend(_blank_issues(original, working, "plant", "PLANT_PRESENT"))
    if "production_line" in working.columns:
        issues.extend(
            _category_issues(
                original,
                working,
                "production_line",
                config.allowed_production_lines,
                "VALID_PRODUCTION_LINE",
            )
        )
    if "machine_id" in working.columns:
        issues.extend(
            _category_issues(
                original,
                working,
                "machine_id",
                config.allowed_machine_ids,
                "VALID_MACHINE_ID",
            )
        )
    if "shift" in working.columns:
        issues.extend(
            _category_issues(
                original,
                working,
                "shift",
                config.allowed_shifts,
                "VALID_SHIFT",
            )
        )
    if "product_code" in working.columns:
        issues.extend(
            _category_issues(
                original,
                working,
                "product_code",
                config.allowed_product_codes,
                "VALID_PRODUCT_CODE",
            )
        )

    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "produced_quantity",
            "PRODUCED_QUANTITY_RANGE",
            minimum=0,
            strict=False,
        )
    )
    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "good_quantity",
            "GOOD_QUANTITY_RANGE",
            minimum=0,
            strict=False,
        )
    )
    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "scrap_quantity",
            "SCRAP_QUANTITY_RANGE",
            minimum=0,
            strict=False,
        )
    )
    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "downtime_minutes",
            "DOWNTIME_MINUTES_RANGE",
            minimum=0,
            strict=False,
        )
    )
    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "planned_minutes",
            "PLANNED_MINUTES_RANGE",
            minimum=0,
            strict=True,
        )
    )
    issues.extend(
        _numeric_range_issues(
            original,
            working,
            "cycle_time_seconds",
            "CYCLE_TIME_RANGE",
            minimum=0,
            strict=True,
        )
    )
    issues.extend(_quantity_balance_issues(original, working))
    issues.extend(_downtime_plan_issues(original, working))

    ordered = unique_sorted_issues(issues)
    has_error = any(issue.severity == "Error" for issue in ordered)
    validated = None if has_error else original.copy(deep=True)
    return ValidationResult(
        issues=ordered,
        validated_data=validated,
        validation_mode="manual",
        validator_name="Pandas",
    )


def _required_column_issues(
    frame: pd.DataFrame,
    config: ProductionDataConfig,
) -> list[ValidationIssue]:
    present = set(frame.columns)
    return [
        ValidationIssue.from_rule(
            "REQUIRED_COLUMNS",
            column=column,
            failure_value=column,
        )
        for column in config.required_columns
        if column not in present
    ]


def _unexpected_column_issues(
    frame: pd.DataFrame,
    config: ProductionDataConfig,
) -> list[ValidationIssue]:
    required = set(config.required_columns)
    return [
        ValidationIssue.from_rule(
            "UNEXPECTED_COLUMNS",
            column=str(column),
            failure_value=str(column),
        )
        for column in frame.columns
        if column not in required
    ]


def _blank_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
    column: str,
    rule_id: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for row_index in working.index[working[column].isna()]:
        issues.append(
            ValidationIssue.from_rule(
                rule_id,
                column=column,
                row_index=_as_row_index(row_index),
                failure_value=_original_value(original, row_index, column),
            )
        )
    return issues


def _duplicate_record_id_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
) -> list[ValidationIssue]:
    series = working["record_id"]
    duplicated = series.notna() & series.duplicated(keep=False)
    issues: list[ValidationIssue] = []
    for row_index in working.index[duplicated]:
        issues.append(
            ValidationIssue.from_rule(
                "UNIQUE_RECORD_ID",
                column="record_id",
                row_index=_as_row_index(row_index),
                failure_value=_original_value(original, row_index, "record_id"),
            )
        )
    return issues


def _invalid_date_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
) -> list[ValidationIssue]:
    parsed = pd.to_datetime(working["production_date"], errors="coerce")
    invalid = working["production_date"].isna() | parsed.isna()
    issues: list[ValidationIssue] = []
    for row_index in working.index[invalid]:
        issues.append(
            ValidationIssue.from_rule(
                "VALID_PRODUCTION_DATE",
                column="production_date",
                row_index=_as_row_index(row_index),
                failure_value=_original_value(original, row_index, "production_date"),
            )
        )
    return issues


def _category_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
    column: str,
    allowed: frozenset[str],
    rule_id: str,
) -> list[ValidationIssue]:
    series = working[column]
    invalid = series.isna() | ~series.isin(allowed)
    issues: list[ValidationIssue] = []
    for row_index in working.index[invalid]:
        issues.append(
            ValidationIssue.from_rule(
                rule_id,
                column=column,
                row_index=_as_row_index(row_index),
                failure_value=_original_value(original, row_index, column),
            )
        )
    return issues


def _numeric_range_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
    column: str,
    rule_id: str,
    *,
    minimum: float,
    strict: bool,
) -> list[ValidationIssue]:
    if column not in working.columns:
        return []
    numeric = pd.to_numeric(working[column], errors="coerce")
    if strict:
        invalid = working[column].isna() | numeric.isna() | (numeric <= minimum)
    else:
        invalid = working[column].isna() | numeric.isna() | (numeric < minimum)
    issues: list[ValidationIssue] = []
    for row_index in working.index[invalid]:
        issues.append(
            ValidationIssue.from_rule(
                rule_id,
                column=column,
                row_index=_as_row_index(row_index),
                failure_value=_original_value(original, row_index, column),
            )
        )
    return issues


def _quantity_balance_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
) -> list[ValidationIssue]:
    needed = ("produced_quantity", "good_quantity", "scrap_quantity")
    if any(column not in working.columns for column in needed):
        return []
    produced = pd.to_numeric(working["produced_quantity"], errors="coerce")
    good = pd.to_numeric(working["good_quantity"], errors="coerce")
    scrap = pd.to_numeric(working["scrap_quantity"], errors="coerce")
    comparable = produced.notna() & good.notna() & scrap.notna()
    failed = comparable & ((good + scrap) > produced)
    return [
        ValidationIssue.from_rule(
            "QUANTITY_BALANCE",
            row_index=_as_row_index(row_index),
            failure_value=_row_values(original, row_index, needed),
        )
        for row_index in working.index[failed]
    ]


def _downtime_plan_issues(
    original: pd.DataFrame,
    working: pd.DataFrame,
) -> list[ValidationIssue]:
    needed = ("downtime_minutes", "planned_minutes")
    if any(column not in working.columns for column in needed):
        return []
    downtime = pd.to_numeric(working["downtime_minutes"], errors="coerce")
    planned = pd.to_numeric(working["planned_minutes"], errors="coerce")
    comparable = downtime.notna() & planned.notna()
    failed = comparable & (downtime > planned)
    return [
        ValidationIssue.from_rule(
            "DOWNTIME_WITHIN_PLAN",
            row_index=_as_row_index(row_index),
            failure_value=_row_values(original, row_index, needed),
        )
        for row_index in working.index[failed]
    ]


def _blank_strings_to_na(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy(deep=True)
    for column in working.columns:
        series = working[column]
        if not (series.dtype == object or pd.api.types.is_string_dtype(series)):
            continue
        as_string = series.astype("string")
        blank = as_string.isna() | as_string.str.strip().eq("")
        working.loc[blank, column] = pd.NA
    return working


def _original_value(frame: pd.DataFrame, row_index: object, column: str) -> object | None:
    if column not in frame.columns or row_index not in frame.index:
        return None
    return _normalize_failure_value(frame.loc[row_index, column])


def _row_values(
    frame: pd.DataFrame,
    row_index: object,
    columns: tuple[str, ...],
) -> dict[str, object] | None:
    if row_index not in frame.index:
        return None
    return {
        column: _original_value(frame, row_index, column)
        for column in columns
        if column in frame.columns
    }


def _as_row_index(value: object) -> int | str:
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return str(value)


def _normalize_failure_value(value: object) -> object | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value
    return value
