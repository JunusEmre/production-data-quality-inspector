"""Reusable validation result models for production data quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from production_quality.rules import RULES_BY_ID, VALIDATION_RULES, ValidationRule

ISSUE_FRAME_COLUMNS: tuple[str, ...] = (
    "rule_id",
    "severity",
    "message",
    "column",
    "row_index",
    "failure_value",
)

_RULE_ORDER = {rule.rule_id: index for index, rule in enumerate(VALIDATION_RULES)}


@dataclass(frozen=True)
class ValidationIssue:
    """One data-quality finding, written for operational review."""

    rule_id: str
    severity: str
    message: str
    column: str | None = None
    row_index: int | str | None = None
    failure_value: object | None = None

    @classmethod
    def from_rule(
        cls,
        rule_id: str,
        *,
        column: str | None = None,
        row_index: int | str | None = None,
        failure_value: object | None = None,
    ) -> ValidationIssue:
        """Build an issue from the shared rule catalog."""

        rule = RULES_BY_ID[rule_id]
        return cls(
            rule_id=rule.rule_id,
            severity=rule.severity,
            message=_issue_message(
                rule,
                column=column,
                row_index=row_index,
                failure_value=failure_value,
            ),
            column=column,
            row_index=row_index,
            failure_value=failure_value,
        )


@dataclass
class ValidationResult:
    """Outcome of one validation pass over a production extract."""

    issues: tuple[ValidationIssue, ...]
    validated_data: pd.DataFrame | None
    validation_mode: str
    validator_name: str

    @property
    def is_valid(self) -> bool:
        """True when the extract has no Error issues. Warnings do not invalidate it."""

        return self.error_count == 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "Error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "Warning")

    @property
    def affected_row_count(self) -> int:
        """Count unique source rows that have at least one Error."""

        return len(
            {
                issue.row_index
                for issue in self.issues
                if issue.severity == "Error" and issue.row_index is not None
            }
        )

    def issues_frame(self) -> pd.DataFrame:
        """Return findings as a table with a stable column layout."""

        if not self.issues:
            return pd.DataFrame(columns=list(ISSUE_FRAME_COLUMNS))
        records = [
            {
                "rule_id": issue.rule_id,
                "severity": issue.severity,
                "message": issue.message,
                "column": issue.column,
                "row_index": issue.row_index,
                "failure_value": issue.failure_value,
            }
            for issue in self.issues
        ]
        return pd.DataFrame.from_records(records, columns=list(ISSUE_FRAME_COLUMNS))


def unique_sorted_issues(
    issues: Iterable[ValidationIssue],
) -> tuple[ValidationIssue, ...]:
    """Drop identical findings and sort by catalog order, then row index."""

    unique: list[ValidationIssue] = []
    seen: set[tuple[object, ...]] = set()
    for issue in issues:
        key = (
            issue.rule_id,
            issue.column,
            issue.row_index,
            _value_key(issue.failure_value),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    unique.sort(key=_issue_sort_key)
    return tuple(unique)


def _issue_message(
    rule: ValidationRule,
    *,
    column: str | None,
    row_index: int | str | None,
    failure_value: object | None,
) -> str:
    details: list[str] = []
    if column is not None:
        details.append(f"column {column}")
    if row_index is not None:
        details.append(f"row {row_index}")
    if failure_value is not None:
        details.append(f"value {failure_value!r}")
    if details:
        return f"{rule.title} ({', '.join(details)})"
    return rule.title


def _issue_sort_key(
    issue: ValidationIssue,
) -> tuple[int, int, int | str, str]:
    rule_rank = _RULE_ORDER.get(issue.rule_id, len(_RULE_ORDER))
    if issue.row_index is None:
        row_rank, row_value = (0, -1)
    elif isinstance(issue.row_index, int):
        row_rank, row_value = (1, issue.row_index)
    else:
        row_rank, row_value = (2, str(issue.row_index))
    return (rule_rank, row_rank, row_value, issue.column or "")


def _value_key(value: object) -> object:
    if isinstance(value, (list, dict, set, tuple)):
        return repr(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value
