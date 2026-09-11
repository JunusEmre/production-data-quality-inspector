"""Shared fixtures for production-quality validation tests."""

from __future__ import annotations

import pandas as pd
import pytest

from production_quality.config import PRODUCTION_DATA_CONFIG as CONFIG


def valid_row(**overrides: object) -> dict[str, object]:
    """Return one valid production row. Allowed categories come from config."""

    row: dict[str, object] = {
        "record_id": "PR-TEST-000001",
        "production_date": "2026-01-15",
        "plant": "Plant-01",
        "production_line": sorted(CONFIG.allowed_production_lines)[0],
        "machine_id": sorted(CONFIG.allowed_machine_ids)[0],
        "shift": sorted(CONFIG.allowed_shifts)[0],
        "product_code": sorted(CONFIG.allowed_product_codes)[0],
        "produced_quantity": 100,
        "good_quantity": 90,
        "scrap_quantity": 10,
        "downtime_minutes": 15,
        "planned_minutes": 480,
        "cycle_time_seconds": 4.5,
    }
    row.update(overrides)
    return row


@pytest.fixture
def valid_frame() -> pd.DataFrame:
    return pd.DataFrame([valid_row()])


@pytest.fixture
def boundary_frame() -> pd.DataFrame:
    """Legal boundary values, including zeros and exact equalities."""

    zero_quantities = valid_row(
        record_id="PR-TEST-BOUND-1",
        produced_quantity=0,
        good_quantity=0,
        scrap_quantity=0,
        downtime_minutes=0,
        planned_minutes=1,
        cycle_time_seconds=0.01,
    )
    equality = valid_row(
        record_id="PR-TEST-BOUND-2",
        production_line=sorted(CONFIG.allowed_production_lines)[1],
        machine_id=sorted(CONFIG.allowed_machine_ids)[1],
        shift=sorted(CONFIG.allowed_shifts)[1],
        product_code=sorted(CONFIG.allowed_product_codes)[1],
        produced_quantity=50,
        good_quantity=40,
        scrap_quantity=10,
        downtime_minutes=480,
        planned_minutes=480,
        cycle_time_seconds=1,
    )
    return pd.DataFrame([zero_quantities, equality])


@pytest.fixture
def two_valid_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            valid_row(),
            valid_row(record_id="PR-TEST-000002", shift=sorted(CONFIG.allowed_shifts)[1]),
        ]
    )


@pytest.fixture
def changed_copy():
    """Return a helper that copies a frame and changes the first row."""

    def _change(frame: pd.DataFrame, **updates: object) -> pd.DataFrame:
        out = frame.copy(deep=True)
        idx = out.index[0]
        for column, value in updates.items():
            if column in out.columns:
                out[column] = out[column].astype(object)
            out.loc[idx, column] = value
        return out

    return _change
