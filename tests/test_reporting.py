"""Tests for report-building helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from production_quality.models import ValidationIssue, ValidationResult
from production_quality.quality import calculate_quality_summary
from production_quality.reporting import (
    AFFECTED_RECORD_EXTRA_COLUMNS,
    ISSUE_REPORT_COLUMNS,
    QUALITY_SUMMARY_COLUMNS,
    RULE_SUMMARY_COLUMNS,
    build_affected_records,
    build_issue_report,
    build_quality_summary_frame,
    build_rule_summary,
    dataframe_to_csv_bytes,
)
from production_quality.rules import VALIDATION_RULES
from production_quality.validation import validate_with_pandera


def _result(*issues: ValidationIssue) -> ValidationResult:
    return ValidationResult(
        issues=issues,
        validated_data=None,
        validation_mode="lazy",
        validator_name="Pandera",
    )


def test_issue_report_has_stable_columns(valid_frame: pd.DataFrame, changed_copy) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    result = validate_with_pandera(frame)
    report = build_issue_report(frame, result)
    assert tuple(report.columns) == ISSUE_REPORT_COLUMNS
    assert not report.empty


def test_empty_issue_report_has_the_same_columns(valid_frame: pd.DataFrame) -> None:
    report = build_issue_report(valid_frame, _result())
    assert tuple(report.columns) == ISSUE_REPORT_COLUMNS
    assert report.empty


def test_record_id_is_mapped_from_source_row(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    report = build_issue_report(frame, validate_with_pandera(frame))
    shift_row = report.loc[report["rule_id"] == "VALID_SHIFT"].iloc[0]
    assert shift_row["record_id"] == "PR-TEST-000001"
    assert shift_row["row_index"] == 0


def test_missing_record_id_column_is_handled_safely(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend").drop(columns=["record_id"])
    result = _result(
        ValidationIssue.from_rule(
            "VALID_SHIFT",
            column="shift",
            row_index=0,
            failure_value="Weekend",
        )
    )
    report = build_issue_report(frame, result)
    assert report.loc[0, "record_id"] is None


def test_original_failure_values_remain_readable(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, produced_quantity="unknown")
    report = build_issue_report(frame, validate_with_pandera(frame))
    values = report.loc[
        report["rule_id"] == "PRODUCED_QUANTITY_RANGE", "failure_value"
    ]
    assert "unknown" in set(values)


def test_affected_records_contain_each_source_row_once(
    two_valid_rows: pd.DataFrame,
) -> None:
    frame = two_valid_rows.copy(deep=True)
    frame["shift"] = frame["shift"].astype(object)
    frame.loc[0, "shift"] = "Weekend"
    result = _result(
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=0),
        ValidationIssue.from_rule(
            "PRODUCED_QUANTITY_RANGE",
            column="produced_quantity",
            row_index=0,
            failure_value="unknown",
        ),
    )
    affected = build_affected_records(frame, result)
    assert len(affected) == 1
    assert int(affected.loc[0, "source_row"]) == 0
    assert int(affected.loc[0, "error_count"]) == 2


def test_multiple_findings_are_combined_into_failed_rules(
    valid_frame: pd.DataFrame,
) -> None:
    result = _result(
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=0),
        ValidationIssue.from_rule(
            "CYCLE_TIME_RANGE",
            column="cycle_time_seconds",
            row_index=0,
        ),
    )
    affected = build_affected_records(valid_frame, result)
    failed = str(affected.loc[0, "failed_rules"])
    assert "VALID_SHIFT" in failed
    assert "CYCLE_TIME_RANGE" in failed
    assert failed.index("VALID_SHIFT") < failed.index("CYCLE_TIME_RANGE")


def test_original_source_values_remain_unchanged(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    snapshot = frame.copy(deep=True)
    affected = build_affected_records(frame, validate_with_pandera(frame))
    pd.testing.assert_frame_equal(frame, snapshot)
    assert affected.loc[0, "shift"] == "Weekend"


def test_dataset_level_failures_do_not_create_fake_affected_rows(
    valid_frame: pd.DataFrame,
) -> None:
    result = _result(
        ValidationIssue.from_rule("REQUIRED_COLUMNS", column="plant", failure_value="plant")
    )
    affected = build_affected_records(valid_frame, result)
    assert affected.empty
    assert list(affected.columns)[:4] == list(AFFECTED_RECORD_EXTRA_COLUMNS)


def test_rule_summary_contains_all_nineteen_rules(valid_frame: pd.DataFrame) -> None:
    summary = build_rule_summary(validate_with_pandera(valid_frame))
    assert tuple(summary.columns) == RULE_SUMMARY_COLUMNS
    assert len(summary) == 19
    assert list(summary["rule_id"]) == [rule.rule_id for rule in VALIDATION_RULES]
    assert set(summary["result"]) == {"Passed"}


def test_passed_error_and_warning_rule_states(valid_frame: pd.DataFrame) -> None:
    result = _result(
        ValidationIssue.from_rule("UNEXPECTED_COLUMNS", column="notes"),
        ValidationIssue.from_rule("VALID_SHIFT", column="shift", row_index=0),
    )
    summary = build_rule_summary(result)
    states = summary.set_index("rule_id")["result"]
    assert states["VALID_SHIFT"] == "Error"
    assert states["UNEXPECTED_COLUMNS"] == "Warning"
    assert states["PLANT_PRESENT"] == "Passed"


def test_quality_summary_frame_contains_correct_values(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    result = validate_with_pandera(frame)
    quality = calculate_quality_summary(frame, result)
    table = build_quality_summary_frame(quality)
    assert tuple(table.columns) == QUALITY_SUMMARY_COLUMNS
    assert table.loc[0, "Status"] == "Issues found"
    assert table.loc[0, "Total rows"] == 1
    assert table.loc[0, "Affected rows"] == 1
    assert table.loc[0, "Error findings"] >= 1


def test_csv_bytes_use_utf8_and_no_index(valid_frame: pd.DataFrame) -> None:
    payload = dataframe_to_csv_bytes(valid_frame)
    text = payload.decode("utf-8")
    assert "record_id" in text.splitlines()[0]
    assert not text.startswith(",")
    assert "\r\n" in text or "\n" in text


def test_reporting_helpers_write_no_files(
    valid_frame: pd.DataFrame, tmp_path: Path, monkeypatch, changed_copy
) -> None:
    monkeypatch.chdir(tmp_path)
    frame = changed_copy(valid_frame, shift="Weekend")
    result = validate_with_pandera(frame)
    summary = calculate_quality_summary(frame, result)
    build_issue_report(frame, result)
    build_affected_records(frame, result)
    build_rule_summary(result)
    dataframe_to_csv_bytes(build_quality_summary_frame(summary))
    assert list(tmp_path.iterdir()) == []


def test_reporting_inputs_are_not_mutated(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    result = validate_with_pandera(frame)
    data_snapshot = frame.copy(deep=True)
    issue_snapshot = result.issues
    build_issue_report(frame, result)
    build_affected_records(frame, result)
    build_rule_summary(result)
    pd.testing.assert_frame_equal(frame, data_snapshot)
    assert result.issues == issue_snapshot
