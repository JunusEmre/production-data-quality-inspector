"""Tests for the validation-rule catalog."""

from dataclasses import FrozenInstanceError

import pytest

from production_quality.rules import VALIDATION_RULES, ValidationRule


EXPECTED_RULE_IDS = (
    "REQUIRED_COLUMNS",
    "UNEXPECTED_COLUMNS",
    "NONEMPTY_DATASET",
    "RECORD_ID_PRESENT",
    "UNIQUE_RECORD_ID",
    "VALID_PRODUCTION_DATE",
    "PLANT_PRESENT",
    "VALID_PRODUCTION_LINE",
    "VALID_MACHINE_ID",
    "VALID_SHIFT",
    "VALID_PRODUCT_CODE",
    "PRODUCED_QUANTITY_RANGE",
    "GOOD_QUANTITY_RANGE",
    "SCRAP_QUANTITY_RANGE",
    "DOWNTIME_MINUTES_RANGE",
    "PLANNED_MINUTES_RANGE",
    "CYCLE_TIME_RANGE",
    "QUANTITY_BALANCE",
    "DOWNTIME_WITHIN_PLAN",
)


def test_every_rule_id_is_unique() -> None:
    rule_ids = [rule.rule_id for rule in VALIDATION_RULES]
    assert len(rule_ids) == len(set(rule_ids))


def test_catalog_contains_the_nineteen_agreed_rules() -> None:
    assert len(VALIDATION_RULES) == 19
    assert tuple(rule.rule_id for rule in VALIDATION_RULES) == EXPECTED_RULE_IDS


def test_every_rule_has_a_nonempty_title_and_description() -> None:
    for rule in VALIDATION_RULES:
        assert rule.title.strip()
        assert rule.description.strip()


def test_rule_severity_is_only_error_or_warning() -> None:
    for rule in VALIDATION_RULES:
        assert rule.severity in {"Error", "Warning"}


def test_validation_rule_is_frozen() -> None:
    rule = VALIDATION_RULES[0]
    with pytest.raises(FrozenInstanceError):
        rule.title = "Changed"  # type: ignore[misc]


def test_rules_are_validation_rule_instances() -> None:
    assert all(isinstance(rule, ValidationRule) for rule in VALIDATION_RULES)
