"""Human-readable catalog of production data-quality rules.

This module documents the agreed business rules. It does not execute
validation; later stages will apply these rules with Pandera and pandas.
"""

from dataclasses import dataclass
from typing import Literal

from production_quality.config import PRODUCTION_DATA_CONFIG

Severity = Literal["Error", "Warning"]


@dataclass(frozen=True)
class ValidationRule:
    """One production data-quality rule, written for operational review."""

    rule_id: str
    title: str
    description: str
    severity: Severity
    columns: tuple[str, ...]


def _sorted_allowed(values: frozenset[str]) -> str:
    """Return allowed values in a stable, presentation-friendly order."""

    return ", ".join(sorted(values))


_CONFIG = PRODUCTION_DATA_CONFIG
_LINES = _sorted_allowed(_CONFIG.allowed_production_lines)
_MACHINES = _sorted_allowed(_CONFIG.allowed_machine_ids)
_SHIFTS = _sorted_allowed(_CONFIG.allowed_shifts)
_PRODUCTS = _sorted_allowed(_CONFIG.allowed_product_codes)

VALIDATION_RULES: tuple[ValidationRule, ...] = (
    ValidationRule(
        rule_id="REQUIRED_COLUMNS",
        title="All required production columns are present",
        description=(
            "The extract must include all 13 agreed columns covering record "
            "identity, plant, machine, product, quantities, and time. Missing "
            "columns make the file incomplete and prevent a fair quality review."
        ),
        severity="Error",
        columns=_CONFIG.required_columns,
    ),
    ValidationRule(
        rule_id="UNEXPECTED_COLUMNS",
        title="Unexpected extra columns are reported",
        description=(
            "Extra columns are reported because they often mean the extract "
            "layout changed. The extra fields are not treated as part of the "
            "agreed production contract until a rule is added for them."
        ),
        severity="Warning",
        columns=(),
    ),
    ValidationRule(
        rule_id="NONEMPTY_DATASET",
        title="The file contains at least one production row",
        description=(
            "A header-only file cannot describe production. There must be at "
            "least one row so quantities, downtime, and machine activity can "
            "be inspected."
        ),
        severity="Error",
        columns=(),
    ),
    ValidationRule(
        rule_id="RECORD_ID_PRESENT",
        title="Every row has a record ID",
        description=(
            "record_id is the tracking number for a production row. A blank "
            "ID makes the row hard to trace, correct, or compare with other "
            "reports."
        ),
        severity="Error",
        columns=("record_id",),
    ),
    ValidationRule(
        rule_id="UNIQUE_RECORD_ID",
        title="Record IDs are unique",
        description=(
            "Each production event should appear once. Duplicate record IDs "
            "can hide a repeated export, a copy-paste error, or two different "
            "events sharing the same identifier."
        ),
        severity="Error",
        columns=("record_id",),
    ),
    ValidationRule(
        rule_id="VALID_PRODUCTION_DATE",
        title="Production date is a real calendar date",
        description=(
            "production_date must be a valid date. Impossible values such as "
            "30 February cannot be placed on a production calendar or used in "
            "daily output reports."
        ),
        severity="Error",
        columns=("production_date",),
    ),
    ValidationRule(
        rule_id="PLANT_PRESENT",
        title="Every row names a plant",
        description=(
            "plant identifies the factory that produced the work. A blank "
            "plant leaves output, scrap, and downtime without an owner."
        ),
        severity="Error",
        columns=("plant",),
    ),
    ValidationRule(
        rule_id="VALID_PRODUCTION_LINE",
        title="Production line is an agreed line",
        description=(
            f"production_line must be one of: {_LINES}. Any other value is "
            "outside the current plant layout and cannot be assigned to a "
            "known line."
        ),
        severity="Error",
        columns=("production_line",),
    ),
    ValidationRule(
        rule_id="VALID_MACHINE_ID",
        title="Machine ID is an agreed machine",
        description=(
            f"machine_id must be one of: {_MACHINES}. Unknown or blank "
            "machine IDs cannot be tied to maintenance, capacity, or scrap "
            "investigation."
        ),
        severity="Error",
        columns=("machine_id",),
    ),
    ValidationRule(
        rule_id="VALID_SHIFT",
        title="Shift is an agreed working shift",
        description=(
            f"shift must be one of: {_SHIFTS}. Values such as Weekend are "
            "outside the current three-shift pattern and break shift "
            "comparisons."
        ),
        severity="Error",
        columns=("shift",),
    ),
    ValidationRule(
        rule_id="VALID_PRODUCT_CODE",
        title="Product code is an agreed product",
        description=(
            f"product_code must be one of: {_PRODUCTS}. A missing or unknown "
            "code means finished output cannot be attributed to a known SKU."
        ),
        severity="Error",
        columns=("product_code",),
    ),
    ValidationRule(
        rule_id="PRODUCED_QUANTITY_RANGE",
        title="Produced quantity is a number of zero or more",
        description=(
            "produced_quantity must be numeric and at least zero. Negative or "
            "non-numeric output cannot be used in production totals."
        ),
        severity="Error",
        columns=("produced_quantity",),
    ),
    ValidationRule(
        rule_id="GOOD_QUANTITY_RANGE",
        title="Good quantity is a number of zero or more",
        description=(
            "good_quantity must be numeric and at least zero. Negative or "
            "non-numeric good output understates or corrupts yield."
        ),
        severity="Error",
        columns=("good_quantity",),
    ),
    ValidationRule(
        rule_id="SCRAP_QUANTITY_RANGE",
        title="Scrap quantity is a number of zero or more",
        description=(
            "scrap_quantity must be numeric and at least zero. Negative or "
            "non-numeric scrap hides loss and distorts quality performance."
        ),
        severity="Error",
        columns=("scrap_quantity",),
    ),
    ValidationRule(
        rule_id="DOWNTIME_MINUTES_RANGE",
        title="Downtime minutes is a number of zero or more",
        description=(
            "downtime_minutes must be numeric and at least zero. Negative or "
            "non-numeric downtime cannot be used in availability reviews."
        ),
        severity="Error",
        columns=("downtime_minutes",),
    ),
    ValidationRule(
        rule_id="PLANNED_MINUTES_RANGE",
        title="Planned minutes is a number greater than zero",
        description=(
            "planned_minutes must be numeric and greater than zero. A missing, "
            "zero, or negative plan makes downtime and output impossible to "
            "judge against the intended run."
        ),
        severity="Error",
        columns=("planned_minutes",),
    ),
    ValidationRule(
        rule_id="CYCLE_TIME_RANGE",
        title="Cycle time is a number greater than zero",
        description=(
            "cycle_time_seconds must be numeric and greater than zero. Zero, "
            "negative, or text values such as 'fast' are not usable machine "
            "cycle times."
        ),
        severity="Error",
        columns=("cycle_time_seconds",),
    ),
    ValidationRule(
        rule_id="QUANTITY_BALANCE",
        title="Good plus scrap does not exceed produced quantity",
        description=(
            "good_quantity plus scrap_quantity must not be greater than "
            "produced_quantity. If good and scrap add up to more than total "
            "output, the quantity split is mathematically impossible."
        ),
        severity="Error",
        columns=("produced_quantity", "good_quantity", "scrap_quantity"),
    ),
    ValidationRule(
        rule_id="DOWNTIME_WITHIN_PLAN",
        title="Downtime does not exceed planned minutes",
        description=(
            "downtime_minutes must not be greater than planned_minutes. "
            "Stopped time longer than the planned run cannot be explained "
            "inside that shift's available minutes."
        ),
        severity="Error",
        columns=("downtime_minutes", "planned_minutes"),
    ),
)
