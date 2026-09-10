"""Tests for safe production-data loading."""

from __future__ import annotations

import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest

from production_quality.config import PRODUCTION_DATA_CONFIG
from production_quality.data import load_production_data
from production_quality.exceptions import DataLoadError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_HEADER = ",".join(PRODUCTION_DATA_CONFIG.required_columns)

VALID_ROW = (
    "PR-2026-000001,2026-01-01,Plant-01,Line-A,MC-101,Day,PRD-A100,"
    "5260,5168,92,0,480,4.86"
)
INVALID_ROW = (
    "PR-2026-BAD,2026-02-30,Plant-01,Line-A,MC-999,Weekend,PRD-A100,"
    "unknown,-10,-3,-15,480,fast"
)


def _write_csv(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def test_load_production_data_reads_a_valid_temporary_csv(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "valid.csv",
        f"{REQUIRED_HEADER}\n{VALID_ROW}\n",
    )

    frame = load_production_data(csv_path)

    assert list(frame.columns) == list(PRODUCTION_DATA_CONFIG.required_columns)
    assert len(frame) == 1
    assert frame.loc[0, "record_id"] == "PR-2026-000001"
    assert frame.loc[0, "shift"] == "Day"


def test_load_production_data_accepts_bytesio() -> None:
    buffer = BytesIO(f"{REQUIRED_HEADER}\n{VALID_ROW}\n".encode("utf-8"))

    frame = load_production_data(buffer)

    assert len(frame) == 1
    assert frame.loc[0, "product_code"] == "PRD-A100"


def test_load_does_not_repair_or_alter_invalid_values(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "invalid.csv",
        f"{REQUIRED_HEADER}\n{VALID_ROW}\n{INVALID_ROW}\n",
    )

    frame = load_production_data(csv_path)

    assert len(frame) == 2
    assert frame.loc[1, "production_date"] == "2026-02-30"
    assert frame.loc[1, "machine_id"] == "MC-999"
    assert frame.loc[1, "shift"] == "Weekend"
    assert frame.loc[1, "produced_quantity"] == "unknown"
    assert int(frame.loc[1, "good_quantity"]) == -10
    assert int(frame.loc[1, "scrap_quantity"]) == -3
    assert int(frame.loc[1, "downtime_minutes"]) == -15
    assert frame.loc[1, "cycle_time_seconds"] == "fast"


def test_returned_dataframe_is_independent_from_later_input_changes(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(
        tmp_path / "source.csv",
        f"{REQUIRED_HEADER}\n{VALID_ROW}\n",
    )
    buffer = BytesIO(csv_path.read_bytes())

    from_path = load_production_data(csv_path)
    from_buffer = load_production_data(buffer)

    csv_path.write_text("tampered\n", encoding="utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    buffer.write(b"tampered")

    assert from_path.loc[0, "record_id"] == "PR-2026-000001"
    assert from_buffer.loc[0, "record_id"] == "PR-2026-000001"

    from_path.loc[0, "record_id"] = "CHANGED"
    assert from_buffer.loc[0, "record_id"] == "PR-2026-000001"


def test_missing_file_raises_data_load_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.csv"

    with pytest.raises(DataLoadError, match="does not exist") as error:
        load_production_data(missing)

    assert "does-not-exist.csv" in str(error.value)


def test_header_only_csv_raises_data_load_error(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "headers_only.csv", f"{REQUIRED_HEADER}\n")

    with pytest.raises(DataLoadError, match="no production rows"):
        load_production_data(csv_path)


def test_csv_with_no_columns_raises_data_load_error(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "empty.csv", "")

    with pytest.raises(DataLoadError, match="no columns"):
        load_production_data(csv_path)


def test_load_preserves_original_row_index(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "two_rows.csv",
        f"{REQUIRED_HEADER}\n{VALID_ROW}\n{INVALID_ROW}\n",
    )

    frame = load_production_data(csv_path)

    assert list(frame.index) == [0, 1]


def test_load_does_not_enforce_business_schema(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "other.csv", "a,b\n1,2\n")

    frame = load_production_data(csv_path)

    assert list(frame.columns) == ["a", "b"]
    assert frame.loc[0, "a"] == 1


def test_unreadable_content_raises_data_load_error() -> None:
    with pytest.raises(DataLoadError, match="cannot be read as CSV"):
        load_production_data(BytesIO(b"\x00\x01\x02\xff"))


def test_importing_package_does_not_read_csv_or_create_files(tmp_path: Path) -> None:
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
                "        raise AssertionError('production_data.csv must not be read on import')\n"
                "    return original_open(file, *args, **kwargs)\n"
                "\n"
                "builtins.open = guarded_open\n"
                "import production_quality\n"
                "assert production_quality.VALIDATION_RULES\n"
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
