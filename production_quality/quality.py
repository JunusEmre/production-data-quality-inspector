"""Row-cleanliness scoring for production extracts.

The score never replaces the validation decision. A file with any Error is
still invalid, even when most rows are clean.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from production_quality.models import ValidationResult

STATUS_PASSED = "Passed"
STATUS_PASSED_WITH_WARNINGS = "Passed with warnings"
STATUS_ISSUES_FOUND = "Issues found"
STATUS_NOT_SCORABLE = "Not scorable"


@dataclass(frozen=True)
class QualitySummary:
    """Operational summary of one inspection, including the row-cleanliness score."""

    total_rows: int
    clean_rows: int | None
    affected_rows: int | None
    error_count: int
    warning_count: int
    score: float | None
    status: str
    is_scorable: bool


def calculate_quality_summary(
    data: pd.DataFrame,
    result: ValidationResult,
) -> QualitySummary:
    """Summarise inspection outcome without mutating the source data or result."""

    total_rows = int(len(data))
    error_count = result.error_count
    warning_count = result.warning_count
    if not _is_scorable(data, result):
        return QualitySummary(
            total_rows=total_rows,
            clean_rows=None,
            affected_rows=None,
            error_count=error_count,
            warning_count=warning_count,
            score=None,
            status=STATUS_NOT_SCORABLE,
            is_scorable=False,
        )

    affected_rows = _affected_error_row_count(result)
    clean_rows = total_rows - affected_rows
    score = round((clean_rows / total_rows) * 100, 2)
    if error_count == 0 and warning_count == 0:
        status = STATUS_PASSED
    elif error_count == 0:
        status = STATUS_PASSED_WITH_WARNINGS
    else:
        status = STATUS_ISSUES_FOUND
    return QualitySummary(
        total_rows=total_rows,
        clean_rows=clean_rows,
        affected_rows=affected_rows,
        error_count=error_count,
        warning_count=warning_count,
        score=score,
        status=status,
        is_scorable=True,
    )


def _is_scorable(data: pd.DataFrame, result: ValidationResult) -> bool:
    if len(data) == 0:
        return False
    return not any(
        issue.severity == "Error" and issue.row_index is None
        for issue in result.issues
    )


def _affected_error_row_count(result: ValidationResult) -> int:
    return len(
        {
            issue.row_index
            for issue in result.issues
            if issue.severity == "Error" and issue.row_index is not None
        }
    )
