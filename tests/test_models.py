"""Tests for validation result models."""

from __future__ import annotations

from production_quality.models import (
    ISSUE_FRAME_COLUMNS,
    ValidationIssue,
    ValidationResult,
)


def _result(*issues: ValidationIssue) -> ValidationResult:
    return ValidationResult(
        issues=issues,
        validated_data=None,
        validation_mode="lazy",
        validator_name="Pandera",
    )


def test_result_with_no_errors_is_valid() -> None:
    result = _result()
    assert result.is_valid
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.affected_row_count == 0


def test_warning_only_result_remains_valid() -> None:
    result = _result(
        ValidationIssue.from_rule(
            "UNEXPECTED_COLUMNS",
            column="notes",
            failure_value="notes",
        )
    )
    assert result.is_valid
    assert result.error_count == 0
    assert result.warning_count == 1
    assert result.affected_row_count == 0


def test_error_result_is_invalid() -> None:
    result = _result(
        ValidationIssue.from_rule(
            "VALID_SHIFT",
            column="shift",
            row_index=3,
            failure_value="Weekend",
        )
    )
    assert not result.is_valid
    assert result.error_count == 1
    assert result.warning_count == 0
    assert result.affected_row_count == 1


def test_counts_are_correct_for_mixed_issues() -> None:
    result = _result(
        ValidationIssue.from_rule("UNEXPECTED_COLUMNS", column="notes"),
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=1),
        ValidationIssue.from_rule(
            "PRODUCED_QUANTITY_RANGE",
            column="produced_quantity",
            row_index=1,
        ),
        ValidationIssue.from_rule(
            "CYCLE_TIME_RANGE",
            column="cycle_time_seconds",
            row_index=4,
        ),
    )
    assert not result.is_valid
    assert result.error_count == 3
    assert result.warning_count == 1
    assert result.affected_row_count == 2


def test_affected_row_count_deduplicates_the_same_row() -> None:
    result = _result(
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=7),
        ValidationIssue.from_rule(
            "PRODUCED_QUANTITY_RANGE",
            column="produced_quantity",
            row_index=7,
        ),
        ValidationIssue.from_rule("REQUIRED_COLUMNS", column="plant"),
    )
    assert result.affected_row_count == 1


def test_issues_frame_has_stable_columns_when_populated() -> None:
    result = _result(
        ValidationIssue.from_rule(
            "VALID_SHIFT",
            column="shift",
            row_index=2,
            failure_value="Weekend",
        )
    )
    frame = result.issues_frame()
    assert tuple(frame.columns) == ISSUE_FRAME_COLUMNS
    assert len(frame) == 1
    assert frame.loc[0, "rule_id"] == "VALID_SHIFT"


def test_issues_frame_has_stable_columns_when_empty() -> None:
    frame = _result().issues_frame()
    assert tuple(frame.columns) == ISSUE_FRAME_COLUMNS
    assert frame.empty
    assert list(frame.columns) == list(ISSUE_FRAME_COLUMNS)
