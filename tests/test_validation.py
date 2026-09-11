"""Tests for the Pandera validation service."""

from __future__ import annotations

import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from production_quality.config import PRODUCTION_DATA_CONFIG
from production_quality.models import ISSUE_FRAME_COLUMNS
from production_quality.validation import (
    validate_file_with_pandera,
    validate_with_pandera,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _rule_ids(result) -> set[str]:
    return {issue.rule_id for issue in result.issues}


def _error_ids(result) -> set[str]:
    return {issue.rule_id for issue in result.issues if issue.severity == "Error"}


def _rows_for(result, rule_id: str) -> set[object]:
    return {
        issue.row_index
        for issue in result.issues
        if issue.rule_id == rule_id and issue.row_index is not None
    }


def test_valid_data_passes(valid_frame: pd.DataFrame) -> None:
    result = validate_with_pandera(valid_frame)
    assert result.is_valid
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.validated_data is not None
    assert result.validator_name == "Pandera"
    assert result.validation_mode == "lazy"


def test_valid_boundary_data_passes(boundary_frame: pd.DataFrame) -> None:
    result = validate_with_pandera(boundary_frame)
    assert result.is_valid
    assert result.issues == ()
    assert result.validated_data is not None


def test_input_dataframe_is_not_mutated(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    original = changed_copy(valid_frame, produced_quantity="unknown")
    snapshot = original.copy(deep=True)
    result = validate_with_pandera(original)
    assert not result.is_valid
    pd.testing.assert_frame_equal(original, snapshot)
    assert original.loc[0, "produced_quantity"] == "unknown"


def test_all_required_columns_are_accepted(valid_frame: pd.DataFrame) -> None:
    result = validate_with_pandera(valid_frame)
    assert list(valid_frame.columns) == list(PRODUCTION_DATA_CONFIG.required_columns)
    assert result.is_valid


@pytest.mark.parametrize("column", PRODUCTION_DATA_CONFIG.required_columns)
def test_each_missing_required_column_fails(
    valid_frame: pd.DataFrame, column: str
) -> None:
    frame = valid_frame.drop(columns=[column])
    result = validate_with_pandera(frame)
    assert not result.is_valid
    assert "REQUIRED_COLUMNS" in _error_ids(result)
    assert any(
        issue.rule_id == "REQUIRED_COLUMNS" and issue.column == column
        for issue in result.issues
    )


def test_extra_column_is_a_warning_and_result_stays_valid(
    valid_frame: pd.DataFrame,
) -> None:
    frame = valid_frame.copy(deep=True)
    frame["notes"] = "supervisor comment"
    result = validate_with_pandera(frame)
    assert result.is_valid
    assert result.warning_count == 1
    assert _rule_ids(result) == {"UNEXPECTED_COLUMNS"}
    assert result.issues[0].severity == "Warning"
    assert result.validated_data is not None


def test_empty_dataframe_fails(valid_frame: pd.DataFrame) -> None:
    empty = valid_frame.iloc[0:0]
    result = validate_with_pandera(empty)
    assert not result.is_valid
    assert "NONEMPTY_DATASET" in _error_ids(result)


def test_blank_record_id_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, record_id=None))
    assert "RECORD_ID_PRESENT" in _error_ids(result)
    assert 0 in _rows_for(result, "RECORD_ID_PRESENT")


def test_duplicate_record_id_identifies_affected_rows(
    two_valid_rows: pd.DataFrame,
) -> None:
    frame = two_valid_rows.copy(deep=True)
    frame.loc[1, "record_id"] = frame.loc[0, "record_id"]
    result = validate_with_pandera(frame)
    assert "UNIQUE_RECORD_ID" in _error_ids(result)
    assert _rows_for(result, "UNIQUE_RECORD_ID") == {0, 1}


def test_invalid_date_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(
        changed_copy(valid_frame, production_date="2026-02-30")
    )
    issue = next(
        item for item in result.issues if item.rule_id == "VALID_PRODUCTION_DATE"
    )
    assert issue.failure_value == "2026-02-30"
    assert issue.row_index == 0


def test_blank_plant_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, plant="  "))
    assert "PLANT_PRESENT" in _error_ids(result)


