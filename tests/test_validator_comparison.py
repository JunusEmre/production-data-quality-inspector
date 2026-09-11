"""Compare Pandera and manual pandas validators on the same examples."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from production_quality.data import load_production_data
from production_quality.manual_validation import validate_with_pandas
from production_quality.validation import validate_with_pandera

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_CSV = PROJECT_ROOT / "data" / "production_data.csv"

PLANTED_RULE_IDS = {
    "RECORD_ID_PRESENT",
    "UNIQUE_RECORD_ID",
    "VALID_PRODUCTION_DATE",
    "VALID_MACHINE_ID",
    "VALID_SHIFT",
    "VALID_PRODUCT_CODE",
    "PRODUCED_QUANTITY_RANGE",
    "GOOD_QUANTITY_RANGE",
    "SCRAP_QUANTITY_RANGE",
    "DOWNTIME_MINUTES_RANGE",
    "CYCLE_TIME_RANGE",
    "QUANTITY_BALANCE",
    "DOWNTIME_WITHIN_PLAN",
}


def _error_ids(result) -> set[str]:
    return {issue.rule_id for issue in result.issues if issue.severity == "Error"}


def _warning_ids(result) -> set[str]:
    return {issue.rule_id for issue in result.issues if issue.severity == "Warning"}


def _rows(result, rule_id: str) -> set[object]:
    return {
        issue.row_index
        for issue in result.issues
        if issue.rule_id == rule_id and issue.row_index is not None
    }


def test_both_accept_valid_data(valid_frame: pd.DataFrame) -> None:
    pandera_result = validate_with_pandera(valid_frame)
    pandas_result = validate_with_pandas(valid_frame)
    assert pandera_result.is_valid is pandas_result.is_valid is True
    assert _warning_ids(pandera_result) == _warning_ids(pandas_result) == set()


def test_both_accept_boundary_data(boundary_frame: pd.DataFrame) -> None:
    pandera_result = validate_with_pandera(boundary_frame)
    pandas_result = validate_with_pandas(boundary_frame)
    assert pandera_result.is_valid
    assert pandas_result.is_valid
    assert pandera_result.error_count == pandas_result.error_count == 0


def test_both_treat_extra_columns_as_warning(valid_frame: pd.DataFrame) -> None:
    frame = valid_frame.copy(deep=True)
    frame["notes"] = "extra"
    pandera_result = validate_with_pandera(frame)
    pandas_result = validate_with_pandas(frame)
    assert pandera_result.is_valid is pandas_result.is_valid is True
    assert _warning_ids(pandera_result) == _warning_ids(pandas_result) == {
        "UNEXPECTED_COLUMNS"
    }


def test_both_agree_on_row_level_failures(two_valid_rows: pd.DataFrame) -> None:
    frame = two_valid_rows.copy(deep=True)
    frame["shift"] = frame["shift"].astype(object)
    frame["record_id"] = frame["record_id"].astype(object)
    frame["cycle_time_seconds"] = frame["cycle_time_seconds"].astype(object)
    frame.loc[0, "shift"] = "Weekend"
    frame.loc[1, "record_id"] = frame.loc[0, "record_id"]
    frame.loc[1, "cycle_time_seconds"] = "fast"
    pandera_result = validate_with_pandera(frame)
    pandas_result = validate_with_pandas(frame)
    assert pandera_result.is_valid is pandas_result.is_valid is False
    assert _error_ids(pandera_result) == _error_ids(pandas_result)
    for rule_id in _error_ids(pandera_result):
        assert _rows(pandera_result, rule_id) == _rows(pandas_result, rule_id)


def test_both_agree_on_quantity_and_downtime_boundaries(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    balanced = changed_copy(
        valid_frame,
        produced_quantity=20,
        good_quantity=12,
        scrap_quantity=8,
        downtime_minutes=30,
        planned_minutes=30,
    )
    broken = changed_copy(
        valid_frame,
        produced_quantity=20,
        good_quantity=12,
        scrap_quantity=9,
        downtime_minutes=31,
        planned_minutes=30,
    )
    for frame, should_be_valid in ((balanced, True), (broken, False)):
        pandera_result = validate_with_pandera(frame)
        pandas_result = validate_with_pandas(frame)
        assert pandera_result.is_valid is pandas_result.is_valid is should_be_valid
        if not should_be_valid:
            assert _error_ids(pandera_result) == _error_ids(pandas_result)
            assert "QUANTITY_BALANCE" in _error_ids(pandera_result)
            assert "DOWNTIME_WITHIN_PLAN" in _error_ids(pandera_result)


def test_both_detect_planted_issue_categories_in_demonstration_csv() -> None:
    frame = load_production_data(PRODUCTION_CSV)
    pandera_lazy = validate_with_pandera(frame, lazy=True)
    pandas_result = validate_with_pandas(frame)

    assert pandera_lazy.is_valid is False
    assert pandas_result.is_valid is False
    assert "UNEXPECTED_COLUMNS" not in _warning_ids(pandera_lazy)
    assert "UNEXPECTED_COLUMNS" not in _warning_ids(pandas_result)
    assert PLANTED_RULE_IDS <= _error_ids(pandera_lazy)
    assert PLANTED_RULE_IDS <= _error_ids(pandas_result)

    assert _rows(pandera_lazy, "UNIQUE_RECORD_ID") == _rows(
        pandas_result, "UNIQUE_RECORD_ID"
    )
    assert _rows(pandera_lazy, "VALID_SHIFT") == _rows(pandas_result, "VALID_SHIFT")
    assert _rows(pandera_lazy, "VALID_PRODUCTION_DATE") == _rows(
        pandas_result, "VALID_PRODUCTION_DATE"
    )
    assert _rows(pandera_lazy, "DOWNTIME_WITHIN_PLAN") == _rows(
        pandas_result, "DOWNTIME_WITHIN_PLAN"
    )


def test_direct_validation_finds_fewer_independent_problems_than_lazy(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    frame = changed_copy(
        valid_frame,
        shift="Weekend",
        produced_quantity="unknown",
        cycle_time_seconds="fast",
    )
    direct = validate_with_pandera(frame, lazy=False)
    lazy = validate_with_pandera(frame, lazy=True)
    assert not direct.is_valid
    assert not lazy.is_valid
    assert len(_error_ids(lazy)) > len(_error_ids(direct))
