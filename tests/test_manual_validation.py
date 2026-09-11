"""Tests for the educational pandas comparison validator."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from production_quality.manual_validation import validate_with_pandas
from production_quality.models import ValidationResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _error_ids(result: ValidationResult) -> set[str]:
    return {issue.rule_id for issue in result.issues if issue.severity == "Error"}


def test_valid_data_passes(valid_frame: pd.DataFrame) -> None:
    result = validate_with_pandas(valid_frame)
    assert result.is_valid
    assert result.validator_name == "Pandas"
    assert result.validation_mode == "manual"
    assert result.validated_data is not None


def test_boundaries_pass(boundary_frame: pd.DataFrame) -> None:
    result = validate_with_pandas(boundary_frame)
    assert result.is_valid


@pytest.mark.parametrize(
    ("updates", "rule_id"),
    [
        ({}, None),
        ({"record_id": None}, "RECORD_ID_PRESENT"),
        ({"production_date": "2026-02-30"}, "VALID_PRODUCTION_DATE"),
        ({"plant": ""}, "PLANT_PRESENT"),
        ({"production_line": "Line-Z"}, "VALID_PRODUCTION_LINE"),
        ({"machine_id": None}, "VALID_MACHINE_ID"),
        ({"machine_id": "MC-999"}, "VALID_MACHINE_ID"),
        ({"shift": "Weekend"}, "VALID_SHIFT"),
        ({"product_code": None}, "VALID_PRODUCT_CODE"),
        ({"product_code": "PRD-Z999"}, "VALID_PRODUCT_CODE"),
        ({"produced_quantity": "unknown"}, "PRODUCED_QUANTITY_RANGE"),
        ({"produced_quantity": -1}, "PRODUCED_QUANTITY_RANGE"),
        ({"good_quantity": "x"}, "GOOD_QUANTITY_RANGE"),
        ({"good_quantity": -1}, "GOOD_QUANTITY_RANGE"),
        ({"scrap_quantity": "x"}, "SCRAP_QUANTITY_RANGE"),
        ({"scrap_quantity": -1}, "SCRAP_QUANTITY_RANGE"),
        ({"downtime_minutes": "x"}, "DOWNTIME_MINUTES_RANGE"),
        ({"downtime_minutes": -1}, "DOWNTIME_MINUTES_RANGE"),
        ({"planned_minutes": "x"}, "PLANNED_MINUTES_RANGE"),
        ({"planned_minutes": 0}, "PLANNED_MINUTES_RANGE"),
        ({"cycle_time_seconds": "fast"}, "CYCLE_TIME_RANGE"),
        ({"cycle_time_seconds": 0}, "CYCLE_TIME_RANGE"),
        (
            {"produced_quantity": 10, "good_quantity": 8, "scrap_quantity": 5},
            "QUANTITY_BALANCE",
        ),
        ({"downtime_minutes": 500}, "DOWNTIME_WITHIN_PLAN"),
    ],
)
def test_every_rule_can_be_detected(
    valid_frame: pd.DataFrame,
    changed_copy,
    updates: dict[str, object],
    rule_id: str | None,
) -> None:
    if rule_id is None:
        frame = valid_frame.drop(columns=["plant"])
        result = validate_with_pandas(frame)
        assert "REQUIRED_COLUMNS" in _error_ids(result)
        return
    result = validate_with_pandas(changed_copy(valid_frame, **updates))
    assert rule_id in _error_ids(result)


def test_empty_dataframe_is_detected(valid_frame: pd.DataFrame) -> None:
    result = validate_with_pandas(valid_frame.iloc[0:0])
    assert "NONEMPTY_DATASET" in _error_ids(result)


def test_duplicate_record_id_is_detected(two_valid_rows: pd.DataFrame) -> None:
    frame = two_valid_rows.copy(deep=True)
    frame.loc[1, "record_id"] = frame.loc[0, "record_id"]
    result = validate_with_pandas(frame)
    assert "UNIQUE_RECORD_ID" in _error_ids(result)
    assert {0, 1} <= {
        issue.row_index
        for issue in result.issues
        if issue.rule_id == "UNIQUE_RECORD_ID"
    }


def test_warnings_do_not_invalidate_the_result(valid_frame: pd.DataFrame) -> None:
    frame = valid_frame.copy(deep=True)
    frame["notes"] = "extra"
    result = validate_with_pandas(frame)
    assert result.is_valid
    assert result.warning_count == 1
    assert result.issues[0].rule_id == "UNEXPECTED_COLUMNS"


def test_invalid_data_returns_multiple_issues(
    valid_frame: pd.DataFrame, changed_copy
) -> None:
    result = validate_with_pandas(
        changed_copy(valid_frame, shift="Weekend", cycle_time_seconds="fast")
    )
    assert {"VALID_SHIFT", "CYCLE_TIME_RANGE"} <= _error_ids(result)


def test_input_is_not_mutated(valid_frame: pd.DataFrame, changed_copy) -> None:
    frame = changed_copy(valid_frame, shift="Weekend")
    snapshot = frame.copy(deep=True)
    validate_with_pandas(frame)
    pd.testing.assert_frame_equal(frame, snapshot)


def test_no_file_is_written(
    valid_frame: pd.DataFrame, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    validate_with_pandas(valid_frame)
    assert list(tmp_path.iterdir()) == []


def test_manual_module_source_does_not_import_pandera() -> None:
    source = (
        PROJECT_ROOT / "production_quality" / "manual_validation.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".")[0])
    assert "pandera" not in imported
    assert "production_quality.schema" not in source
    assert "validate_with_pandera" not in source


def test_importing_manual_validation_does_not_import_pandera() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import production_quality.manual_validation as module\n"
                "assert 'pandera' not in sys.modules\n"
                "assert 'production_quality.schema' not in sys.modules\n"
                "assert 'production_quality.validation' not in sys.modules\n"
                "assert module.validate_with_pandas.__name__\n"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