def test_invalid_production_line_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(
        changed_copy(valid_frame, production_line="Line-Z")
    )
    assert "VALID_PRODUCTION_LINE" in _error_ids(result)


def test_missing_machine_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, machine_id=None))
    assert "VALID_MACHINE_ID" in _error_ids(result)


def test_unknown_machine_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, machine_id="MC-999"))
    issue = next(item for item in result.issues if item.rule_id == "VALID_MACHINE_ID")
    assert issue.failure_value == "MC-999"


def test_invalid_shift_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, shift="Weekend"))
    assert "VALID_SHIFT" in _error_ids(result)


def test_missing_product_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, product_code=None))
    assert "VALID_PRODUCT_CODE" in _error_ids(result)


def test_unknown_product_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, product_code="PRD-Z999"))
    assert "VALID_PRODUCT_CODE" in _error_ids(result)


@pytest.mark.parametrize(
    ("column", "value", "rule_id"),
    [
        ("produced_quantity", "unknown", "PRODUCED_QUANTITY_RANGE"),
        ("produced_quantity", -5, "PRODUCED_QUANTITY_RANGE"),
        ("good_quantity", "bad", "GOOD_QUANTITY_RANGE"),
        ("good_quantity", -10, "GOOD_QUANTITY_RANGE"),
        ("scrap_quantity", "n/a", "SCRAP_QUANTITY_RANGE"),
        ("scrap_quantity", -3, "SCRAP_QUANTITY_RANGE"),
        ("downtime_minutes", "stopped", "DOWNTIME_MINUTES_RANGE"),
        ("downtime_minutes", -15, "DOWNTIME_MINUTES_RANGE"),
        ("planned_minutes", "plan", "PLANNED_MINUTES_RANGE"),
        ("planned_minutes", 0, "PLANNED_MINUTES_RANGE"),
        ("cycle_time_seconds", "fast", "CYCLE_TIME_RANGE"),
        ("cycle_time_seconds", 0, "CYCLE_TIME_RANGE"),
        ("cycle_time_seconds", -1.5, "CYCLE_TIME_RANGE"),
    ],
)
def test_numeric_rule_failures(
    valid_frame: pd.DataFrame,
    changed_copy,
    column: str,
    value: object,
    rule_id: str,
) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, **{column: value}))
    assert rule_id in _error_ids(result)
    issue = next(item for item in result.issues if item.rule_id == rule_id)
    assert issue.failure_value == value
    assert issue.row_index == 0


