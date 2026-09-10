"""Immutable contract settings for manufacturing production extracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionDataConfig:
    """Shared production-data contract used by later validation and reporting.

    Allowed values are stored as frozensets so membership checks stay
    unambiguous. Column lists stay as tuples so later schema code can keep
    a stable order.
    """

    required_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    allowed_production_lines: frozenset[str]
    allowed_machine_ids: frozenset[str]
    allowed_shifts: frozenset[str]
    allowed_product_codes: frozenset[str]


PRODUCTION_DATA_CONFIG = ProductionDataConfig(
    required_columns=(
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
    ),
    numeric_columns=(
        "produced_quantity",
        "good_quantity",
        "scrap_quantity",
        "downtime_minutes",
        "planned_minutes",
        "cycle_time_seconds",
    ),
    allowed_production_lines=frozenset({"Line-A", "Line-B"}),
    allowed_machine_ids=frozenset({"MC-101", "MC-102", "MC-201", "MC-202"}),
    allowed_shifts=frozenset({"Day", "Evening", "Night"}),
    allowed_product_codes=frozenset(
        {"PRD-A100", "PRD-B200", "PRD-C300", "PRD-D400"}
    ),
)
