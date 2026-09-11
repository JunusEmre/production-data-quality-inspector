"""Tests for the row-cleanliness score."""

from __future__ import annotations

import pandas as pd

from production_quality.models import ValidationIssue, ValidationResult
from production_quality.quality import (
    STATUS_ISSUES_FOUND,
    STATUS_NOT_SCORABLE,
    STATUS_PASSED,
    STATUS_PASSED_WITH_WARNINGS,
    calculate_quality_summary,
)


def _result(*issues: ValidationIssue) -> ValidationResult:
    return ValidationResult(
        issues=issues,
        validated_data=None,
        validation_mode="lazy",
        validator_name="Pandera",
    )


def test_valid_data_receives_passed_and_full_score(valid_frame: pd.DataFrame) -> None:
    summary = calculate_quality_summary(valid_frame, _result())
    assert summary.status == STATUS_PASSED
    assert summary.is_scorable
    assert summary.score == 100.00
    assert summary.clean_rows == 1
    assert summary.affected_rows == 0
    assert summary.error_count == 0
    assert summary.warning_count == 0


def test_warning_only_data_keeps_full_score(valid_frame: pd.DataFrame) -> None:
    result = _result(
        ValidationIssue.from_rule("UNEXPECTED_COLUMNS", column="notes", failure_value="notes")
    )
    summary = calculate_quality_summary(valid_frame, result)
    assert summary.status == STATUS_PASSED_WITH_WARNINGS
    assert summary.score == 100.00
    assert summary.affected_rows == 0
    assert summary.clean_rows == 1
    assert summary.warning_count == 1


def test_multiple_errors_on_one_row_reduce_the_score_once(
    two_valid_rows: pd.DataFrame,
) -> None:
    result = _result(
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=0),
        ValidationIssue.from_rule(
            "PRODUCED_QUANTITY_RANGE",
            column="produced_quantity",
            row_index=0,
        ),
        ValidationIssue.from_rule("CYCLE_TIME_RANGE", column="cycle_time_seconds", row_index=0),
    )
    summary = calculate_quality_summary(two_valid_rows, result)
    assert summary.status == STATUS_ISSUES_FOUND
    assert summary.affected_rows == 1
    assert summary.clean_rows == 1
    assert summary.score == 50.00
    assert summary.error_count == 3


def test_errors_on_different_rows_reduce_by_row_count(
    two_valid_rows: pd.DataFrame,
) -> None:
    result = _result(
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=0),
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=1),
    )
    summary = calculate_quality_summary(two_valid_rows, result)
    assert summary.affected_rows == 2
    assert summary.clean_rows == 0
    assert summary.score == 0.00
    assert summary.status == STATUS_ISSUES_FOUND


def test_demonstration_counts_produce_98_58() -> None:
    data = pd.DataFrame({"record_id": [f"PR-{index:04d}" for index in range(1200)]})
    issues = [
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=index)
        for index in range(17)
    ]
    issues.append(
        ValidationIssue.from_rule(
            "PRODUCED_QUANTITY_RANGE",
            column="produced_quantity",
            row_index=0,
        )
    )
    summary = calculate_quality_summary(data, _result(*issues))
    assert summary.total_rows == 1200
    assert summary.affected_rows == 17
    assert summary.clean_rows == 1183
    assert summary.score == 98.58
    assert summary.status == STATUS_ISSUES_FOUND


def test_missing_column_error_is_not_scorable(valid_frame: pd.DataFrame) -> None:
    data = valid_frame.drop(columns=["plant"])
    result = _result(
        ValidationIssue.from_rule("REQUIRED_COLUMNS", column="plant", failure_value="plant")
    )
    summary = calculate_quality_summary(data, result)
    assert summary.status == STATUS_NOT_SCORABLE
    assert summary.score is None
    assert summary.clean_rows is None
    assert summary.affected_rows is None
    assert summary.is_scorable is False


def test_empty_data_is_not_scorable(valid_frame: pd.DataFrame) -> None:
    empty = valid_frame.iloc[0:0]
    result = _result(ValidationIssue.from_rule("NONEMPTY_DATASET"))
    summary = calculate_quality_summary(empty, result)
    assert summary.status == STATUS_NOT_SCORABLE
    assert summary.score is None
    assert summary.clean_rows is None
    assert summary.affected_rows is None
    assert summary.score != 0


def test_none_score_is_not_converted_to_zero(valid_frame: pd.DataFrame) -> None:
    result = _result(
        ValidationIssue.from_rule("REQUIRED_COLUMNS", column="plant", failure_value="plant")
    )
    summary = calculate_quality_summary(valid_frame, result)
    assert summary.score is None
    assert summary.clean_rows is None
    assert summary.affected_rows is None


def test_status_is_based_on_errors_not_score() -> None:
    data = pd.DataFrame({"record_id": [f"PR-{index:04d}" for index in range(1200)]})
    issues = [
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=index)
        for index in range(17)
    ]
    summary = calculate_quality_summary(data, _result(*issues))
    assert summary.score == 98.58
    assert summary.status == STATUS_ISSUES_FOUND
    assert summary.status != STATUS_PASSED


def test_quality_summary_does_not_mutate_inputs(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    result = _result(
        ValidationIssue.from_rule(
            "VALID_SHIFT",
            column="shift",
            row_index=0,
            failure_value="Weekend",
        )
    )
    data_snapshot = frame.copy(deep=True)
    issue_snapshot = result.issues
    calculate_quality_summary(frame, result)
    pd.testing.assert_frame_equal(frame, data_snapshot)
    assert result.issues is issue_snapshot
