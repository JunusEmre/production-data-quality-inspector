"""Pandera validation service for production extracts.

This is the production engine that later stages, including Streamlit, should
call. Extra columns are classified here as Warning using the shared rule
catalog because Pandera ``strict=False`` does not treat them as fatal.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import pandera.pandas as pa

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.data import ProductionDataSource, load_production_data
from production_quality.models import (
    ValidationIssue,
    ValidationResult,
    unique_sorted_issues,
)
from production_quality.rules import RULES_BY_ID
from production_quality.schema import build_production_schema


def validate_with_pandera(
    data: pd.DataFrame,
    *,
    lazy: bool = True,
    config: ProductionDataConfig = PRODUCTION_DATA_CONFIG,
) -> ValidationResult:
    """Validate a production DataFrame with the Pandera schema."""

    original = data.copy(deep=True)
    working = _blank_strings_to_na(data.copy(deep=True))
    issues: list[ValidationIssue] = list(_unexpected_column_issues(original, config))

    schema = build_production_schema(config)
    try:
        schema.validate(working, lazy=lazy)
    except pa.errors.SchemaErrors as exc:
        for error in exc.schema_errors:
            issues.extend(_issues_from_schema_error(error, original))
    except pa.errors.SchemaError as exc:
        issues.extend(_issues_from_schema_error(exc, original))

    ordered = unique_sorted_issues(issues)
    has_error = any(issue.severity == "Error" for issue in ordered)
    validated = None if has_error else _coerced_success_copy(original, config)
    return ValidationResult(
        issues=ordered,
        validated_data=validated,
        validation_mode="lazy" if lazy else "direct",
        validator_name="Pandera",
    )


def validate_file_with_pandera(
    source: ProductionDataSource,
    *,
    lazy: bool = True,
    config: ProductionDataConfig = PRODUCTION_DATA_CONFIG,
) -> ValidationResult:
    """Load a production CSV, then validate it with Pandera."""

    frame = load_production_data(source)
    return validate_with_pandera(frame, lazy=lazy, config=config)


def _unexpected_column_issues(
    frame: pd.DataFrame,
    config: ProductionDataConfig,
) -> Iterable[ValidationIssue]:
    required = set(config.required_columns)
    for column in frame.columns:
        if column not in required:
            yield ValidationIssue.from_rule(
                "UNEXPECTED_COLUMNS",
                column=str(column),
                failure_value=str(column),
            )


def _issues_from_schema_error(
    error: pa.errors.SchemaError,
    original: pd.DataFrame,
) -> list[ValidationIssue]:
    rule_id = _rule_id_from_error(error)
    if rule_id is None:
        return []

    if rule_id == "NONEMPTY_DATASET":
        return [ValidationIssue.from_rule(rule_id)]

    if rule_id == "REQUIRED_COLUMNS":
        return _missing_column_issues(error)

    if rule_id in {"QUANTITY_BALANCE", "DOWNTIME_WITHIN_PLAN"}:
        return _cross_column_issues(rule_id, error, original)

    return _column_check_issues(rule_id, error, original)


def _rule_id_from_error(error: pa.errors.SchemaError) -> str | None:
    check_name = getattr(error.check, "name", None)
    if isinstance(check_name, str) and check_name in RULES_BY_ID:
        return check_name

    reason = error.reason_code
    if reason == pa.errors.SchemaErrorReason.COLUMN_NOT_IN_DATAFRAME:
        return "REQUIRED_COLUMNS"
    if reason == pa.errors.SchemaErrorReason.SERIES_CONTAINS_NULLS:
        return _null_rule_for_column(error.column_name)
    if reason == pa.errors.SchemaErrorReason.SERIES_CONTAINS_DUPLICATES:
        return "UNIQUE_RECORD_ID"

    check = error.check
    if check == "column_in_dataframe":
        return "REQUIRED_COLUMNS"
    if check == "not_nullable":
        return _null_rule_for_column(error.column_name)
    if check == "field_uniqueness":
        return "UNIQUE_RECORD_ID"
    if isinstance(check, str) and check in RULES_BY_ID:
        return check
    return None


def _null_rule_for_column(column_name: str | None) -> str:
    if column_name:
        for rule in RULES_BY_ID.values():
            if rule.columns == (column_name,):
                return rule.rule_id
    return "REQUIRED_COLUMNS"


def _missing_column_issues(error: pa.errors.SchemaError) -> list[ValidationIssue]:
    missing_names: list[str] = []
    failure_cases = error.failure_cases
    if isinstance(failure_cases, pd.DataFrame) and "failure_case" in failure_cases:
        missing_names.extend(
            str(value) for value in failure_cases["failure_case"].tolist()
        )
    elif isinstance(failure_cases, pd.Series):
        missing_names.extend(str(value) for value in failure_cases.tolist())
    elif failure_cases is not None:
        missing_names.append(str(failure_cases))
    if not missing_names and error.column_name:
        missing_names.append(str(error.column_name))

    return [
        ValidationIssue.from_rule(
            "REQUIRED_COLUMNS",
            column=name,
            failure_value=name,
        )
        for name in missing_names
    ]


def _cross_column_issues(
    rule_id: str,
    error: pa.errors.SchemaError,
    original: pd.DataFrame,
) -> list[ValidationIssue]:
    indexes = _failure_indexes(error)
    if not indexes:
        return [ValidationIssue.from_rule(rule_id)]
    issues: list[ValidationIssue] = []
    columns = RULES_BY_ID[rule_id].columns
    for row_index in indexes:
        failure_value = _row_values(original, row_index, columns)
        issues.append(
            ValidationIssue.from_rule(
                rule_id,
                row_index=row_index,
                failure_value=failure_value,
            )
        )
    return issues


def _column_check_issues(
    rule_id: str,
    error: pa.errors.SchemaError,
    original: pd.DataFrame,
) -> list[ValidationIssue]:
    column = str(error.column_name) if error.column_name is not None else None
    failure_cases = error.failure_cases
    if isinstance(failure_cases, pd.DataFrame) and not failure_cases.empty:
        issues: list[ValidationIssue] = []
        for record in failure_cases.to_dict("records"):
            row_index = _normalize_row_index(record.get("index"))
            if column is None and record.get("column") is not None:
                column_name = str(record["column"])
            else:
                column_name = column
            failure_value = _original_value(
                original,
                row_index,
                column_name,
                fallback=record.get("failure_case"),
            )
            issues.append(
                ValidationIssue.from_rule(
                    rule_id,
                    column=column_name,
                    row_index=row_index,
                    failure_value=failure_value,
                )
            )
        return issues

    failure_value = _original_value(original, None, column, fallback=None)
    return [
        ValidationIssue.from_rule(
            rule_id,
            column=column,
            failure_value=failure_value,
        )
    ]


def _failure_indexes(error: pa.errors.SchemaError) -> list[int | str]:
    failure_cases = error.failure_cases
    if not isinstance(failure_cases, pd.DataFrame) or "index" not in failure_cases:
        return []
    seen: list[int | str] = []
    for raw in failure_cases["index"].tolist():
        row_index = _normalize_row_index(raw)
        if row_index is None or row_index in seen:
            continue
        seen.append(row_index)
    return seen


def _row_values(
    frame: pd.DataFrame,
    row_index: int | str,
    columns: tuple[str, ...],
) -> dict[str, object] | None:
    if row_index not in frame.index:
        return None
    values: dict[str, object] = {}
    for column in columns:
        if column not in frame.columns:
            continue
        values[column] = _normalize_failure_value(frame.loc[row_index, column])
    return values or None


def _original_value(
    frame: pd.DataFrame,
    row_index: int | str | None,
    column: str | None,
    *,
    fallback: object,
) -> object | None:
    if (
        row_index is not None
        and column is not None
        and column in frame.columns
        and row_index in frame.index
    ):
        return _normalize_failure_value(frame.loc[row_index, column])
    return _normalize_failure_value(fallback)


def _normalize_row_index(value: object) -> int | str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and value.is_integer():
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


def _blank_strings_to_na(frame: pd.DataFrame) -> pd.DataFrame:
    """Treat whitespace-only cells as missing on a defensive copy."""

    working = frame.copy(deep=True)
    for column in working.columns:
        series = working[column]
        if not (series.dtype == object or pd.api.types.is_string_dtype(series)):
            continue
        as_string = series.astype("string")
        blank = as_string.isna() | as_string.str.strip().eq("")
        working.loc[blank, column] = pd.NA
    return working


def _coerced_success_copy(
    frame: pd.DataFrame,
    config: ProductionDataConfig,
) -> pd.DataFrame:
    """Convert valid dates and numeric columns after a fully successful pass."""

    coerced = frame.copy(deep=True)
    if "production_date" in coerced.columns:
        coerced["production_date"] = pd.to_datetime(
            coerced["production_date"], errors="raise"
        )
    for column in config.numeric_columns:
        if column in coerced.columns:
            coerced[column] = pd.to_numeric(coerced[column], errors="raise")
    return coerced
