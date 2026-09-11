"""Production Data Quality Inspector.

The public interface covers loading, validation, scoring, and report
builders. Importing this package does not read production files, start
Streamlit, run validation, or write output.
"""

from production_quality.config import PRODUCTION_DATA_CONFIG, ProductionDataConfig
from production_quality.data import load_production_data
from production_quality.exceptions import DataLoadError
from production_quality.manual_validation import validate_with_pandas
from production_quality.models import ValidationIssue, ValidationResult
from production_quality.quality import QualitySummary, calculate_quality_summary
from production_quality.reporting import (
    build_affected_records,
    build_issue_report,
    build_quality_summary_frame,
    build_rule_summary,
    dataframe_to_csv_bytes,
)
from production_quality.rules import VALIDATION_RULES, ValidationRule

__all__ = [
    "PRODUCTION_DATA_CONFIG",
    "ProductionDataConfig",
    "DataLoadError",
    "load_production_data",
    "ValidationRule",
    "VALIDATION_RULES",
    "ValidationIssue",
    "ValidationResult",
    "QualitySummary",
    "calculate_quality_summary",
    "build_issue_report",
    "build_affected_records",
    "build_rule_summary",
    "build_quality_summary_frame",
    "dataframe_to_csv_bytes",
    "build_production_schema",
    "validate_with_pandera",
    "validate_file_with_pandera",
    "validate_with_pandas",
]

_LAZY_EXPORTS = {
    "build_production_schema": ("production_quality.schema", "build_production_schema"),
    "validate_with_pandera": ("production_quality.validation", "validate_with_pandera"),
    "validate_file_with_pandera": (
        "production_quality.validation",
        "validate_file_with_pandera",
    ),
}


def __getattr__(name: str):
    """Load Pandera helpers only when they are first used."""

    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))
