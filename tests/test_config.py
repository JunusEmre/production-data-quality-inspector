"""Tests for the immutable production-data contract."""

from dataclasses import FrozenInstanceError

import pytest

from production_quality.config import PRODUCTION_DATA_CONFIG


def test_config_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        PRODUCTION_DATA_CONFIG.required_columns = ()  # type: ignore[misc]


def test_required_columns_match_expected_contract() -> None:
    assert PRODUCTION_DATA_CONFIG.required_columns == (
        "record_id",
        "production_date",
        "plant",
        "production_line",
        "machine_id",
        "shift",
        "product_code",
        "produced_quantity",
        "good_quantity",
        "scrap_quantity",
        "downtime_minutes",
        "planned_minutes",
        "cycle_time_seconds",
    )
    assert len(PRODUCTION_DATA_CONFIG.required_columns) == 13


def test_numeric_columns_match_expected_contract() -> None:
    assert PRODUCTION_DATA_CONFIG.numeric_columns == (
        "produced_quantity",
        "good_quantity",
        "scrap_quantity",
        "downtime_minutes",
        "planned_minutes",
        "cycle_time_seconds",
    )


def test_allowed_business_values_match_expected_contract() -> None:
    assert PRODUCTION_DATA_CONFIG.allowed_production_lines == frozenset(
        {"Line-A", "Line-B"}
    )
    assert PRODUCTION_DATA_CONFIG.allowed_machine_ids == frozenset(
        {"MC-101", "MC-102", "MC-201", "MC-202"}
    )
    assert PRODUCTION_DATA_CONFIG.allowed_shifts == frozenset(
        {"Day", "Evening", "Night"}
    )
    assert PRODUCTION_DATA_CONFIG.allowed_product_codes == frozenset(
        {"PRD-A100", "PRD-B200", "PRD-C300", "PRD-D400"}
    )


def test_allowed_value_collections_are_immutable() -> None:
    with pytest.raises(AttributeError):
        PRODUCTION_DATA_CONFIG.allowed_shifts.add("Weekend")  # type: ignore[attr-defined]
