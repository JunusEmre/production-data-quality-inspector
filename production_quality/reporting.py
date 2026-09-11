"""Pure report builders for inspection display and in-memory downloads."""

from __future__ import annotations

from io import StringIO

import pandas as pd

from production_quality.models import ValidationResult
from production_quality.quality import QualitySummary
from production_quality.rules import RULES_BY_ID, VALIDATION_RULES

ISSUE_REPORT_COLUMNS: tuple[str, ...] = (
    "severity",
    "rule_id",
    "rule_title",
    "message",
    "row_index",
    "record_id",
    "column",
    "failure_value",
)

AFFECTED_RECORD_EXTRA_COLUMNS: tuple[str, ...] = (
    "source_row",
    "error_count",
    "warning_count",
    "failed_rules",
)

RULE_SUMMARY_COLUMNS: tuple[str, ...] = (
    "rule_id",
    "title",
    "severity",
    "finding_count",
    "affected_row_count",
    "result",
)

QUALITY_SUMMARY_COLUMNS: tuple[str, ...] = (
    "Status",
    "Row-cleanliness score",
    "Total rows",
    "Clean rows",
    "Affected rows",
    "Error findings",
    "Warning findings",
    "Scorable",
)


def build_issue_report(
    data: pd.DataFrame,
    result: ValidationResult,
) -> pd.DataFrame:
    """Return one row per finding, with rule titles and source record IDs."""

    if not result.issues:
        return pd.DataFrame(columns=list(ISSUE_REPORT_COLUMNS))

    records = []
    for issue in result.issues:
        rule = RULES_BY_ID.get(issue.rule_id)
        records.append(
            {
                "severity": issue.severity,
                "rule_id": issue.rule_id,
                "rule_title": rule.title if rule is not None else issue.rule_id,
                "message": issue.message,
                "row_index": issue.row_index,
                "record_id": _record_id_for_row(data, issue.row_index),
                "column": issue.column,
                "failure_value": format_failure_value(issue.failure_value),
            }
        )
    return pd.DataFrame.from_records(records, columns=list(ISSUE_REPORT_COLUMNS))


def build_affected_records(
    data: pd.DataFrame,
    result: ValidationResult,
) -> pd.DataFrame:
    """Return each Error-affected source row once, with combined rule IDs."""

    extra = list(AFFECTED_RECORD_EXTRA_COLUMNS)
    empty_columns = extra + list(data.columns)
    error_rows = [
        issue.row_index
        for issue in result.issues
        if issue.severity == "Error" and issue.row_index is not None
    ]
    unique_rows: list[int | str] = []
    seen: set[int | str] = set()
    for row_index in error_rows:
        if row_index in seen or row_index not in data.index:
            continue
        seen.add(row_index)
        unique_rows.append(row_index)
    if not unique_rows:
        return pd.DataFrame(columns=empty_columns)

    records: list[dict[str, object]] = []
    for row_index in unique_rows:
        row_issues = [
            issue for issue in result.issues if issue.row_index == row_index
        ]
        source = data.loc[row_index]
        record = {column: source[column] for column in data.columns}
        record["source_row"] = row_index
        record["error_count"] = sum(
            1 for issue in row_issues if issue.severity == "Error"
        )
        record["warning_count"] = sum(
            1 for issue in row_issues if issue.severity == "Warning"
        )
        record["failed_rules"] = _joined_rule_ids(row_issues)
        records.append(record)
    frame = pd.DataFrame.from_records(records)
    return frame.loc[:, extra + list(data.columns)]


def build_rule_summary(result: ValidationResult) -> pd.DataFrame:
    """Return all 19 catalog rules with the current inspection outcome."""

    records = []
    for rule in VALIDATION_RULES:
        issues = [issue for issue in result.issues if issue.rule_id == rule.rule_id]
        affected = {
            issue.row_index
            for issue in issues
            if issue.row_index is not None
        }
        if not issues:
            outcome = "Passed"
        elif any(issue.severity == "Error" for issue in issues):
            outcome = "Error"
        else:
            outcome = "Warning"
        records.append(
            {
                "rule_id": rule.rule_id,
                "title": rule.title,
                "severity": rule.severity,
                "finding_count": len(issues),
                "affected_row_count": len(affected),
                "result": outcome,
            }
        )
    return pd.DataFrame.from_records(records, columns=list(RULE_SUMMARY_COLUMNS))


def build_quality_summary_frame(summary: QualitySummary) -> pd.DataFrame:
    """Return a one-row table suitable for CSV download."""

    return pd.DataFrame(
        [
            {
                "Status": summary.status,
                "Row-cleanliness score": summary.score,
                "Total rows": summary.total_rows,
                "Clean rows": summary.clean_rows,
                "Affected rows": summary.affected_rows,
                "Error findings": summary.error_count,
                "Warning findings": summary.warning_count,
                "Scorable": summary.is_scorable,
            }
        ],
        columns=list(QUALITY_SUMMARY_COLUMNS),
    )


def dataframe_to_csv_bytes(data: pd.DataFrame) -> bytes:
    """Encode a DataFrame as UTF-8 CSV bytes without writing to disk."""

    buffer = StringIO()
    data.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def format_failure_value(value: object) -> str | None:
    """Turn a stored failing value into a readable report cell."""

    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, dict):
        parts = [f"{key}={_plain_text(item)}" for key, item in value.items()]
        return "; ".join(parts)
    return _plain_text(value)


def _record_id_for_row(data: pd.DataFrame, row_index: int | str | None) -> object | None:
    if row_index is None or "record_id" not in data.columns:
        return None
    if row_index not in data.index:
        return None
    return _plain_text(data.loc[row_index, "record_id"])


def _joined_rule_ids(issues: list) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    catalog_order = {rule.rule_id: index for index, rule in enumerate(VALIDATION_RULES)}
    for issue in sorted(
        issues, key=lambda item: catalog_order.get(item.rule_id, len(catalog_order))
    ):
        if issue.rule_id in seen:
            continue
        seen.add(issue.rule_id)
        ordered.append(issue.rule_id)
    return ", ".join(ordered)


def _plain_text(value: object) -> str | None:
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
    return str(value)