def test_quantity_balance_fails(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(
        changed_copy(valid_frame, produced_quantity=10, good_quantity=8, scrap_quantity=5)
    )
    assert "QUANTITY_BALANCE" in _error_ids(result)
    assert 0 in _rows_for(result, "QUANTITY_BALANCE")


def test_downtime_greater_than_planned_fails(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    result = validate_with_pandera(
        changed_copy(valid_frame, downtime_minutes=500, planned_minutes=480)
    )
    assert "DOWNTIME_WITHIN_PLAN" in _error_ids(result)


def test_equality_boundaries_pass(boundary_frame: pd.DataFrame) -> None:
    result = validate_with_pandera(boundary_frame)
    assert result.is_valid


def test_nonnumeric_quantity_does_not_create_balance_failure(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    result = validate_with_pandera(
        changed_copy(valid_frame, produced_quantity="unknown")
    )
    assert "PRODUCED_QUANTITY_RANGE" in _error_ids(result)
    assert "QUANTITY_BALANCE" not in _error_ids(result)


def test_lazy_false_returns_only_the_first_pandera_error(
    valid_frame: pd.DataFrame,
) -> None:
    frame = valid_frame.copy(deep=True)
    frame["notes"] = "extra"
    frame["shift"] = frame["shift"].astype(object)
    frame["produced_quantity"] = frame["produced_quantity"].astype(object)
    frame.loc[0, "shift"] = "Weekend"
    frame.loc[0, "produced_quantity"] = "unknown"
    result = validate_with_pandera(frame, lazy=False)
    assert result.validation_mode == "direct"
    assert "UNEXPECTED_COLUMNS" in _rule_ids(result)
    error_ids = _error_ids(result)
    assert error_ids == {"VALID_SHIFT"}
    assert "PRODUCED_QUANTITY_RANGE" not in error_ids


def test_lazy_true_returns_multiple_independent_errors(
    valid_frame: pd.DataFrame,
) -> None:
    frame = valid_frame.copy(deep=True)
    frame["shift"] = frame["shift"].astype(object)
    frame["produced_quantity"] = frame["produced_quantity"].astype(object)
    frame.loc[0, "shift"] = "Weekend"
    frame.loc[0, "produced_quantity"] = "unknown"
    result = validate_with_pandera(frame, lazy=True)
    assert result.validation_mode == "lazy"
    assert {"VALID_SHIFT", "PRODUCED_QUANTITY_RANGE"} <= _error_ids(result)


def test_original_bad_values_remain_in_failure_value(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    result = validate_with_pandera(
        changed_copy(
            valid_frame,
            produced_quantity="unknown",
            cycle_time_seconds="fast",
            production_date="2026-02-30",
        )
    )
    values = {
        issue.rule_id: issue.failure_value
        for issue in result.issues
        if issue.rule_id
        in {"PRODUCED_QUANTITY_RANGE", "CYCLE_TIME_RANGE", "VALID_PRODUCTION_DATE"}
    }
    assert values["PRODUCED_QUANTITY_RANGE"] == "unknown"
    assert values["CYCLE_TIME_RANGE"] == "fast"
    assert values["VALID_PRODUCTION_DATE"] == "2026-02-30"


def test_errors_are_deduplicated_and_deterministically_ordered(
    two_valid_rows: pd.DataFrame,
) -> None:
    frame = two_valid_rows.copy(deep=True)
    frame["shift"] = frame["shift"].astype(object)
    frame["produced_quantity"] = frame["produced_quantity"].astype(object)
    frame.loc[0, "shift"] = "Weekend"
    frame.loc[1, "shift"] = "Weekend"
    frame.loc[0, "produced_quantity"] = "unknown"
    result = validate_with_pandera(frame)
    keys = [
        (issue.rule_id, issue.row_index, issue.column)
        for issue in result.issues
    ]
    assert keys == sorted(keys, key=lambda item: keys.index(item))
    assert keys == list(dict.fromkeys(keys))
    rule_order = [issue.rule_id for issue in result.issues]
    assert rule_order.index("VALID_SHIFT") < rule_order.index("PRODUCED_QUANTITY_RANGE")


def test_validate_file_with_pandera_reuses_loader(
    tmp_path: Path, valid_frame: pd.DataFrame
) -> None:
    csv_path = tmp_path / "valid.csv"
    valid_frame.to_csv(csv_path, index=False)
    result = validate_file_with_pandera(csv_path)
    assert result.is_valid
    buffer = BytesIO(csv_path.read_bytes())
    assert validate_file_with_pandera(buffer).is_valid


def test_validation_does_not_create_or_write_files(
    valid_frame: pd.DataFrame, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    validate_with_pandera(valid_frame)
    validate_with_pandera(valid_frame.assign(notes="x"))
    assert list(tmp_path.iterdir()) == []


def test_issues_frame_columns_are_stable(valid_frame: pd.DataFrame, changed_copy) -> None:
    result = validate_with_pandera(changed_copy(valid_frame, shift="Weekend"))
    assert tuple(result.issues_frame().columns) == ISSUE_FRAME_COLUMNS


def test_importing_validation_does_not_read_csv_or_run_validation(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path\n"
                "import builtins\n"
                "original_open = builtins.open\n"
                "\n"
                "def guarded_open(file, *args, **kwargs):\n"
                "    try:\n"
                "        path = Path(file)\n"
                "    except TypeError:\n"
                "        return original_open(file, *args, **kwargs)\n"
                "    if path.name == 'production_data.csv':\n"
                "        raise AssertionError('CSV must not be read on import')\n"
                "    return original_open(file, *args, **kwargs)\n"
                "\n"
                "builtins.open = guarded_open\n"
                "import production_quality.validation as module\n"
                "assert module.validate_with_pandera.__name__\n"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []
