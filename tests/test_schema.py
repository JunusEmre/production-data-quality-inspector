"""Tests for the Pandera production schema."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from production_quality.config import PRODUCTION_DATA_CONFIG
from production_quality.schema import build_production_schema

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_schema_columns_match_config() -> None:
    schema = build_production_schema()
    assert tuple(schema.columns) == PRODUCTION_DATA_CONFIG.required_columns


def test_schema_accepts_valid_data(valid_frame: pd.DataFrame) -> None:
    validated = build_production_schema().validate(valid_frame, lazy=True)
    assert len(validated) == 1


def test_schema_accepts_boundary_data(boundary_frame: pd.DataFrame) -> None:
    validated = build_production_schema().validate(boundary_frame, lazy=True)
    assert len(validated) == 2


def test_schema_does_not_treat_extra_columns_as_fatal(valid_frame: pd.DataFrame) -> None:
    frame = valid_frame.copy(deep=True)
    frame["notes"] = "keep"
    validated = build_production_schema().validate(frame, lazy=True)
    assert "notes" in validated.columns


def test_importing_schema_does_not_read_production_csv(tmp_path: Path) -> None:
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
                "from production_quality.schema import build_production_schema\n"
                "build_production_schema()\n"
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
